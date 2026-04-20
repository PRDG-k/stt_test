from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class ActionIntent(BaseModel):
    action: str
    params: Optional[Dict[str, Any]] = None
    confidence: float = 1.0

class ActionTarget(BaseModel):
    URI: str = Field(description="The target API URI or frontend page identifier")
    TYPE: str = Field(description="The HTTP method or action type (e.g., GET, POST, NAVIGATE)")
    PARAMS: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")

class NLUResponse(BaseModel):
    transcript: str
    message: str = Field(description="Response message or clarification question for the user")
    candidates: List[Dict[str, Any]] = Field(default_factory=list, description="List of proposed actions to take")
    requires_confirmation: bool = Field(default=True, description="True if the user must pick a candidate or confirm")
    session_id: str

class ActionLog(BaseModel):
    id: Optional[int] = None
    transcript: str
    intent: ActionIntent
    status: str = "success"
    created_at: datetime = datetime.now()

class STTResponse(BaseModel):
    transcript: str
    intent: ActionIntent
    message: str
    redirect_url: Optional[str] = None

class CommandRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
