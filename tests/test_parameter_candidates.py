import pytest
import asyncio
import json
from app.services.workflow import create_nlu_graph, AgentState
from app.services.action_manager import action_manager
from langchain_core.messages import HumanMessage, AIMessage

@pytest.mark.asyncio
async def test_parameter_candidates_generation():
    """파라미터 누락 시 후보군 생성 및 메시지 포함 여부 테스트"""
    graph = create_nlu_graph().compile()
    
    # '장비 제어해줘' (어떤 장치인지 모름)
    initial_state = {
        "text": "장비 꺼줘",
        "session_id": "test_candidates",
        "messages": [],
        "selected_actions": [],
        "candidates": [],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(initial_state)
    
    print(f"Final Message with Candidates: {result['final_message']}")
    
    # 1. candidates 리스트에 정보가 포함되어야 함
    assert len(result["candidates"]) > 0
    # 액션 확장이 일어났으므로 전체 후보들 중 inverter_01이 포함되어 있는지 확인
    assert "inverter_01" in str(result["candidates"])
    
    # 2. final_message에 정적 메시지 접두사가 포함되어야 함
    assert "명령을 실행하기 위해 부족한 정보가 있습니다." in result["final_message"]
    assert "1." in result["final_message"]
    assert "inverter_01" in result["final_message"]

@pytest.mark.asyncio
async def test_numbered_choice_selection():
    """번호 선택 시 실제 파라미터로 매핑되는지 테스트 (2-Turn)"""
    graph = create_nlu_graph().compile()
    
    # Turn 1에서 이미 후보군이 제시된 상황을 가정하여 Turn 2 수행
    # 이전 AI 메시지: "어떤 장치를 끄시겠습니까? 1. inverter_01, 2. inverter_02 ..."
    prev_ai_msg = "명령을 실행하기 위해 부족한 정보가 있습니다. device 정보를 알려주세요.\n- device 선택지: 1. inverter_01, 2. inverter_02, 3. inverter_03, 4. pump_main"
    
    # 사용자가 "1번"이라고 대답
    state = {
        "text": "1번",
        "session_id": "test_numbered_choice",
        "messages": [
            HumanMessage(content="장비 꺼줘"),
            AIMessage(content=prev_ai_msg)
        ],
        "selected_actions": ["DEVICE_CONTROL"],
        "candidates": [{
            "action": "DEVICE_CONTROL",
            "requires_confirmation": True,
            "params": {"device": None, "command": "STOP"}
        }],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(state)
    
    print(f"Final Candidate: {json.dumps(result['candidates'], indent=2, ensure_ascii=False)}")
    
    # 1번 선택지가 inverter_01로 정확히 매핑되어야 함
    assert len(result["candidates"]) > 0
    final_action = result["candidates"][0]
    assert final_action["params"]["device"] == "inverter_01"
    assert final_action["requires_confirmation"] is False
    
    # 메시지에 '인버터', '끄', '정지', '종료' 중 하나라도 포함되어 있는지 확인 (유연한 검증)
    msg = result["final_message"]
    assert any(keyword in msg for keyword in ["인버터", "inverter", "끄", "정지", "종료", "멈춤"])
