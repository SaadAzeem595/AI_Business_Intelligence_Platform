from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ExecutionLogItem(BaseModel):
    agent_name: str
    status: str  # success, failure, pending, paused
    duration_ms: float
    timestamp: str
    details: Optional[str] = None

class AgentChatPayload(BaseModel):
    message: str
    thread_id: Optional[str] = None
    workspace: Optional[str] = "default"
    dataset: Optional[str] = None
    active_project: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None

class ApproveQueryPayload(BaseModel):
    thread_id: str
    approved: bool

class AgentChatResponse(BaseModel):
    thread_id: str
    status: str  # completed, paused, failed
    response: Optional[str] = None
    reasoning_path: List[str] = Field(default_factory=list)
    execution_logs: List[ExecutionLogItem] = Field(default_factory=list)
    visualization_spec: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    executive_summary: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    chart: Optional[Dict[str, Any]] = None
    table: Optional[Dict[str, Any]] = None
