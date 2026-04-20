import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from app.services.stt import transcribe_audio
from app.services.nlu import parse_intent
from app.models.schemas import STTResponse, ActionIntent, CommandRequest, NLUResponse
from app.models.database import log_action, get_session_history, log_conversation
from app.core.security import get_current_user_role
from app.core.config import settings

router = APIRouter()

def check_rbac(role: str, response: NLUResponse) -> NLUResponse:
    """
    NLU 결과의 candidates 중 현재 역할(Role)이 수행할 수 없는 액션이 포함되어 있는지 검사합니다.
    """
    allowed_actions = settings.ROLE_PERMISSIONS.get(role, [])
    filtered_candidates = []
    
    for candidate in response.candidates:
        action_name = candidate.get("action")
        if action_name in allowed_actions:
            filtered_candidates.append(candidate)
        else:
            print(f"[RBAC WARNING] Role '{role}' attempted unauthorized action: {action_name}")
    
    if response.candidates and not filtered_candidates:
        response.message = f"권한 오류: 사용자의 권한({role})으로는 요청하신 작업을 수행할 수 없습니다."
        response.candidates = []
    else:
        response.candidates = filtered_candidates
        
    return response

@router.post("/intent", response_model=NLUResponse)
async def process_intent_endpoint(
    data: CommandRequest, 
    role: str = Depends(get_current_user_role)
):
    sid = data.session_id or "default"
    try:
        # 1. DB에서 세션 히스토리 가져오기
        history = get_session_history(sid)
        
        # 2. 사용자 입력 로깅
        log_conversation(sid, "user", data.text)
        
        # 3. NLU 분석
        response = await parse_intent(data.text, history)
        response.session_id = sid
        
        # 4. RBAC 검사
        response = check_rbac(role, response)
        
        # 5. 어시스턴트 응답 로깅
        log_conversation(sid, "assistant", response.message)
        
        # 6. 액션 시도 로깅
        log_action(sid, data.text, response.model_dump())
        
        return response
    except Exception as e:
        return NLUResponse(
            transcript=data.text,
            message=f"오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id=sid
        )

@router.post("/upload-audio", response_model=NLUResponse)
async def process_audio(
    file: UploadFile = File(...), 
    role: str = Depends(get_current_user_role)
):
    file_location = f"temp_{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
    
    sid = "audio_session"
    try:
        transcript = await transcribe_audio(file_location)
        
        if transcript.startswith("["):
            return NLUResponse(
                transcript=transcript,
                message=transcript,
                candidates=[],
                requires_confirmation=False,
                session_id=sid
            )

        response = await parse_intent(transcript)
        response.session_id = sid
        
        # RBAC 검사
        response = check_rbac(role, response)
        
        log_action(sid, transcript, response.model_dump())
        
        return response
        
    except Exception as e:
        return NLUResponse(
            transcript="[처리 오류]",
            message=f"오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id=sid
        )
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

@router.post("/mock-command", response_model=NLUResponse)
async def mock_command(
    data: CommandRequest, 
    role: str = Depends(get_current_user_role)
):
    sid = data.session_id or "mock_session"
    try:
        response = await parse_intent(data.text)
        response.session_id = sid
        
        # RBAC 검사
        response = check_rbac(role, response)
        
        log_action(sid, data.text, response.model_dump())
        return response
    except Exception as e:
        return NLUResponse(
            transcript=data.text,
            message=f"오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id=sid
        )
