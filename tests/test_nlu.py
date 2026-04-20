import pytest
from unittest.mock import patch, MagicMock
from app.services.nlu import parse_intent

@pytest.mark.asyncio
async def test_parse_intent_success():
    # vLLM 클라이언트 응답 모킹
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"message": "동작 수행", "candidates": [{"action": "DEVICE_CONTROL", "params": {"device": "1", "command": "START"}}], "requires_confirmation": false}'))
    ]
    
    with patch('app.services.nlu.vllm_client.chat.completions.create', return_value=mock_response):
        res = await parse_intent("장치 가동해줘")
        
        assert res.transcript == "장치 가동해줘"
        assert len(res.candidates) == 1
        assert res.candidates[0]["action"] == "DEVICE_CONTROL"
        assert res.requires_confirmation is False

@pytest.mark.asyncio
async def test_parse_intent_error_handling():
    # 잘못된 JSON 응답 발생 시의 처리 검증
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='Invalid JSON string'))
    ]
    
    with patch('app.services.nlu.vllm_client.chat.completions.create', return_value=mock_response):
        res = await parse_intent("에러 유도")
        
        assert "명령을 이해하지 못했습니다" in res.message
        assert len(res.candidates) == 0
