# 동작(Action) 추가 가이드

본 시스템은 `action-definition` 디렉토리에 정의된 JSON 스키마를 동적으로 로드하여 vLLM 기반 NLU 엔진이 명령을 분석합니다. 새로운 동작을 추가하려면 다음 3단계를 수행하십시오.

## 1단계: JSON 스키마 정의
`action-definition/schemas/` 디렉토리에 새로운 스키마 파일(`{ACTION_NAME}.schema.json`)을 생성합니다.

- **필수 규칙**: 
  - `action` 필드는 상수로 정의되어야 하며, 파일명과 일치하는 것이 좋습니다.
  - `params` 객체 내부에 필요한 파라미터와 타입을 명시합니다.

**예시: `LIGHT_CONTROL.schema.json`**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LIGHT_CONTROL",
  "type": "object",
  "required": ["action", "params"],
  "properties": {
    "action": { "type": "string", "const": "LIGHT_CONTROL" },
    "params": {
      "type": "object",
      "required": ["location", "state"],
      "properties": {
        "location": { "type": "string", "description": "조명 위치 (예: 거실, 안방)" },
        "state": { "type": "string", "enum": ["ON", "OFF"], "description": "조명 상태" }
      }
    }
  }
}
```

## 2단계: 메타데이터 및 레지스트리 업데이트 (선택 사항)
시스템 관리 및 통합 대시보드와의 정합성을 위해 다음 파일들을 업데이트하는 것을 권장합니다.

1.  **메타데이터**: `action-definition/metadata/{ACTION_NAME}.meta.json` 생성 (설명, 버전 등 기록)
2.  **레지스트리**: `action-definition/actions.registry.json`의 `actions` 배열에 새로운 동작 정보를 추가합니다.

## 3단계: 시스템 반영 확인
스키마 파일을 저장하면 백엔드 서버를 재시작할 필요 없이(Hot-load 아님, 호출 시마다 로드) 즉시 NLU 엔진이 해당 동작을 인식할 수 있습니다.

**테스트 예시**:
```bash
curl -X POST "http://localhost:8000/api/mock-command" \
     -H "Content-Type: application/json" \
     -d '{"text": "거실 불 켜줘"}'
```

성공적으로 인식되면 `candidates` 배열에 `LIGHT_CONTROL` 액션이 포함된 JSON이 반환됩니다.
