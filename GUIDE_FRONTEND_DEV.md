# 프론트엔드 개발자 가이드: 음성 제어 시스템 연동

본 문서는 프론트엔드 앱에서 음성 인식을 처리하고, 백엔드 NLU(자연어 이해) 엔진과 연동하여 통합 대시보드를 제어하는 상세 명세를 제공합니다. 

> **참고**: 본 서버는 분석 및 제어 명령 생성 전용이며, 인증(Authentication) 정책은 통합 백엔드 시스템의 방침을 따릅니다.

---

## 1. 시스템 워크플로우 (2단계 분석 아키텍처)

엔진은 정확도와 유연성을 위해 두 단계로 나누어 의도를 분석합니다.

1.  **Stage 1: 순수 텍스트 분석 (Strict Mode)**
    - 입력된 텍스트만으로 즉시 동작 스키마를 도출합니다.
    - 명령이 명확한 경우 즉시 실행 가능한 액션이 반환됩니다.
2.  **Stage 2: 피드백 기반 추천 (Fallback Mode)**
    - 1단계 분석 실패 시, DB에 축적된 **과거 성공 사례** 중 유사한 패턴을 검색합니다.
    - 과거 사례를 참고하여 가능성 높은 후보(`candidates`)를 생성하며, 이 경우 사용자에게 선택지를 제공해야 합니다.

---

## 2. API 상세 명세

### 2.1 의도 분석 요청 (`POST /api/intent`)

프론트엔드에서 인식된 텍스트를 분석하여 구조화된 명령을 가져옵니다.

- **Payload**:
  ```json
  {
    "text": "1번 장비 재부팅해줘",
    "session_id": "uuid-v4-session-id"
  }
  ```
- **Response (NLUResponse)**:
  - **단일 액션 반환 (Stage 1 성공)**: `candidates` 배열에 1개의 객체가 포함됩니다.
  - **다중 후보 추천 (Stage 2 Fallback)**: `candidates` 배열에 2~3개의 추천 후보가 포함되며, `requires_confirmation`이 항상 `true`입니다.

### 2.2 피드백 전송 (`POST /api/feedback`)

분석된 결과가 맞는지, 혹은 틀려서 수정했는지를 엔진에 전달합니다. **성능 향상의 핵심입니다.**

- **Payload**:
  ```json
  {
    "log_id": 42,
    "is_correct": true,
    "corrected_intent": null
  }
  ```
  - `is_correct`: 사용자가 결과를 승인(실행)했다면 `true`.
  - `corrected_intent`: (선택) 분석 결과가 틀려 사용자가 직접 수정했다면 수정한 `candidates` 배열 구조를 포함.

---

## 3. 프론트엔드 구현 가이드 (JavaScript 예시)

### 3.1 분석 결과 처리 및 UI 대응
```javascript
async function processVoiceCommand(recognizedText) {
  const response = await fetch('/api/intent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: recognizedText, session_id: currentSessionId })
  });

  const data = await response.json();

  // 1. 분석 실패 처리
  if (data.candidates.length === 0) {
    showToast(data.message);
    return;
  }

  // 2. [중요] 다중 후보 추천 처리 (Fallback Mode)
  // 입력이 모호하여 과거 사례를 기반으로 후보군이 생성된 경우입니다.
  if (data.candidates.length > 1) {
    // 사용자에게 후보 리스트를 보여주고 하나를 선택하게 합니다.
    const selectedAction = await showSelectionUI(data.message, data.candidates);
    if (!selectedAction) return;

    // 선택된 액션 실행 및 학습 데이터 전송
    if (executeDashboardAction(selectedAction)) {
      sendFeedback(data.log_id, true); 
    }
    return;
  }

  // 3. 단일 액션 처리
  const action = data.candidates[0];

  // 사용자 확인 절차 (requires_confirmation이 true인 경우)
  if (data.requires_confirmation) {
    const confirmed = await showConfirmModal(data.message);
    if (!confirmed) return;
  }

  // 실제 대시보드 제어 실행 및 결과 피드백
  if (executeDashboardAction(action)) {
    sendFeedback(data.log_id, true); // 성공 시 엔진 학습을 위해 호출
  }
}
```

### 3.2 피드백 전송 (엔진 학습 루프)
분석 결과가 정확했는지 피드백을 보내면 엔진이 해당 용어나 명령 습관을 학습하여 다음에 더 정확한 추천을 제공합니다.

- **성공(승인/실행)** 시: `is_correct: true` 전송.
- **실패(수정)** 시: `is_correct: false`와 함께 사용자가 선택한 정답 `corrected_intent` 전송.

```javascript
function sendFeedback(logId, isCorrect, correction = null) {
  fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      log_id: logId,
      is_correct: isCorrect,
      corrected_intent: correction
    })
  });
}
```

---

## 4. 에러 처리 전략

| 상황 | 처리 방법 |
| :--- | :--- |
| **분석 결과 없음** | NLU가 의도를 파악하지 못한 경우입니다. `data.message`를 사용자에게 안내하십시오. |
| **STT 인식 실패** | 음성 인식 품질이 낮은 경우입니다. 사용자에게 "다시 말씀해 주세요"라고 시각적/청각적 피드백을 제공하십시오. |
| **네트워크 오류** | 서버 연결 상태를 확인하고 사용자에게 재시도를 권장하십시오. |
