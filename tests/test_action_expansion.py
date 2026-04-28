import pytest
import asyncio
import json
from app.services.workflow import create_nlu_graph, AgentState
from app.services.action_manager import action_manager

@pytest.mark.asyncio
async def test_move_page_expansion():
    """페이지 이동 요청 시 키워드 기반 필터링 및 후보 확장 테스트"""
    graph = create_nlu_graph().compile()
    
    # '보고서 페이지로 가고 싶어' -> notice-report.html, tax-report.html 두 개가 확장되어야 함
    initial_state = {
        "text": "보고서 페이지 보여줘",
        "session_id": "test_expansion",
        "messages": [],
        "selected_actions": [],
        "candidates": [],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(initial_state)
    
    print(f"Final Message: {result['final_message']}")
    print(f"Candidates Count: {len(result['candidates'])}")
    
    # URL 목록 추출 (params 내부 또는 루트 레벨)
    urls = []
    for c in result["candidates"]:
        u = c.get("url") or c.get("params", {}).get("url")
        if u: urls.append(u)

    # 1. '보고서' 키워드가 포함된 페이지들이 확장되었는지 확인
    assert len(result["candidates"]) >= 2
    assert any("notice-report.html" in url for url in urls)
    assert any("tax-report.html" in url for url in urls)

@pytest.mark.asyncio
async def test_date_parsing_and_message_nullification():
    """날짜 포맷 YYYY-MM-DD 변환 확인 및 message null 처리 확인"""
    graph = create_nlu_graph().compile()
    
    # '이번 달 세금 보고서 엑셀' -> start, end 파라미터 확인, message null 확인
    initial_state = {
        "text": "이번 달 세금 보고서 엑셀",
        "session_id": "test_date_parsing",
        "messages": [],
        "selected_actions": [],
        "candidates": [],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(initial_state)
    
    candidates = result["candidates"]
    assert len(candidates) > 0
    action = candidates[0]
    
    assert action["action"] == "FILE_DOWNLOAD"
    assert action["fileType"] == "xlsx"
    assert action["params"]["reportName"] == "tax" or "tax" in action["params"].get("reportName", "").lower() or "세금" in action["params"].get("reportName", "")
    
    # YYYY-MM-DD format check
    import re
    assert re.match(r"\d{4}-\d{2}-\d{2}", action["params"]["start"])
    assert re.match(r"\d{4}-\d{2}-\d{2}", action["params"]["end"])
    
    # Message should be None or not present, depending on schema, but if present it shouldn't be a string
    if "message" in action.get("params", {}):
        assert action["params"]["message"] is None

@pytest.mark.asyncio
async def test_device_control_filtered_expansion():
    """장치 제어 요청 시 필터링 기반 후보 확장 테스트"""
    graph = create_nlu_graph().compile()
    
    # '인버터 제어' -> 어떤 인버터인지 모르므로 inverter_01, 02, 03 세 개가 확장되어야 함
    initial_state = {
        "text": "인버터 제어",
        "session_id": "test_device_expansion",
        "messages": [],
        "selected_actions": [],
        "candidates": [],
        "final_message": "",
        "is_fallback": False,
        "project_id": None,
        "sl_id": None
    }
    
    result = await graph.ainvoke(initial_state)
    
    devices = []
    for c in result["candidates"]:
        d = c.get("params", {}).get("device")
        if d: devices.append(d)
        
    print(f"Expanded Devices: {devices}")
    
    # 'inverter'가 포함된 3개 장치가 후보로 나와야 함 (필터링 검증)
    assert len([d for d in devices if "inverter" in d]) >= 3
    # 'pump'는 필터링되어 없어야 함
    assert not any("pump" in d for d in devices)
