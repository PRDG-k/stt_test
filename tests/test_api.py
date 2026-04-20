import pytest
import json
from unittest.mock import patch, MagicMock

def test_mock_command_unauthorized(client):
    # API 키가 없을 때 401 에러 확인
    response = client.post("/api/mock-command", json={"text": "재부팅"})
    assert response.status_code == 401
    assert response.json()["detail"] == "API Key missing"

def test_mock_command_admin_success(client):
    # ADMIN 키로 제어 명령 성공 확인
    mock_nlu_res = {
        "message": "재부팅합니다.",
        "candidates": [{"action": "DEVICE_CONTROL", "params": {"device": "1", "command": "REBOOT"}}],
        "requires_confirmation": False
    }
    
    with patch('app.services.nlu.vllm_client.chat.completions.create') as mock_vllm:
        mock_vllm.return_value.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_nlu_res)))]
        
        headers = {"X-API-Key": "admin-key-123"}
        response = client.post("/api/mock-command", json={"text": "1번 재부팅"}, headers=headers)
        
        assert response.status_code == 200
        assert response.json()["candidates"][0]["action"] == "DEVICE_CONTROL"

def test_mock_command_viewer_rbac_denied(client):
    # VIEWER 키로 제어 명령 시도 시 RBAC 차단 확인
    mock_nlu_res = {
        "message": "재부팅합니다.",
        "candidates": [{"action": "DEVICE_CONTROL", "params": {"device": "1", "command": "REBOOT"}}],
        "requires_confirmation": False
    }
    
    with patch('app.services.nlu.vllm_client.chat.completions.create') as mock_vllm:
        mock_vllm.return_value.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_nlu_res)))]
        
        headers = {"X-API-Key": "viewer-key-789"}
        response = client.post("/api/mock-command", json={"text": "1번 재부팅"}, headers=headers)
        
        assert response.status_code == 200
        # RBAC에 의해 candidates가 비워지고 에러 메시지가 포함되어야 함
        assert len(response.json()["candidates"]) == 0
        assert "권한 오류" in response.json()["message"]
