from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ChatMessagePayload(BaseModel):
    message: str
    sessionId: Optional[str] = None


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    chart: Optional[Dict[str, Any]] = None
    table: Optional[Dict[str, Any]] = None


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created: str
