import pytest
import asyncio
import json
from app.services.nlu_core import _extract_params
from app.services.workflow import _call_vllm, ACTION_SELECT_PROMPT, load_resource
from app.services.action_manager import action_manager
from jinja2 import Template

@pytest.fixture
def select_template():
    return Template(load_resource(ACTION_SELECT_PROMPT))

@pytest.fixture
def context_data():
    return {
        "tools_yaml": action_manager.get_all_schemas_text(),
        "dynamic_context": action_manager.get_dynamic_prompt_context(),
        "history": "",
        "current_plan": "",
        "reference_cases": [],
        "is_fallback": False
    }

@pytest.mark.asyncio
async def test_move_page_precise(select_template, context_data):
    """정확한 페이지 이동 요청 테스트"""
    text = "SL-100 화면으로 이동해줘"
    
    # 1. 액션 선택 테스트
    prompt_s1 = select_template.render(text=text, **context_data)
    selection = await _call_vllm(prompt_s1)
    
    assert selection is not None
    assert "MOVE_PAGE" in selection.get("actions", [])
    
    # 2. 파라미터 추출 테스트
    full_action = await _extract_params("MOVE_PAGE", text, context_data["dynamic_context"])
    
    assert full_action["action"] == "MOVE_PAGE"
    assert "params" in full_action
    assert full_action["params"]["slId"] == "SL-100"

@pytest.mark.asyncio
async def test_data_fetch_ambiguous(select_template, context_data):
    """모호한 데이터 조회 요청 테스트 (파라미터 누락 시 null 반환 확인)"""
    text = "발전량 보여줘"
    
    # 1. 액션 선택
    prompt_s1 = select_template.render(text=text, **context_data)
    selection = await _call_vllm(prompt_s1)
    
    assert "DATA_FETCH" in selection.get("actions", [])
    
    # 2. 파라미터 추출
    full_action = await _extract_params("DATA_FETCH", text, context_data["dynamic_context"])
    
    print(f"Ambiguous Result: {json.dumps(full_action, indent=2, ensure_ascii=False)}")
    assert full_action["action"] == "DATA_FETCH"
    # 필수 파라미터인 device가 null(None)이어야 함
    assert full_action["params"].get("device") is None

@pytest.mark.asyncio
async def test_show_msg_precise(select_template, context_data):
    """메시지 표시 요청 테스트"""
    text = "안녕하세요라고 인사해줘"
    
    prompt_s1 = select_template.render(text=text, **context_data)
    selection = await _call_vllm(prompt_s1)
    
    assert "SHOW_MSG" in selection.get("actions", [])
    
    full_action = await _extract_params("SHOW_MSG", text, context_data["dynamic_context"])
    assert full_action["content"] == "안녕하세요"
    assert full_action["type"] == "info"

@pytest.mark.asyncio
async def test_data_fetch_interaction_refinement(select_template, context_data):
    """상호작용을 통한 파라미터 구체화 테스트 (2-Turn)"""
    
    # --- Turn 1: 모호한 요청 ---
    text_1 = "발전량 보여줘"
    prompt_1 = select_template.render(text=text_1, **context_data)
    selection_1 = await _call_vllm(prompt_1)
    
    assert "DATA_FETCH" in selection_1["actions"]
    
    # 파라미터 추출 (device 누락 상태)
    result_1 = await _extract_params("DATA_FETCH", text_1, context_data["dynamic_context"])
    assert result_1["params"]["device"] is None
    
    # --- Turn 2: 부족한 정보 보충 ---
    text_2 = "인버터 1번"
    
    # 2턴 프롬프트 구성 시 대화 기록(history)과 현재 계획(current_plan)을 모두 주입
    history = f"user: {text_1}\nai: {selection_1.get('message', '')}"
    current_plan = f"선택된 액션: DATA_FETCH\n현재 추출된 파라미터:\n- DATA_FETCH: {json.dumps(result_1['params'], ensure_ascii=False)}\n"
    
    context_data_2 = context_data.copy()
    context_data_2["history"] = history
    context_data_2["current_plan"] = current_plan
    
    prompt_2 = select_template.render(text=text_2, **context_data_2)
    selection_2 = await _call_vllm(prompt_2)
    
    # 사용자가 직접적인 액션 언급이 없어도 기존 액션(DATA_FETCH)이 유지되거나 재선택되어야 함
    assert "DATA_FETCH" in selection_2["actions"]
    
    # 최종 파라미터 추출 (이전 결과인 result_1을 넘겨서 병합 확인)
    final_result = await _extract_params(
        "DATA_FETCH", 
        text_2, 
        context_data["dynamic_context"], 
        current_action_obj=result_1
    )
    
    print(f"Final Refined Result: {json.dumps(final_result, indent=2, ensure_ascii=False)}")
    assert final_result["action"] == "DATA_FETCH"
    # 모델이 dynamic_context를 참고하여 '인버터 1번'에 해당하는 ID를 추출함 (null이 아니어야 함)
    assert final_result["params"]["device"] is not None
    # 이전 턴에서 추출된 fields 정보가 유지되는지 확인
    assert "power" in final_result["params"]["fields"]

