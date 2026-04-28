import pytest
import asyncio
from app.services.workflow import create_nlu_graph, AgentState
from app.services.nlu_core import _validate_message
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_message_validation_logic():
    """메시지 검수 로직 단독 테스트 (inverter_01 환각 제거 확인)"""
    text = "컨버터 제어해줘"
    hallucinated_message = "어떤 컨버터(장치 ID)를 어떻게 제어하시겠습니까? (예: inverter_01을 멈추기)"
    
    validated_message = await _validate_message(text, hallucinated_message, candidates=[])
    
    print(f"Original: {hallucinated_message}")
    print(f"Validated: {validated_message}")
    
    # 'inverter_01'이라는 구체적이고 사용자 발화(컨버터)와 일치하지 않는 예시가 제거되었는지 확인
    assert "inverter_01" not in validated_message
    assert "컨버터" in validated_message

@pytest.mark.asyncio
async def test_message_consistency_validation():
    """메시지와 파라미터 간의 불일치(환각) 교정 테스트"""
    text = "2번"
    # LLM이 이전 맥락(inverter_01)에 갇혀서 잘못된 질문을 던진 상황 가정
    wrong_message = "현재 'inverter_01' 장치를 끄는 작업을 진행 중입니다. '2번'이 어떤 장치를 의미하시나요?"
    # 실제 추출된 파라미터는 inverter_02인 상황
    candidates = [{
        "action": "DEVICE_CONTROL",
        "requires_confirmation": True,
        "params": {
            "device": "inverter_02",
            "command": "STOP"
        }
    }]
    
    validated_message = await _validate_message(text, wrong_message, candidates)
    
    print(f"Wrong Message: {wrong_message}")
    print(f"Validated Message: {validated_message}")
    
    # 잘못된 장치 ID인 'inverter_01'이 제거되거나 'inverter_02'로 교정되어야 함
    assert "inverter_01" not in validated_message

@pytest.mark.asyncio
async def test_workflow_with_validation_node():
    """전체 워크플로우에서 검수 노드가 작동하는지 통합 테스트"""
    graph = create_nlu_graph().compile()
    
    # '컨버터'를 언급했을 때 환각이 발생할 가능성이 높은 시나리오
    initial_state = {
        "text": "컨버터 꺼줘",
        "session_id": "test_session",
        "messages": [],
        "selected_actions": [],
        "candidates": [],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    # 런타임에 vLLM을 실제로 호출하므로 결과는 가변적일 수 있으나, 
    # 검수 노드가 추가된 그래프가 정상적으로 끝까지 실행되는지 확인
    result = await graph.ainvoke(initial_state)
    
    print(f"Final Message: {result['final_message']}")
    
    assert "final_message" in result
    assert len(result["final_message"]) > 0
    # 최종 메시지에 사용자가 요청한 '컨버터' 맥락이 유지되면서 엉뚱한 'inverter_01' 예시가 없어야 함
    assert "inverter_01" not in result["final_message"]
