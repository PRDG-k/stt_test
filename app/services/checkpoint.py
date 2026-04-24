from typing import Type, TypeVar, Optional, List, Generic, Dict, Any
from pydantic import BaseModel
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from psycopg.rows import dict_row


# Pydantic 모델을 위한 제네릭 타입 변수
T = TypeVar('T', bound=BaseModel)

class AsyncCheckpointManager(Generic[T]):
    def __init__(self, 
                 pool: AsyncConnectionPool,
                 checkpointer: AsyncPostgresSaver, 
                 state_model: Type[T],
                 flow: Any
                 ):
        """
        Args:
            db_uri: PostgreSQL 연결 문자열
            state_model: 상태를 매핑할 Pydantic 클래스
        """
        self.state_model = state_model
        self.pool = pool
        self.checkpointer = checkpointer
        self.flow = flow

    
    @classmethod
    async def create(cls, db_uri: str, state_model: Type[T], checkpoint_name: str = "langgraph_ckpt") -> "AsyncCheckpointManager":
        pool = AsyncConnectionPool(conninfo=db_uri, open=False,
                                   kwargs={
                                       "row_factory": dict_row,
                                       "options": f"-c search_path={checkpoint_name}",
                                       "autocommit": True
                                   })
        await pool.open()

        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()

        # 워크플로우(라우팅) 로직 제거.
        # 오직 상태 저장/조회를 위한 '빈 껍데기' 그래프 구성
        builder = StateGraph(dict) 
        builder.add_node("__store__", lambda x: x)
        builder.add_edge(START, "__store__")
        flow = builder.compile(checkpointer=checkpointer)

        return cls(pool, checkpointer, state_model, flow)


    async def load_state(self, thread_id: str) -> Optional[T]:
        """
        [복원] 가장 최근의 체크포인트를 불러와 Pydantic 모델로 변환해 반환
        """
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = await self.flow.aget_state(config)
        
        # 저장된 상태가 없으면 None 반환
        if not state_snapshot or not state_snapshot.values:
            return None
            
        # 딕셔너리를 사용자의 Pydantic 모델로 매핑하여 반환.
        # OrchestratorContext를 복원하면 될 듯?
        return self.state_model.model_validate(state_snapshot.values)

    async def save_state(self, thread_id: str, state_data: T) -> str:
        """
        [저장/업데이트] Pydantic 모델의 현재 상태를 새로운 체크포인트로 저장
        반환값: 생성된 체크포인트의 고유 ID (thread_ts)
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        # Pydantic -> dict 변환
        state_dict = state_data.model_dump(mode="json")
        
        updated_config = await self.flow.aupdate_state(config, state_dict, as_node="__store__")
        
        # return updated_config["configurable"]["thread_ts"]
        return updated_config["configurable"]

    async def get_history(self, thread_id: str) -> List[T]:
        """
        [이력 추적] 해당 스레드의 과거 상태 변경 이력을 모두 Pydantic 객체 리스트로 불러
        최신 상태부터 역순으로 정렬돼.
        """
        config = {"configurable": {"thread_id": thread_id}}
        history_async_gen = self.flow.aget_state_history(config)
        
        result_history = []
        async for snapshot in history_async_gen:
            if snapshot.values:
                try:
                    parsed_state = await self.state_model.model_validate(snapshot.values)
                    result_history.append(parsed_state)
                except Exception as e:
                    # 스키마가 변경되기 전의 아주 오래된 데이터 등 변환 실패 시 안전하게 무시 (필요시 로깅)
                    pass
                    
        return result_history

    async def close(self):
        """DB 커넥션 해제"""
        if self.pool:
            await self.pool.close()

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()



class AsyncCheckpointAggregator(Generic[T]):
    def __init__(self, graph: AsyncCheckpointManager, index: AsyncCheckpointManager):
        self._graph = graph
        self._index = index

    def filter_checkpoint(self, tags: List[str]) -> List[T]:
        ...

    # def _get_index