@pytest.mark.asyncio
async def test_base_argument_injection(select_template):
    """기본 인자(projectId, slId) 주입 테스트"""
    text = "다른 화면 보여줘"
    project_id = "project-A"
    sl_id = "SL-999"
    
    # 1. 액션 선택
    context_data = {
        "tools_yaml": action_manager.get_all_schemas_text(),
        "dynamic_context": action_manager.get_dynamic_prompt_context(),
        "history": "",
        "current_plan": "",
        "reference_cases": [],
        "is_fallback": False
    }
    prompt = select_template.render(text=text, **context_data)
    selection = await _call_vllm(prompt)
    
    assert "MOVE_PAGE" in selection["actions"]
    
    # 2. 파라미터 추출 시 기본 인자 주입 상황 모사 (workflow.py의 로직)
    current_action_obj = {
        "projectId": project_id,
        "params": {"slId": sl_id}
    }
    
    full_action = await _extract_params(
        "MOVE_PAGE", 
        text, 
        context_data["dynamic_context"], 
        current_action_obj=current_action_obj
    )
    
    print(f"Injection Result: {json.dumps(full_action, indent=2, ensure_ascii=False)}")
    assert full_action["action"] == "MOVE_PAGE"
    assert full_action["projectId"] == project_id
    assert full_action["params"]["slId"] == sl_id

@pytest.mark.asyncio
async def test_move_page_ambiguous_report(select_template, context_data):
    """보고서 이동 요청 시 모호성 처리 테스트"""
    text = "보고서 화면으로 이동"
    
    # 1. 액션 선택
    prompt_s1 = select_template.render(text=text, **context_data)
    selection = await _call_vllm(prompt_s1)
    
    print(f"Selection Result: {json.dumps(selection, indent=2, ensure_ascii=False)}")
    
    # 2. 파라미터 추출
    full_action = await _extract_params("MOVE_PAGE", text, context_data["dynamic_context"])
    
    print(f"Extracted Action: {json.dumps(full_action, indent=2, ensure_ascii=False)}")
    
    # 문제 재현 확인: url이나 slId가 임의의 값(hallucination)으로 채워지는지 확인
    # '보고서'만으로는 구체적인 url을 알 수 없어야 함
    assert full_action["url"] is None or full_action["url"] == ""

@pytest.mark.asyncio
async def test_device_control_hallucination_and_message(select_template, context_data):
    """장치 제어 시 존재하지 않는 장치(컨버터)에 대한 환각 방지 및 메시지 생성 테스트"""
    text = "컨버터 재시작해줘"
    
    # 1. 액션 선택
    prompt_s1 = select_template.render(text=text, **context_data)
    selection = await _call_vllm(prompt_s1)
    
    # 액션은 선택될 수 있음 (제어 의도는 명확하므로)
    assert "DEVICE_CONTROL" in selection["actions"]
    
    # 2. 파라미터 추출
    full_action = await _extract_params("DEVICE_CONTROL", text, context_data["dynamic_context"])
    
    print(f"Device Control Result: {json.dumps(full_action, indent=2, ensure_ascii=False)}")
    
    # 문제 재현 확인: '컨버터'가 목록에 없으므로 device는 null이어야 함
    # (현재는 inverter_01로 환각이 발생한다고 보고됨)
    assert full_action["params"]["device"] is None or full_action["params"]["device"] not in ["inverter_01", "inverter_02", "inverter_03"]

    # 메시지 생성 확인 (Null 처리 정책 반영)
    assert "message" in full_action["params"]
    assert full_action["params"]["message"] is None

