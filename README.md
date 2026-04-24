# STT-NLU Dashboard Action Engine

본 프로젝트는 음성 명령을 분석하여 통합 대시보드 서버를 제어하기 위한 NLU(자연어 이해) 엔진입니다.

## 주요 기능
- **NLU (Natural Language Understanding)**: `vLLM` 기반 의도 분석 및 제어 명령 생성.
- **Dynamic Schema Loading**: `action-definition`의 JSON 스키마를 동적으로 로드 및 검증.
- **Case-Based Refinement**: 사용자 피드백을 기반으로 실시간 정확도 향상.
- **Backend Only**: 분석 및 제어 명령 생성에 최적화된 API 서버.

## 시작하기

### 로컬 실행
```bash
uv run python -m app.main
```

### Docker 실행
1. `key.env` 파일에 필요한 API Key(OpenAI/Groq 등)를 설정합니다.
2. 서비스를 빌드하고 실행합니다.
```bash
./build.sh
docker compose up -d
```

## 문서
- [프론트엔드 연동 가이드](GUIDE_FRONTEND_DEV.md): API 호출 및 제어 로직 구현 방법.
- [동작 추가 가이드](GUIDE_ADD_ACTION.md): 새로운 제어 스키마를 추가하는 방법.