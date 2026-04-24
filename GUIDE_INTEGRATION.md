# 통합 대시보드 API 연동 가이드 (프론트 STT 대응 버전)

본 문서는 통합 대시보드 서버 또는 프론트엔드 앱에서 음성 인식 결과를 바탕으로 제어 명령을 분석하고 처리하는 방법을 설명합니다. 

> **참고**: 본 서버는 분석 및 제어 명령 생성 전용입니다. 인증(Authentication) 및 역할 기반 접근 제어(RBAC)는 통합 백엔드 서버에서 처리하므로, 본 API 호출 전 메인 시스템의 인증 절차를 따르십시오.

## 1. 연동 아키텍처 개요

프론트엔드에서 음성을 텍스트로 변환(STT)한 후, 해당 텍스트를 백엔드의 **NLU 분석 엔드포인트**로 전달하여 제어 명령 JSON을 받아가는 구조입니다.

```text
[Frontend] --(Voice)--> [STT 엔진] --(Text)--> [Backend API] --(Action JSON)--> [Frontend/Dashboard]
```

---

## 2. 주요 API 엔드포인트

### 2.1 [권장] 텍스트 명령 분석 (`POST /api/intent`)
프론트엔드에서 인식된 음성 텍스트를 분석하여 구조화된 액션 객체를 반환합니다.

- **Payload**:
  ```json
  {
    "text": "1번 장비 가동해줘",
    "session_id": "optional_session_uuid"
  }
  ```

### 2.2 음성 파일 직접 업로드 (`POST /api/upload-audio`)
백엔드의 STT 기능을 이용해야 하는 경우 오디오 파일을 직접 전송할 수 있습니다. 

- **Content-Type**: `multipart/form-data`
- **Body**: `file` (Binary)

### 2.3 피드백 및 결과 학습 (`POST /api/feedback`)
분석 결과가 정확했는지 피드백을 보내 엔진의 정확도를 실시간으로 향상시킵니다. 

- **Payload**:
  ```json
  {
    "log_id": 123,
    "is_correct": true,
    "corrected_intent": null
  }
  ```

---

## 3. 응답 파싱 및 제어 구현 가이드

백엔드는 `action-definition`에 정의된 스키마에 따라 검증된 액션만 반환합니다.

### 응답 예시 (DEVICE_CONTROL)
```json
{
  "transcript": "1번 장비 가동해줘",
  "message": "1번 장비를 가동합니다.",
  "candidates": [
    {
      "action": "DEVICE_CONTROL",
      "params": {
        "device": "1",
        "command": "START",
        "message": "가동 명령 전달"
      }
    }
  ],
  "requires_confirmation": false,
  "session_id": "default",
  "log_id": 123
}
```

### 처리 로직 핵심
1.  **`candidates` 유무 확인**: 배열이 비어있다면 권한이 없거나 분석에 실패한 것입니다. `message` 필드의 내용을 사용자에게 노출하십시오.
2.  **`action` 분기 처리**: `candidates[0].action` 값(`MOVE_PAGE`, `DEVICE_CONTROL` 등)을 기준으로 대시보드 내부 제어 로직을 실행합니다.
3.  **`requires_confirmation` 확인**: 이 값이 `true`인 경우, 사용자에게 확인 팝업을 띄운 후 승인을 얻었을 때 실제 제어를 실행하는 것을 권장합니다.
4.  **학습(Feedback) 수행**: 제어가 성공적으로 승인/실행되면 `/api/feedback`을 호출하여 `is_correct: true`를 보내십시오. 향후 유사한 명령에 대한 분석 정확도가 향상됩니다.
