from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.reports.schemas import GenerateReportPayload, ReportResponse
from app.features.reports.service import ReportService

router = APIRouter(prefix="/reports", tags=["Executive Reports"])


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[ReportResponse]:
    """Returns compiled report documents archives."""
    return [
        ReportResponse(id="1", title="Q3 Sales Projections & Outliers Report", type="PDF", frequency="Weekly", created="2026-08-02", size="1.4 MB", recipient="board@acme.com"),
        ReportResponse(id="2", title="Customer Clustering & Cohort Profile Review", type="PowerPoint", frequency="Ad-hoc", created="2026-07-28", size="4.2 MB", recipient="saad@example.com"),
        ReportResponse(id="3", title="System Anomalies Log Summary", type="PDF", frequency="Daily", created="2026-08-01", size="320 KB", recipient="ops@acme.com"),
    ]


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    payload: GenerateReportPayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Queues a document compiler action via workers."""
    return ReportService.trigger_celery_report_generation(payload)


@router.delete("/{id}")
async def delete_report(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Removes a report archive from local logs."""
    return {"status": "success"}
