from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import difflib
from app.core.config import settings

Base = declarative_base()

class ActionLogModel(Base):
    __tablename__ = "action_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    transcript = Column(String)
    intent = Column(JSON)  # NLUResponse 데이터 (candidates 등)
    status = Column(String)
    is_correct = Column(Boolean, nullable=True) # 사용자 피드백
    corrected_intent = Column(JSON, nullable=True) # 사용자가 직접 수정한 결과
    created_at = Column(DateTime, default=datetime.utcnow)

class ConversationLogModel(Base):
    __tablename__ = "conversation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String) # "user", "assistant"
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def log_conversation(session_id: str, role: str, content: str):
    db = SessionLocal()
    try:
        new_log = ConversationLogModel(
            session_id=session_id,
            role=role,
            content=content
        )
        db.add(new_log)
        db.commit()
    finally:
        db.close()

def log_action(session_id: str, transcript: str, intent_dict: dict, status: str = "success"):
    db = SessionLocal()
    try:
        new_log = ActionLogModel(
            session_id=session_id,
            transcript=transcript,
            intent=intent_dict,
            status=status
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return new_log
    finally:
        db.close()

def update_action_feedback(log_id: int, is_correct: bool, corrected_intent: dict = None):
    db = SessionLocal()
    try:
        log = db.query(ActionLogModel).filter(ActionLogModel.id == log_id).first()
        if log:
            log.is_correct = is_correct
            if corrected_intent:
                log.corrected_intent = corrected_intent
            db.commit()
            return True
        return False
    finally:
        db.close()

def get_similar_cases(query_text: str, limit: int = 3, threshold: float = 0.6) -> list:
    db = SessionLocal()
    try:
        # 최근 성공 사례(피드백이 긍정적이거나 수정된 결과가 있는 경우) 100개를 가져옴
        past_cases = db.query(ActionLogModel)\
                       .filter((ActionLogModel.is_correct == True) | (ActionLogModel.corrected_intent != None))\
                       .order_by(ActionLogModel.created_at.desc())\
                       .limit(100).all()
        
        results = []
        for case in past_cases:
            similarity = difflib.SequenceMatcher(None, query_text, case.transcript).ratio()
            if similarity >= threshold:
                target_intent = case.corrected_intent if case.corrected_intent else case.intent
                # 프롬프트에 넣기 위해 최소 정보만 추출
                results.append({
                    "input": case.transcript,
                    "output": target_intent.get("candidates", []),
                    "similarity": similarity
                })
        
        # 유사도 순으로 정렬 후 상위 limit개 반환
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
    finally:
        db.close()

def get_session_history(session_id: str, limit: int = 10) -> str:
    db = SessionLocal()
    try:
        logs = db.query(ConversationLogModel)\
                 .filter(ConversationLogModel.session_id == session_id)\
                 .order_by(ConversationLogModel.created_at.asc())\
                 .limit(limit).all()
        
        history = ""
        for log in logs:
            history += f"{log.role}: {log.content}\n"
        return history or "No previous history."
    finally:
        db.close()
