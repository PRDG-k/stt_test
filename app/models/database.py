from sqlalchemy import Column, Integer, String, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from app.core.config import settings

Base = declarative_base()

class ActionLogModel(Base):
    __tablename__ = "action_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    transcript = Column(String)
    intent = Column(JSON)  # Pydantic ActionTarget 리스트 또는 NLUResponse 데이터
    status = Column(String)
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
