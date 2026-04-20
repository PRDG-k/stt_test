# 통합 대시보드 API 연동 가이드

본 문서는 통합 대시보드 서버에서 음성 제어 엔진(STT-NLU)을 호출하고, 반환된 제어 명령을 파싱하여 실제 장비나 화면을 제어하는 방법을 설명합니다.

## 1. 인증 (Authentication)

모든 API 요청은 HTTP 헤더에 `X-API-Key`를 포함해야 합니다. 권한별 사용 가능한 키는 다음과 같습니다 (설정 파일에서 변경 가능).

| 역할 (Role) | API Key (예시) | 허용 액션 |
| :--- | :--- | :--- |
| **ADMIN** | `admin-key-123` | 모든 액션 (제어, 조회, 다운로드 등) |
| **OPERATOR** | `operator-key-456` | 장치 제어 및 데이터 조회 |
| **VIEWER** | `viewer-key-789` | 데이터 조회 및 메시지 표시 전용 |

---

## 2. 주요 API 엔드포인트

### 2.1 텍스트 명령 분석 (`/api/intent`)
이미 텍스트로 변환된 명령이나 챗봇 형태의 입력을 처리할 때 사용합니다.

- **URL**: `POST /api/intent`
- **Payload**:
  ```json
  {
    "text": "1번 장비 가동해줘",
    "session_id": "user_session_001"
  }
  ```

### 2.2 음성 파일 분석 (`/api/upload-audio`)
마이크로 녹음된 오디오 파일(.m4a, .wav 등)을 직접 업로드하여 분석할 때 사용합니다.

- **URL**: `POST /api/upload-audio`
- **Content-Type**: `multipart/form-data`
- **Body**: `file` (Binary)

---

## 3. 응답 구조 및 파싱 방법

모든 정상 응답은 `NLUResponse` 형태의 JSON 객체입니다.

### 응답 객체 (JSON)
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
  "session_id": "user_session_001"
}
```

### 파싱 로직 가이드
1.  **`candidates` 배열 확인**: 
    - 배열이 비어있다면, 엔진이 의도를 파악하지 못했거나 권한이 없는 경우입니다. `message`를 사용자에게 노출하십시오.
2.  **`action` 필드 분기**:
    - `candidates[0].action` 값을 읽어 어떤 동작인지 파악합니다. (예: `DEVICE_CONTROL`, `DATA_FETCH` 등)
3.  **스키마 기반 처리**:
    - 각 액션에 따른 세부 데이터는 `params` 또는 추가 필드에 들어있습니다. 이 구조는 `action-definition/schemas/`에 정의된 JSON 스키마를 따릅니다.
4.  **확인 필요 여부 (`requires_confirmation`)**:
    - `true`인 경우, 즉시 실행하지 말고 사용자에게 "정말 수행할까요?"와 같은 UI 팝업을 띄우는 것을 권장합니다.

---

## 4. 호출 예시 (Python / JavaScript)

### Python (requests 사용)
```python
import requests

url = "http://engine-server:8000/api/intent"
headers = {"X-API-Key": "admin-key-123"}
data = {"text": "실시간 전압 보여줘"}

response = requests.post(url, json=data, headers=headers)
result = response.json()

if result["candidates"]:
    action = result["candidates"][0]
    if action["action"] == "DATA_FETCH":
        print(f"조회 대상: {action['params']['fields']}")
```

### JavaScript (Fetch API 사용)
```javascript
const response = await fetch('http://engine-server:8000/api/intent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'admin-key-123'
  },
  body: JSON.stringify({ text: '1번 장비 재부팅' })
});

const data = await response.json();
if (data.candidates.length > 0) {
  // 대시보드 제어 로직 실행
  executeAction(data.candidates[0]);
} else {
  alert(data.message); // 권한 부족 또는 인식 불가 메시지
}
```
