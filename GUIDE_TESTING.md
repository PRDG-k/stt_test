# NLU Action Testing Guide

이 가이드는 백엔드 NLU(Natural Language Understanding) 로직과 vLLM 서버 간의 연동을 검증하기 위한 테스트 프레임워크 사용법을 설명합니다.

## 개요

NLU 엔진이 사용자의 발화(Korean Speech-to-Text 결과)를 분석하여 정의된 액션 스키마에 맞게 파라미터를 정확히 추출하는지 검증합니다. 특히, 정보가 부족한 상황에서 모델이 어떻게 반응하는지(Ambiguity handling)를 중점적으로 테스트합니다.

## 테스트 구조

테스트는 `tests/test_nlu_actions.py`에 구현되어 있으며, 실제 `ActionManager`와 `vLLM` 클라이언트를 사용하여 통합 테스트 형태로 동작합니다.

### 주요 테스트 케이스

1.  **정확한 요청 (Precise Requests)**:
    - 모든 필수 파라미터가 포함된 발화 시나리오.
    - 예상 결과: 액션명이 일치하고 모든 파라미터가 정확한 값으로 채워짐.
2.  **모호한 요청 (Ambiguous Requests)**:
    - 필수 파라미터가 누락된 발화 시나리오.
    - 예상 결과: 액션명은 선택되나, 누락된 파라미터는 `null`로 반환되어 시스템이 상호작용(질문)을 유도할 수 있게 함.
3.  **메시지/인사 요청 (Simple Actions)**:
    - 파라미터 구조가 단순한 액션(예: `SHOW_MSG`)에 대한 처리 검증.
4.  **상호작용 및 파라미터 구체화 (Multi-turn Interaction)**:
    - 1차 요청에서 누락된 정보를 2차 답변을 통해 보충하는 시나리오.
    - 예상 결과: 이전 대화 맥락과 추출된 파라미터가 유지되면서, 새로운 정보가 기존 액션 객체에 정확히 병합됨.
5.  **기본 인자 주입 (Base Argument Injection)**:
    - API 호출 시 `projectId`, `slId` 등을 기본 인자로 전달하는 시나리오.
    - 예상 결과: 사용자가 직접 언급하지 않더라도, 전달된 기본 인자가 액션 파라미터의 초기값으로 활용됨.
6.  **환각 방지 및 메시지 생성 (Zero Hallucination & Message Generation)**:
    - 존재하지 않는 장치명(예: '컨버터')을 포함한 제어 명령 시나리오.
    - 예상 결과: 모델이 임의로 유사한 장치를 선택하지 않고 `null`을 반환(환각 방지)하며, 사용자에게 보여줄 안내 문구(`message`)를 직접 생성함.

## 실행 방법

의존성 패키지가 모두 설치된 Docker 컨테이너 내부에서 실행하는 것을 권장합니다.

```bash
# Docker 컨테이너 내에서 전체 테스트 실행
docker exec stt-action-engine pytest tests/test_nlu_actions.py -s

# 특정 테스트 케이스만 실행 (예: 모호성 테스트)
docker exec stt-action-engine pytest tests/test_nlu_actions.py -k "test_data_fetch_ambiguous" -s
```

## 참고 사항

- **vLLM 연동**: 테스트 실행 시 실제 vLLM 서버(설정된 `VLLM_MODEL_NAME`)에 요청을 보냅니다. 서버 연결 상태를 확인하세요.
- **스키마 동기화**: `action-definition/schemas/` 폴더의 JSON 스키마를 실시간으로 참조하여 프롬프트를 구성합니다.
- **동적 컨텍스트**: 현재 시각(KST), 허용된 페이지 리스트, 제어 가능한 장치 리스트 등이 프롬프트에 자동으로 주입되어 테스트됩니다.
