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


@router.get("/diagnostics")
async def chat_diagnostics(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Safe diagnostic endpoint reporting AI Chat subsystem health and dataset readiness."""
    import os
    from datetime import datetime
    from sqlalchemy import select, func
    from app.core.llm import LLMService
    from app.core.database import get_duckdb_conn
    from app.features.datasets.models import Dataset
    from app.core.config import settings

    # 1. DB dataset count & summaries
    res = await db.execute(select(func.count(Dataset.id)))
    ds_count = res.scalar() or 0

    ds_res = await db.execute(select(Dataset))
    datasets = [
        {
            "id": d.id,
            "filename": d.filename,
            "display_name": d.display_name,
            "duckdb_table": d.duckdb_table,
            "project_id": d.project_id,
            "workspace_id": d.workspace_id,
            "storage_path": d.storage_path,
            "exists_on_disk": os.path.exists(d.storage_path) if d.storage_path else False,
            "rows": d.rows
        }
        for d in ds_res.scalars().all()
    ]

    # 2. DuckDB connectivity probe
    duckdb_ok = False
    duckdb_err = None
    try:
        gen = get_duckdb_conn()
        conn = next(gen)
        conn.execute("SELECT 1")
        duckdb_ok = True
    except Exception as de:
        duckdb_err = str(de)

    # 3. Storage path readiness
    uploads_dir = getattr(settings, "resolved_uploads_dir", None)
    storage_ok = bool(uploads_dir and os.path.isdir(uploads_dir))
    files_in_uploads = os.listdir(uploads_dir) if storage_ok else []

    # 4. LLM provider status
    llm_diag = LLMService.get_diagnostic_status()

    return {
        "status": "healthy" if (duckdb_ok and llm_diag.get("api_key_configured")) else "degraded",
        "timestamp": datetime.now().isoformat(),
        "user_id": current_user.id,
        "workspace_id": current_user.workspace_id,
        "datasets_count": ds_count,
        "datasets": datasets,
        "duckdb": {"ready": duckdb_ok, "error": duckdb_err},
        "storage": {
            "uploads_dir": uploads_dir,
            "exists": storage_ok,
            "file_count": len(files_in_uploads),
            "files": files_in_uploads[:20]
        },
        "llm": llm_diag
    }
