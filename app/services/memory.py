import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from app.core.config import settings
from app.services.checkpoint import AsyncCheckpointManager

# 로거 설정
logger = logging.getLogger(__name__)

class MemoryState(BaseModel):
    """Memory manager를 위한 상태 모델 (메시지 이력 + 현재 행동 계획)"""
    messages: List[Dict[str, str]] = Field(default_factory=list)
    selected_actions: List[str] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)

class MemoryManager:
    _manager: Optional[AsyncCheckpointManager[MemoryState]] = None

    @classmethod
    async def get_manager(cls) -> AsyncCheckpointManager[MemoryState]:
        try:
            if cls._manager is None:
                # Ensure schema exists
                if settings.PG_CHECKPOINT_SCHEMA:
                    # Using a temporary connection to create schema
                    async with await AsyncConnection.connect(settings.postgres_dsn, autocommit=True) as conn:
                        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {settings.PG_CHECKPOINT_SCHEMA}")
                
                cls._manager = await AsyncCheckpointManager.create(
                    db_uri=settings.postgres_dsn,
                    state_model=MemoryState,
                    checkpoint_name=settings.PG_CHECKPOINT_SCHEMA
                )
            return cls._manager
        except Exception as e:
            logger.error(f"Error in get_manager: {e}", exc_info=True)
            raise

    @classmethod
    async def get_checkpointer(cls) -> AsyncPostgresSaver:
        """LangGraph 그래프에서 사용할 체크포인터를 반환"""
        try:
            manager = await cls.get_manager()
            return manager.checkpointer
        except Exception as e:
            logger.error(f"Error in get_checkpointer: {e}", exc_info=True)
            raise

    @classmethod
    async def save_message(cls, session_id: str, role: str, content: str):
        """세션에 메시지를 수동으로 저장"""
        try:
            manager = await cls.get_manager()
            state = await manager.load_state(session_id) or MemoryState()
            state.messages.append({"role": role, "content": content})
            await manager.save_state(session_id, state)
        except Exception as e:
            logger.error(f"[Session ID: {session_id}] Error in save_message: {e}", exc_info=True)
            raise

    @classmethod
    async def get_history(cls, session_id: str) -> str:
        """세션의 메시지 이력을 문자열로 반환"""
        try:
            manager = await cls.get_manager()
            state = await manager.load_state(session_id)
            if not state:
                return ""
            
            return "\n".join([f"{m['role']}: {m['content']}" for m in state.messages])
        except Exception as e:
            logger.error(f"[Session ID: {session_id}] Error in get_history: {e}", exc_info=True)
            raise
