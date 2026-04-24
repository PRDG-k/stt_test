import json
import logging
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from app.services.nlu_core import _call_vllm, _extract_params, load_resource, ACTION_SELECT_PROMPT
from app.services.action_manager import action_manager
from app.models.database import get_similar_cases
from jinja2 import Template

# 워크플로우 로거 설정
logger = logging.getLogger("workflow_logger")

# 그래프 상태 정의
class AgentState(TypedDict):
    text: str
    session_id: str
    messages: Annotated[List[BaseMessage], add_messages]
    selected_actions: List[str]
    candidates: List[Dict[str, Any]]
    final_message: str
    is_fallback: bool

# 노드 1: 동작 선택 (Action Selection)
async def select_action_node(state: AgentState):
    text = state["text"]
    session_id = state.get("session_id", "unknown")
    logger.info(f"--- [Node: select_action][Session ID: {session_id}] Processing input: '{text}' ---")
    
    # 대화 기록 포맷팅 (AIMessage 반영)
    history = "\n".join([f"{m.type}: {m.content}" for m in state["messages"][-5:]])
    
    # 현재까지 생성된 행동 계획 및 파라미터 정보 포맷팅
    current_plan = ""
    if state.get("selected_actions"):
        current_plan = f"선택된 액션: {', '.join(state['selected_actions'])}\n"
        if state.get("candidates"):
            current_plan += "현재 추출된 파라미터:\n"
            for cand in state["candidates"]:
                current_plan += f"- {cand['action']}: {json.dumps(cand.get('params', cand), ensure_ascii=False)}\n"

    action_schemas_text = action_manager.get_all_schemas_text()
    dynamic_context = action_manager.get_dynamic_prompt_context()
    select_template = Template(load_resource(ACTION_SELECT_PROMPT))

    # Strict 시도
    logger.info(f"[Session ID: {session_id}] Attempting Stage 1 (Strict Analysis)...")
    prompt_s1 = select_template.render(
        tools_yaml=action_schemas_text,
        dynamic_context=dynamic_context,
        text=text,
        history=history,
        current_plan=current_plan,
        reference_cases=[],
        is_fallback=False
    )
    
    selection = await _call_vllm(prompt_s1)
    actions = selection.get("actions", []) if selection else []
    
    # 기존에 선택된 액션이 있고, 새로운 입력이 해당 액션의 보충 정보인 경우 기존 액션 유지
    if not actions and state.get("selected_actions"):
        actions = state["selected_actions"]
        logger.info(f"[Session ID: {session_id}] Maintaining existing actions: {actions}")

    if actions:
        logger.info(f"[Session ID: {session_id}] Stage 1 Success. Selected actions: {actions}")
    
    is_fallback = False

    # Fallback 시도 (피드백 주입)
    if not actions:
        logger.info(f"[Session ID: {session_id}] Stage 1 failed or returned no actions. Attempting Stage 2 (Fallback)...")
        reference_cases = get_similar_cases(text, limit=3)
        if reference_cases:
            prompt_s2 = select_template.render(
                tools_yaml=action_schemas_text,
                dynamic_context=dynamic_context,
                text=text,
                history=history,
                current_plan=current_plan,
                reference_cases=reference_cases,
                is_fallback=True
            )
            selection = await _call_vllm(prompt_s2)
            actions = selection.get("actions", []) if selection else []
            if actions:
                logger.info(f"[Session ID: {session_id}] Stage 2 Success (with feedback). Recommended: {actions}")
            is_fallback = True

    if not actions:
        logger.warning(f"[Session ID: {session_id}] No actions determined. Returning clarification message.")

    return {
        "selected_actions": actions,
        "final_message": (selection.get("message", "") if selection else "") or "죄송합니다. 요청하신 내용을 이해하지 못했습니다. 다시 말씀해 주시겠어요?",
        "is_fallback": is_fallback
    }

# 노드 2: 파라미터 추출 (Parameter Extraction)
async def extract_params_node(state: AgentState):
    actions = state["selected_actions"]
    text = state["text"]
    session_id = state.get("session_id", "unknown")
    final_message = state.get("final_message", "")
    
    if not actions:
        logger.info(f"[Session ID: {session_id}] No actions to extract params for. Skipping node.")
        return {"candidates": []}

    logger.info(f"--- [Node: extract_params][Session ID: {session_id}] Extracting params for actions: {actions} ---")
    
    dynamic_context = action_manager.get_dynamic_prompt_context()
    
    # 기존에 추출된 후보(파라미터 포함) 정보 가져오기
    existing_candidates = {c['action']: c for c in state.get("candidates", [])}
    
    candidates = []
    all_missing_fields = []
    
    for action_name in actions:
        logger.info(f"[Session ID: {session_id}] Processing extraction for: {action_name}")
        
        # 해당 액션의 기존 데이터 객체가 있으면 전달
        current_action_obj = existing_candidates.get(action_name)

        # logger.info(f"[Session ID: {session_id}] Dynamic prompts of param node\n-> {dynamic_context}")
        
        full_action = await _extract_params(action_name, text, dynamic_context, current_action_obj)
        if full_action:
            is_valid, missing_fields = action_manager.validate_action(full_action)
            
            # 액션이 식별되었다면 유효성 여부와 상관없이 candidates에 추가 (null 포함 구조 유지)
            candidates.append(full_action)
            
            if is_valid:
                logger.info(f"[Session ID: {session_id}] Successfully validated action: {action_name}")
            else:
                all_missing_fields.extend(missing_fields)
                logger.warning(f"[Session ID: {session_id}] Action '{action_name}' is incomplete. Missing: {missing_fields}")
        else:
            logger.error(f"[Session ID: {session_id}] Failed to extract params for action: {action_name}")
            
    # 누락된 파라미터가 있다면 재질의 메시지 생성
    if all_missing_fields:
        unique_missing = list(set(all_missing_fields))
        missing_str = ", ".join(unique_missing)
        final_message = f"명령을 실행하기 위해 부족한 정보가 있습니다. {missing_str} 정보를 알려주세요."

    return {
        "candidates": candidates,
        "final_message": final_message
    }

# 그래프 구성
def create_nlu_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("select_action", select_action_node)
    workflow.add_node("extract_params", extract_params_node)
    
    workflow.set_entry_point("select_action")
    workflow.add_edge("select_action", "extract_params")
    workflow.add_edge("extract_params", END)
    
    return workflow
