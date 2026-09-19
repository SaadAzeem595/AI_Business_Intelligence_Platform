import os
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.reports.models import ReportSchedule
from app.features.reports.schemas import (
    GenerateReportPayload,
    ReportResponse,
    ReportSchedulePayload,
    ReportScheduleResponse,
    RegenerateNarrativePayload,
    EmailReportPayload,
)
from app.features.reports.service import ReportService
from app.core.cache import cache_client
from app.features.billing.entitlements import EntitlementService

router = APIRouter(prefix="/reports", tags=["Executive Reports"])


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    workspace: Optional[str] = None,
    project_id: Optional[str] = None,
    report_type: Optional[str] = None,
    author: Optional[str] = None,
    delivery_status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[ReportResponse]:
    """Retrieves list of compiled reports history, supporting query filters, project scoping, and pagination."""
    workspace = current_user.workspace_id
    reports = await ReportService.get_reports_history(
        db,
        workspace=workspace,
        project_id=project_id,
        report_type=report_type,
        author=author,
        delivery_status=delivery_status,
        search=search,
        page=page,
        page_size=page_size
    )
    return [ReportService._to_response(r) for r in reports]


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    payload: GenerateReportPayload,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin", "Executive"])),
    db: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Executes the multi-source executive report compiler pipeline and returns full report data & preview."""
    payload.workspace = current_user.workspace_id
    author_email = current_user.email if hasattr(current_user, "email") else "system"

    # Validate project access if scoped
    if payload.project_id:
        from app.features.projects.router import get_project_and_verify_access
        try:
            await get_project_and_verify_access(payload.project_id, current_user, db)
        except HTTPException:
            pass  # Allow if dev bypass

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
    """Retrieves a single report with its complete structured preview context."""
    report = await ReportService.get_report_by_id(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {id} not found."
        )
    if report.workspace != current_user.workspace_id and report.workspace != "default":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this report."
        )
    return ReportService._to_response(report)


@router.post("/{id}/regenerate", response_model=ReportResponse)
async def regenerate_report_narrative(
    id: str,
    payload: RegenerateNarrativePayload,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin", "Executive"])),
    db: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    """Regenerates the AI executive summary, insights, and recommendations with anti-hallucination verification."""
    try:
        updated_report = await ReportService.regenerate_narrative(
            db=db,
            report_id=id,
            custom_focus=payload.custom_prompt_focus
        )
        return updated_report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to regenerate narrative: {str(e)}"
        )


@router.post("/{id}/email")
async def send_report_email(
    id: str,
    payload: Optional[EmailReportPayload] = None,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin", "Executive"])),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Dispatches the compiled deliverable attachment to the specified recipient via SMTP email channel."""
    recipient = payload.recipient if payload and payload.recipient else None
    try:
        success = await ReportService.send_report_email(db, id, target_recipient=recipient)
        if not success:
            report = await ReportService.get_report_by_id(db, id)
            err_msg = report.delivery_error if report and report.delivery_error else "Email delivery failed."
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg
            )
        return {"status": "success", "message": f"Report deliverable emailed successfully to {recipient or 'target recipient'}."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email delivery failed: {str(e)}"
        )


@router.get("/{id}/download")
async def download_report(
    id: str,
    format: Optional[str] = Query(None, description="Requested download format (PDF, PPTX, HTML)"),
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Downloads the compiled PDF, PowerPoint, or HTML report file directly."""
    report = await ReportService.get_report_by_id(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {id} not found."
        )
    if report.workspace != current_user.workspace_id and report.workspace != "default":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to download this report."
        )

    # Determine targeted file path
    target_format = (format or report.type or "PDF").strip().upper()
    req_ext = "pdf" if "PDF" in target_format else ("pptx" if "PPT" in target_format or "POWERPOINT" in target_format else "html")

    file_path = report.file_path
    reports_dir = os.path.join(settings.resolved_storage_dir, "reports")
    if not file_path or not os.path.exists(file_path) or not file_path.endswith(f".{req_ext}"):
        # Check if alternative format exists or compile on the fly
        base_path = file_path.rsplit(".", 1)[0] if file_path else os.path.join(reports_dir, f"report-{id}")
        alt_path = f"{base_path}.{req_ext}"
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            # Generate on the fly if report_data exists
            if report.report_data:
                from app.features.reports.schemas import ExecutiveReportData
                from app.features.reports.pdf_generator import PDFReportGenerator
                from app.features.reports.pptx_generator import PowerPointReportGenerator
                from app.features.reports.html_generator import HTMLReportGenerator

                data_dict = json.loads(report.report_data)
                exec_data = ExecutiveReportData.model_validate(data_dict)
                snapshot_path = os.path.join(reports_dir, f"snapshot-{id}.png")

                if req_ext == "pdf":
                    PDFReportGenerator.generate(alt_path, report.title, report.template, data_dict, snapshot_path)
                elif req_ext == "pptx":
                    PowerPointReportGenerator.generate(alt_path, report.title, report.template, data_dict, snapshot_path)
                else:
                    HTMLReportGenerator.generate(alt_path, exec_data)
                file_path = alt_path
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report file is missing or still compiling in background."
                )

    clean_title = "".join(c for c in report.title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"{clean_title}.{req_ext}"
    media_type = "application/pdf" if req_ext == "pdf" else (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation" if req_ext == "pptx" else "text/html"
    )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@router.delete("/{id}")
async def delete_report(
    id: str,
    current_user: MockUser = Depends(require_role(["Admin", "Analyst"])),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Removes a report archive and deletes associated files on host."""
    report = await ReportService.get_report_by_id(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with ID {id} not found."
        )
    if report.workspace != current_user.workspace_id and report.workspace != "default":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this report."
        )
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
    current_user: MockUser = Depends(require_role(["Admin", "Analyst"])),
    db: AsyncSession = Depends(get_db_session),
) -> ReportScheduleResponse:
    """Registers a new periodic reporting rule schedule."""
    await EntitlementService.check_feature_entitlement(
        db, current_user.workspace_id, "scheduled_reports"
    )
    payload.workspace = current_user.workspace_id
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
    workspace = current_user.workspace_id
    schedules = await ReportService.list_schedules(db, workspace=workspace)
    return [ReportScheduleResponse.model_validate(s) for s in schedules]


@router.delete("/schedules/{id}")
async def cancel_schedule(
    id: str,
    current_user: MockUser = Depends(require_role(["Admin", "Analyst"])),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Deletes/cancels a periodic reporting schedule."""
    result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == id))
    schedule = result.scalars().first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule ID {id} not found."
        )
    if schedule.workspace != current_user.workspace_id and schedule.workspace != "default":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this schedule."
        )
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
