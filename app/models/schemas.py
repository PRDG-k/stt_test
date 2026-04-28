from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime
from enum import Enum

# --- Base Action Model ---

class BaseAction(BaseModel):
    requires_confirmation: bool = Field(default=True, description="사용자 확인 필요 여부")

# --- Action Parameter Models ---

class DataFetchParams(BaseModel):
    device: str
    interval: Literal["1s", "5s", "10s", "30s", "1m", "5m", "1h"]
    fields: List[Literal["voltage", "current", "power", "temperature"]]

class DataFetchAction(BaseAction):
    action: Literal["DATA_FETCH"]
    target: Literal["realtime_chart"]
    params: DataFetchParams

class DeviceControlParams(BaseModel):
    device: str
    command: Literal["REBOOT", "START", "STOP", "RESET"]
    message: Optional[str] = None

class DeviceControlAction(BaseAction):
    action: Literal["DEVICE_CONTROL"]
    status: Optional[Literal["success", "fail", "pending"]] = None
    params: DeviceControlParams

class FileDownloadParams(BaseModel):
    reportName: str
    start: str
    end: str
    downloadUrl: str

class FileDownloadAction(BaseAction):
    action: Literal["FILE_DOWNLOAD"]
    fileType: Literal["xlsx", "csv", "pdf"]
    params: FileDownloadParams

class MovePageParams(BaseModel):
    slId: Optional[str]

class MovePageAction(BaseAction):
    action: Literal["MOVE_PAGE"]
    projectId: Optional[str] = None
    url: str
    params: MovePageParams

class ShowMsgAction(BaseAction):
    action: Literal["SHOW_MSG"]
    type: Literal["info", "success", "warning", "error"]
    content: str

# Union type for all validated actions
ValidatedAction = Union[
    DataFetchAction, 
    DeviceControlAction, 
    FileDownloadAction, 
    MovePageAction, 
    ShowMsgAction
]

# --- Existing Models ---

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
    log_id: Optional[int] = None

class FeedbackRequest(BaseModel):
    log_id: int
    is_correct: bool
    corrected_intent: Optional[Dict[str, Any]] = None

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
    projectId: Optional[str] = None
    slId: Optional[str] = None
    selected_candidate: Optional[Dict[str, Any]] = None
