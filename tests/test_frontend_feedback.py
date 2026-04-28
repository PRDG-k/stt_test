import pytest
import asyncio
import json
from app.services.workflow import create_nlu_graph
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_bypass_action_selection():
    """프론트엔드에서 전달된 불완전한 후보군으로 인해 Action Selection이 생략되는지 테스트"""
    graph = create_nlu_graph().compile()
    
    # 프론트가 넘겨준 선택지 (사용자가 "2번"을 눌러 DEVICE_CONTROL의 inverter_02를 골랐으나, command가 모호한 상태라고 가정)
    selected_candidate = {
        "action": "DEVICE_CONTROL",
        "requires_confirmation": True,
        "params": {
            "device": "inverter_02",
            "command": None
        }
    }
    
    # 'text'에는 사용자가 방금 말한 보충 정보가 들어옴
    initial_state = {
        "text": "정지해",
        "session_id": "test_bypass",
        "messages": [HumanMessage(content="정지해")],
        "selected_actions": ["DEVICE_CONTROL"],
        "candidates": [selected_candidate],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(initial_state)
    
    # 결과 검증
    # 1. DEVICE_CONTROL 액션이 유지되어야 함
    assert "DEVICE_CONTROL" in result["selected_actions"]
    
    # 2. candidates의 첫 번째 액션 파라미터가 모두 채워져 확정 상태가 되어야 함 (inverter_02, STOP)
    assert len(result["candidates"]) > 0
    action = result["candidates"][0]
    assert action["params"]["device"] == "inverter_02"
    assert action["params"]["command"] == "STOP"
    assert action["requires_confirmation"] is False

@pytest.mark.asyncio
async def test_move_page_structure():
    """MOVE_PAGE 확장이 발생할 때 url이 root에 남고 params에 섞여 들어가지 않는 구조적 테스트"""
    graph = create_nlu_graph().compile()
    
    initial_state = {
        "text": "보고서",
        "session_id": "test_move_page_structure",
        "messages": [HumanMessage(content="보고서")],
        "selected_actions": ["MOVE_PAGE"],
        "candidates": [{
            "action": "MOVE_PAGE",
            "requires_confirmation": True,
            "url": None,
            "params": {"slId": "SL-01"} # slId는 프론트가 인자로 넣어줬다고 가정
        }],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(initial_state)
    
    print(json.dumps(result["candidates"], indent=2, ensure_ascii=False))
    
    # 확장된 후보 중 하나 확인
    assert len(result["candidates"]) >= 1
    
    # FILE_DOWNLOAD 등 다른 액션이 먼저 올 수 있으므로 MOVE_PAGE 액션만 필터링
    move_page_actions = [c for c in result["candidates"] if c["action"] == "MOVE_PAGE"]
    assert len(move_page_actions) > 0
    action = move_page_actions[0]
    
    # url은 루트에 위치해야 함
    assert "url" in action
    assert action["url"] is not None
    
    # params 안에는 slId가 유지되어야 하며, url은 없어야 함
    assert "params" in action
    assert "slId" in action["params"]
    assert action["params"]["slId"] == "SL-01" # 프론트가 넘긴 값이 오염되지 않아야 함
    assert "url" not in action["params"] # url이 params로 밀려들어가는 버그가 없어야 함
