# STT-NLU Dashboard Action Engine

본 프로젝트는 음성 명령을 분석하여 통합 대시보드 서버를 제어하기 위한 백엔드 전용 NLU(자연어 이해) 엔진입니다.

## 주요 기능
- **STT (Speech-To-Text)**: 음성 파일을 텍스트로 변환 (Google Web Speech API).
- **NLU (Natural Language Understanding)**: `vLLM` 기반 의도 분석 및 제어 명령 생성.
- **Dynamic Schema Loading**: `action-definition`의 JSON 스키마를 동적으로 로드하여 분석 프롬프트에 자동 반영.
- **Backend Only**: 프론트엔드 UI 없이 순수 JSON API로 동작하며 통합 대시보드와의 연동에 최적화.

## 디렉토리 구조
- `app/`: FastAPI 기반 백엔드 소스 코드.
- `action-definition/`: 동작(Action)의 정의(스키마, 메타데이터)를 담는 저장소.
- `voicefile/`: 음성 녹음 샘플 데이터.

## 새로운 동작 추가 방법
새로운 제어 명령이나 데이터 조회 동작을 추가하려면 [동작 추가 가이드](GUIDE_ADD_ACTION.md)를 참고하십시오.

## API 엔드포인트
- `POST /api/upload-audio`: 음성 파일 업로드 및 분석.
- `POST /api/intent`: 텍스트 명령 분석 및 히스토리 기반 대화 처리.
- `POST /api/mock-command`: 단순 텍스트 기반 명령 테스트.

## 시작하기

### 로컬 실행
```bash
uv run python -m app.main
```
(HTTPS 모드 필요 시 `--https` 옵션 사용)

### Docker 실행
1. `key.env` 파일에 필요한 API Key 및 설정을 완료합니다.
2. Docker Compose를 사용하여 서비스를 빌드하고 실행합니다.
```bash
docker compose up --build -d
```
3. 서비스가 정상적으로 실행되면 `http://localhost:8000`에서 API를 이용할 수 있습니다.