from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessagePayload(BaseModel):
    message: str
    thread_id: Optional[str] = None
    conversation_id: Optional[str] = None
    workspace: Optional[str] = "default"
    workspace_id: Optional[str] = None
    dataset: Optional[str] = None
    dataset_id: Optional[str] = None
    selected_dataset_ids: Optional[List[str]] = None
    active_project: Optional[str] = None
    project_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class ChatMessageResponse(BaseModel):
    role: str = "assistant"
    content: str
    response: Optional[str] = None
    thread_id: Optional[str] = None
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    sql_query: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: Optional[int] = None
    chart: Optional[Dict[str, Any]] = None
    table: Optional[Dict[str, Any]] = None


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created: str
