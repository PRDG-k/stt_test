import os
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Form
from app.services.stt import transcribe_audio
from app.services.nlu import parse_intent
from app.models.schemas import STTResponse, ActionIntent, CommandRequest, NLUResponse, FeedbackRequest
from app.models.database import log_action, get_session_history, log_conversation, update_action_feedback
from app.core.config import settings
from app.services.action_manager import action_manager

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/actions")
async def get_available_actions():
    """
    현재 시스템에 등록된 모든 액션 레지스트리 정보를 반환합니다.
    """
    registry = action_manager.get_registry()
    return registry

@router.post("/intent", response_model=NLUResponse)
async def process_intent_endpoint(
    data: CommandRequest
):
    session_id = data.session_id or "tmp_session"
    logger.info(f"[Session ID: {session_id}] Processing text intent: {data.text} (Project: {data.projectId}, SL: {data.slId})")
    try:
        # 1. DB에서 세션 히스토리 가져오기
        # history = get_session_history(session_id)

        # 2. 사용자 입력 로깅
        log_conversation(session_id, "user", data.text)
        
        # 3. NLU 분석 (LangGraph 체크포인터가 히스토리를 자동 관리함)
        response = await parse_intent(
            text=data.text, 
            session_id=session_id, 
            project_id=data.projectId, 
            sl_id=data.slId,
            selected_candidate=data.selected_candidate
        )
        response.session_id = session_id
        
        # 4. 어시스턴트 응답 로깅
        log_conversation(session_id, "assistant", response.message)
        
        # 5. 액션 시도 로깅 및 log_id 획득
        log_entry = log_action(session_id, data.text, response.model_dump())
        response.log_id = log_entry.id
        
        logger.info(f"[Session ID: {session_id}] Successfully processed intent. Log ID: {response.log_id}")
        return response
    except Exception as e:
        logger.error(f"[Session ID: {session_id}] Error processing intent: {e}", exc_info=True)
        return NLUResponse(
            transcript=data.text,
            message=f"오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id=session_id
        )

@router.post("/upload-audio", response_model=NLUResponse)
async def process_audio(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    projectId: Optional[str] = Form(None),
    slId: Optional[str] = Form(None)
):
    file_location = f"temp_{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(await file.read())
    
    session_id = session_id or "audio_session"
    logger.info(f"[Session ID: {session_id}] Processing audio upload: {file.filename} (Project: {projectId}, SL: {slId})")
    try:
        transcript = await transcribe_audio(file_location)
        logger.info(f"[Session ID: {session_id}] Transcribed text: {transcript}")
        
        if transcript.startswith("["):
            return NLUResponse(
                transcript=transcript,
                message=transcript,
                candidates=[],
                requires_confirmation=False,
                session_id=session_id
            )

        response = await parse_intent(
            transcript, 
            session_id=session_id,
            project_id=projectId,
            sl_id=slId
        )
        response.session_id = session_id
        
        log_entry = log_action(session_id, transcript, response.model_dump())
        response.log_id = log_entry.id
        
        logger.info(f"[Session ID: {session_id}] Successfully processed audio. Log ID: {response.log_id}")
        return response
        
    except Exception as e:
        logger.error(f"[Session ID: {session_id}] Error processing audio: {e}", exc_info=True)
        return NLUResponse(
            transcript="[처리 오류]",
            message=f"오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id=session_id
        )
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

@router.post("/mock-command", response_model=NLUResponse)
async def mock_command(
    data: CommandRequest
):
    session_id = data.session_id or "mock_session"
    logger.info(f"[Session ID: {session_id}] Processing mock command: {data.text} (Project: {data.projectId}, SL: {data.slId})")
    try:
        # history = get_session_history(session_id)

        response = await parse_intent(
            text=data.text, 
            session_id=session_id, 
            project_id=data.projectId, 
            sl_id=data.slId,
            selected_candidate=data.selected_candidate
        )
        response.session_id = session_id
        
        log_entry = log_action(session_id, data.text, response.model_dump())
        response.log_id = log_entry.id
        
        logger.info(f"[Session ID: {session_id}] Successfully processed mock command. Log ID: {response.log_id}")
        return response
    except Exception as e:
        logger.error(f"[Session ID: {session_id}] Error processing mock command: {e}", exc_info=True)
        return NLUResponse(
            transcript=data.text,
            message=f"오류가 발생했습니다: {str(e)}",
            candidates=[],
            requires_confirmation=False,
            session_id=session_id
        )

@router.post("/feedback")
async def receive_feedback(
    data: FeedbackRequest
):
    logger.info(f"Received feedback for Log ID: {data.log_id}, Correct: {data.is_correct}")
    success = update_action_feedback(data.log_id, data.is_correct, data.corrected_intent)
    if success:
        return {"message": "피드백이 성공적으로 기록되었습니다."}
    else:
        logger.warning(f"Failed to find log entry for feedback. Log ID: {data.log_id}")
        raise HTTPException(status_code=404, detail="해당 로그를 찾을 수 없습니다.")
