import json
import re
import os
from functools import lru_cache
from jinja2 import Template
from app.core.config import settings, vllm_client
from app.models.schemas import NLUResponse
from app.models.database import get_similar_cases
from app.services.action_manager import action_manager
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from app.services.workflow import create_nlu_graph
from app.services.memory import MemoryManager, MemoryState

# 글로벌 변수로 관리
_nlu_app = None

async def get_nlu_app():
    global _nlu_app
    if _nlu_app is None:
        # 비동기로 체크포인터 초기화 및 그래프 컴파일
        checkpointer = await MemoryManager.get_checkpointer()
        _nlu_app = create_nlu_graph().compile(checkpointer=checkpointer)
    return _nlu_app

async def parse_intent(
    text: str, 
    session_id: str = "default_user",
    project_id: Optional[str] = None,
    selected_candidate: Optional[Dict[str, Any]] = None
) -> NLUResponse:
    # 워크플로우 인스턴스 획득
    nlu_app = await get_nlu_app()

    # LangGraph 워크플로우 실행
    config = {"configurable": {"thread_id": session_id}}

    # 초기 상태 설정 (이전 대화 기록 및 행동 계획은 체크포인터가 자동으로 불러옴)
    initial_input = {
        "text": text,
        "session_id": session_id,
        "project_id": project_id,
        "messages": [HumanMessage(content=text)]
    }
    
    if selected_candidate:
        initial_input["selected_actions"] = [selected_candidate.get("action")]
        initial_input["candidates"] = [selected_candidate]

    result = await nlu_app.ainvoke(initial_input, config=config)

    # 실행 완료 후 AI 메시지 상태 및 행동 계획 업데이트
    final_ai_msg = result["final_message"] or "이해했습니다."
    
    # LangGraph 상태 업데이트 (메시지 이력 + 행동 계획)
    await nlu_app.aupdate_state(config, {
        "messages": [AIMessage(content=final_ai_msg)],
        "selected_actions": result["selected_actions"],
        "candidates": result["candidates"]
    })

    return NLUResponse(
        transcript=text,
        message=final_ai_msg,
        candidates=result["candidates"],
        requires_confirmation=result["is_fallback"] or any(c.get("requires_confirmation", True) for c in result["candidates"]),
        session_id=session_id
    )

