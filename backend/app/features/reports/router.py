import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.reports.schemas import (
    GenerateReportPayload,
    ReportResponse,
    ReportSchedulePayload,
    ReportScheduleResponse,
)
from app.features.reports.service import ReportService
from app.core.cache import cache_client

router = APIRouter(prefix="/reports", tags=["Executive Reports"])


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    workspace: Optional[str] = None,
    report_type: Optional[str] = None,
    author: Optional[str] = None,
    delivery_status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[ReportResponse]:
    """Retrieves list of compiled reports history, supporting query filters and searches."""
    cache_key = f"reports:list:{workspace}:{report_type}:{author}:{delivery_status}:{search}"
    try:
        cached = await cache_client.get(cache_key)
        if cached:
            return [ReportResponse.model_validate(r) for r in cached]
    except Exception:
        pass

    reports = await ReportService.get_reports_history(
        db,
        workspace=workspace,
        report_type=report_type,
        author=author,
        delivery_status=delivery_status,
        search=search
    )
    res_list = [ReportResponse.model_validate(r) for r in reports]
    try:
        cache_data = [r.model_dump() for r in res_list]
        await cache_client.set(cache_key, cache_data, ttl=60)
    except Exception:
        pass
    return res_list


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    payload: GenerateReportPayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Queues a document compiler action in background Celery workers and returns initial pending log."""
    author_email = current_user.email if hasattr(current_user, "email") else "system"
    res = await ReportService.trigger_celery_report_generation(db, payload, author=author_email)
    try:
        await cache_client.invalidate_pattern("reports:*")
    except Exception:
        pass
    return res


@router.get("/{id}", response_model=ReportResponse)
async def get_report(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Retrieves a single report log details."""
    cache_key = f"reports:item:{id}"
    try:
        cached = await cache_client.get(cache_key)
        if cached:
            return ReportResponse.model_validate(cached)
    except Exception:
        pass

    report = await ReportService.get_report_by_id(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {id} not found."
        )
    res_obj = ReportResponse.model_validate(report)
    try:
        await cache_client.set(cache_key, res_obj.model_dump(), ttl=60)
    except Exception:
        pass
    return res_obj


@router.get("/{id}/download")
async def download_report(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Downloads the compiled PDF/PowerPoint report file directly."""
    report = await ReportService.get_report_by_id(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {id} not found."
        )
    
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file is missing or still compiling in background."
        )
        
    ext = "pdf" if report.type == "PDF" else "pptx"
    filename = f"{report.title.replace(' ', '_')}.{ext}"
    
    return FileResponse(
        path=report.file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.delete("/{id}")
async def delete_report(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Removes a report archive and delete files on host."""
    success = await ReportService.delete_report(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {id} not found."
        )
    try:
        await cache_client.invalidate(f"reports:item:{id}")
        await cache_client.invalidate_pattern("reports:list:*")
    except Exception:
        pass
    return {"status": "success", "message": f"Report {id} deleted successfully."}


@router.post("/schedule", response_model=ReportScheduleResponse)
async def create_schedule(
    payload: ReportSchedulePayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReportScheduleResponse:
    """Registers a new periodic reporting rule schedule."""
    author_email = current_user.email if hasattr(current_user, "email") else "system"
    schedule = await ReportService.create_schedule(db, payload, author=author_email)
    try:
        await cache_client.invalidate_pattern("reports:*")
    except Exception:
        pass
    return ReportScheduleResponse.model_validate(schedule)


@router.get("/schedules/list", response_model=List[ReportScheduleResponse])
async def list_schedules(
    workspace: Optional[str] = None,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[ReportScheduleResponse]:
    """Lists current scheduled routines."""
    schedules = await ReportService.list_schedules(db, workspace=workspace)
    return [ReportScheduleResponse.model_validate(s) for s in schedules]


@router.delete("/schedules/{id}")
async def cancel_schedule(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Deletes/cancels a periodic reporting schedule."""
    success = await ReportService.cancel_schedule(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule ID {id} not found."
        )
    try:
        await cache_client.invalidate_pattern("reports:*")
    except Exception:
        pass
    return {"status": "success", "message": f"Schedule {id} cancelled successfully."}
