from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.chat.schemas import ChatMessagePayload, ChatMessageResponse, ChatSessionResponse
from app.features.chat.service import ChatService

router = APIRouter(prefix="/chat", tags=["AI Copilot Chat Engine"])


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: MockUser = Depends(get_current_user),
) -> List[ChatSessionResponse]:
    """Returns past conversational sessions history details."""
    return [
        ChatSessionResponse(id="s-902", title="Q3 Projections Audit", created="2026-08-02"),
        ChatSessionResponse(id="s-781", title="Churn Cluster Review", created="2026-08-01"),
    ]


@router.post("/message", response_model=ChatMessageResponse)
async def post_chat_message(
    payload: ChatMessagePayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChatMessageResponse:
    """Submits a message and yields responses containing analysis text, charts, or structured data tables."""
    return await ChatService.get_assistant_response(payload, current_user, db)
