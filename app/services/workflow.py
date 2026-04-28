import json
import logging
from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from app.services.nlu_core import _call_vllm, _extract_params, _validate_message, load_resource, ACTION_SELECT_PROMPT
from app.services.action_manager import action_manager
from app.models.database import get_similar_cases
from jinja2 import Template

# 워크플로우 로거 설정
logger = logging.getLogger("workflow_logger")

# 그래프 상태 정의
class AgentState(TypedDict):
    text: str
    session_id: str
    project_id: Optional[str]
    sl_id: Optional[str]
    messages: Annotated[List[BaseMessage], add_messages]
    selected_actions: List[str]
    candidates: List[Dict[str, Any]]
    final_message: str
    is_fallback: bool

# 노드 1: 동작 선택 (Action Selection)
async def select_action_node(state: AgentState):
    text = state["text"]
    session_id = state.get("session_id", "unknown")
    
    # 프론트엔드에서 불완전한 후보군(candid)을 선택하여 전달한 경우, 액션 선택 생략
    if state.get("selected_actions") and state.get("candidates"):
        logger.info(f"--- [Node: select_action][Session ID: {session_id}] Bypassing action selection. Frontend provided candidate. ---")
        return {"selected_actions": state["selected_actions"]}

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
    
    # 대화 기록 포맷팅 (숫자 답변 매핑을 위해 전달)
    history = "\n".join([f"{m.type}: {m.content}" for m in state["messages"][-5:]])

    # 기존에 추출된 후보(파라미터 포함) 정보 가져오기
    existing_candidates = {c['action']: c for c in state.get("candidates", [])}
    
    candidates = []
    all_missing_fields_info = [] # (field_name, action_name) 튜플 리스트
    
    for action_name in actions:
        logger.info(f"[Session ID: {session_id}] Processing extraction for: {action_name}")
        
        # 해당 액션의 기존 데이터 객체가 있으면 전달
        current_action_obj = existing_candidates.get(action_name)

        # 기본 인자(ProjectID, SLID) 주입 시도
        if current_action_obj is None:
            current_action_obj = {}
        
        # MOVE_PAGE 등에서 사용하는 projectId, slId 기본값 주입
        if state.get("project_id") and "projectId" not in current_action_obj:
            current_action_obj["projectId"] = state["project_id"]
        
        if state.get("sl_id"):
            if "params" not in current_action_obj:
                current_action_obj["params"] = {}
            if isinstance(current_action_obj["params"], dict) and "slId" not in current_action_obj["params"]:
                current_action_obj["params"]["slId"] = state["sl_id"]
        
        full_action = await _extract_params(action_name, text, dynamic_context, current_action_obj, history=history)
        if full_action:
            is_valid, missing_fields = action_manager.validate_action(full_action, text=text)
            
            # 액션 객체에 fallback 정보 및 확인 필요 여부 주입
            full_action["is_fallback"] = state.get("is_fallback", False)
            full_action["requires_confirmation"] = not is_valid or state.get("is_fallback", False)
            
            # -----------------------------------------------------------
            # [구조 변경] 파라미터 후보군 기반 액션 확장 (Expansion)
            # -----------------------------------------------------------
            expanded_candidates = []
            if missing_fields:
                # [고도화] 우선순위에 따라 missing_fields 정렬
                priority_map = action_manager.ACTION_FIELD_PRIORITY.get(action_name, [])
                def get_priority(f):
                    try: return priority_map.index(f)
                    except ValueError: return 999
                missing_fields.sort(key=get_priority)
                
                # 첫 번째 누락된 필드(최우선순위)를 기준으로 확장 시도
                target_field = missing_fields[0]
                field_choices = action_manager.get_field_candidates(action_name, target_field, text=text)
                
                # 후보군이 적절한 개수(2~5개)인 경우 액션 복제 확장
                if 1 < len(field_choices) <= 5:
                    logger.info(f"[Session ID: {session_id}] Expanding action '{action_name}' into {len(field_choices)} candidates based on '{target_field}'")
                    for choice in field_choices:
                        # 액션 객체 깊은 복사 및 필드 채우기
                        clone = json.loads(json.dumps(full_action))
                        
                        # [고도화] 스키마를 확인하여 target_field가 속해야 할 정확한 위치(root vs params)에 주입
                        schema = action_manager.load_schema(action_name)
                        params_props = schema.get("properties", {}).get("params", {}).get("properties", {}) if schema else {}
                        
                        if target_field in params_props:
                            if "params" not in clone or not isinstance(clone["params"], dict):
                                clone["params"] = {}
                            clone["params"][target_field] = choice
                        else:
                            clone[target_field] = choice

                        # 메시지 재생성 (확정형으로 변경)
                        if "params" in clone and isinstance(clone["params"], dict) and "message" in clone["params"]:
                            clone["params"]["message"] = None # 메시지는 프론트엔드가 생성하도록 Null 처리

                        # 복제된 후보는 그 자체로 선택지이므로 confirmation을 False로 설정할 수 있음
                        clone["requires_confirmation"] = False
                        expanded_candidates.append(clone)
                
                # 확장 여부와 상관없이 parameter_candidates 정보는 유지 (UI 보조용)
                full_action["parameter_candidates"] = {}
                for field in missing_fields:
                    all_choices = action_manager.get_field_candidates(action_name, field, text=text)
                    if all_choices:
                        full_action["parameter_candidates"][field] = all_choices
                        all_missing_fields_info.append((field, action_name, all_choices))
                    else:
                        all_missing_fields_info.append((field, action_name, []))

            if expanded_candidates:
                candidates.extend(expanded_candidates)
                # 다중 후보가 생성되었으므로 root message 조정 필요 플래그 설정 가능
                if not ("?" in final_message or "선택" in final_message):
                    final_message = "원하시는 항목을 선택해 주세요."
            else:
                # 확장이 안 된 경우 기존처럼 하나의 객체 추가
                candidates.append(full_action)
            
            if is_valid:
                logger.info(f"[Session ID: {session_id}] Successfully validated action: {action_name}")
            else:
                logger.warning(f"[Session ID: {session_id}] Action '{action_name}' is incomplete. Missing: {missing_fields}")
        else:
            logger.error(f"[Session ID: {session_id}] Failed to extract params for action: {action_name}")
            
    # 누락된 파라미터가 있다면 규칙 기반으로 메시지를 무조건 덮어씀 (환각 방지)
    if all_missing_fields_info:
        unique_missing_fields = list(set([info[0] for info in all_missing_fields_info]))
        missing_str = ", ".join(unique_missing_fields)
        final_message = f"명령을 실행하기 위해 부족한 정보가 있습니다. {missing_str} 정보를 알려주세요."
        
        options_text = ""
        for field, action, choices in all_missing_fields_info:
            if choices:
                choices_str = ", ".join([f"{i+1}. {c}" for i, c in enumerate(choices)])
                options_text += f"\n- {field} 선택지: {choices_str}"
        
        if options_text:
            final_message += options_text

    return {
        "candidates": candidates,
        "final_message": final_message
    }

# 노드 3: 메시지 검수 (Message Validation)
async def validate_message_node(state: AgentState):
    text = state["text"]
    final_message = state.get("final_message", "")
    candidates = state.get("candidates", [])
    session_id = state.get("session_id", "unknown")
    
    # 1. 모든 파라미터가 유효한 경우(requires_confirmation == False), candidates 내부의 message로 루트 final_message 동기화
    all_valid = all(not c.get("requires_confirmation") for c in candidates) if candidates else False
    
    if all_valid:
        # candidates의 params 중 message 필드가 있는 경우 이를 수집
        messages = [c.get("params", {}).get("message") for c in candidates if isinstance(c.get("params"), dict) and c.get("params", {}).get("message")]
        if messages:
            new_message = " ".join(messages)
            if new_message != final_message:
                logger.info(f"[Session ID: {session_id}] Action is fully validated. Syncing root message to extracted message: '{new_message}'")
                return {"final_message": new_message}

    # 2. 질문 형식의 메시지가 있고, 파라미터가 누락된 상황(candidates 중 하나라도 requires_confirmation인 경우)에서 환각/모호성 검수 수행
    needs_validation = any(c.get("requires_confirmation") for c in candidates)
    is_static_message = final_message.startswith("명령을 실행하기 위해 부족한 정보가 있습니다.")
    
    if final_message and needs_validation and not is_static_message:
        logger.info(f"--- [Node: validate_message][Session ID: {session_id}] Validating message: '{final_message}' ---")
        validated_message = await _validate_message(text, final_message, candidates)
        
        if validated_message != final_message:
            logger.info(f"[Session ID: {session_id}] Message corrected: '{validated_message}'")
            return {"final_message": validated_message}
            
    return {"final_message": final_message}

# 그래프 구성
def create_nlu_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("select_action", select_action_node)
    workflow.add_node("extract_params", extract_params_node)
    workflow.add_node("validate_message", validate_message_node)
    
    workflow.set_entry_point("select_action")
    workflow.add_edge("select_action", "extract_params")
    workflow.add_edge("extract_params", "validate_message")
    workflow.add_edge("validate_message", END)
    
    return workflow
