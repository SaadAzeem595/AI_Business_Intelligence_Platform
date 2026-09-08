import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.reports.models import Report, ReportSchedule
from app.features.reports.schemas import (
    GenerateReportPayload,
    ReportResponse,
    ReportSchedulePayload,
    ReportScheduleResponse,
    ExecutiveReportData,
    ReportMetadata,
)
from app.features.reports.context_builder import ExecutiveReportContextBuilder
from app.features.reports.narrative_generator import NarrativeGenerator
from app.features.reports.snapshot_generator import DashboardSnapshotGenerator
from app.features.reports.pdf_generator import PDFReportGenerator
from app.features.reports.pptx_generator import PowerPointReportGenerator
from app.features.reports.html_generator import HTMLReportGenerator
from app.features.reports.delivery import EmailDeliveryChannel

logger = logging.getLogger(__name__)


class ReportService:
    """
    Core service orchestrating report compiling pipelines, multi-module context aggregation,
    anti-hallucination validation, multi-format delivery (PDF, PPTX, HTML), and recurring schedules.
    """

    @staticmethod
    async def trigger_celery_report_generation(
        db: AsyncSession,
        payload: GenerateReportPayload,
        author: str = "system"
    ) -> ReportResponse:
        """
        Creates report stub record with 'Pending' status and enqueues compilation to Celery workers.
        """
        report_id = str(uuid.uuid4())
        sources_str = json.dumps(payload.data_sources) if payload.data_sources else "[]"
        options_str = json.dumps(payload.options) if payload.options else "[]"

        db_report = Report(
            id=report_id,
            title=payload.title,
            type=payload.type,
            frequency=payload.frequency,
            created=datetime.now().isoformat(),
            size="0 KB",
            recipient=payload.recipient,
            workspace=payload.workspace,
            project_id=payload.project_id,
            author=author,
            template=payload.template,
            reporting_period=payload.reporting_period,
            data_sources=sources_str,
            options=options_str,
            delivery_status="Pending",
            file_path=None,
            report_data=None,
            delivery_error=None
        )
        db.add(db_report)
        await db.commit()
        await db.refresh(db_report)

        # Trigger Celery task
        from app.features.reports.tasks import generate_report_task
        generate_report_task.delay(report_id, payload.model_dump())

        return ReportService._to_response(db_report)

    @staticmethod
    async def generate_report_db_flow(
        db: AsyncSession,
        report_id: str,
        payload: GenerateReportPayload,
        author: str = "system"
    ) -> Report:
        """
        Executes the full multi-module aggregation, anti-hallucination validation,
        deliverable compilation, and optional email delivery.
        """
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalars().first()
        if not report:
            raise ValueError(f"Report stub with ID {report_id} not found.")

        try:
            logger.info(f"Starting Executive Report aggregation pipeline for report: {payload.title} (ID: {report_id})")

            # 1. Multi-module analytical context aggregation
            ctx = await ExecutiveReportContextBuilder.build_context(payload, db, author=author)
            ctx.metadata.report_id = report_id

            # 2. Grounded narrative generation & anti-hallucination verification
            summary, insights, impacts, recs = NarrativeGenerator.generate_narrative_and_insights(
                ctx=ctx,
                template=payload.template
            )

            # 3. Assemble normalized ExecutiveReportData
            report_data = ExecutiveReportData(
                metadata=ctx.metadata,
                executive_summary=summary,
                kpi_overview=ctx.kpis,
                key_insights=insights,
                trends_chart=ctx.chart_data,
                anomalies=ctx.anomalies,
                forecast=ctx.forecast,
                segmentation=ctx.segments,
                business_impact=impacts,
                recommendations=recs,
                evidence=ctx.evidence
            )

            # 4. Generate Snapshot PNG for visuals
            os.makedirs(os.path.join("storage", "reports"), exist_ok=True)
            snapshot_filename = f"snapshot-{report_id}.png"
            snapshot_path = os.path.join("storage", "reports", snapshot_filename)
            snapshot_abs = os.path.abspath(snapshot_path)

            kpis_dict_list = [
                {"title": k.title, "value": k.current_value, "change": k.change_pct}
                for k in ctx.kpis
            ]
            DashboardSnapshotGenerator.generate_dashboard_snapshot(kpis_dict_list, ctx.chart_data, snapshot_abs)

            # 5. Compile Deliverables (PDF / PPTX / HTML)
            format_type = (payload.type or "PDF").strip()
            ext = "pdf" if format_type == "PDF" else ("pptx" if format_type in ["PowerPoint", "PPTX"] else "html")
            report_filename = f"report-{report_id}.{ext}"
            report_path = os.path.join("storage", "reports", report_filename)
            report_abs = os.path.abspath(report_path)

            template_data = report_data.model_dump()
            template_data["author"] = author
            template_data["workspace"] = payload.workspace
            template_data["recipient"] = payload.recipient
            template_data["confidence_score"] = 0.96

            if ext == "pdf":
                PDFReportGenerator.generate(report_abs, payload.title, payload.template, template_data, snapshot_abs)
            elif ext == "pptx":
                PowerPointReportGenerator.generate(report_abs, payload.title, payload.template, template_data, snapshot_abs)
            else:
                HTMLReportGenerator.generate(report_abs, report_data)

            # Calculate file size
            file_size_bytes = os.path.getsize(report_abs) if os.path.exists(report_abs) else 1024
            file_size_kb = file_size_bytes / 1024
            size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{(file_size_kb/1024):.1f} MB"

            # 6. Execute Email Delivery if requested
            delivery_status = "Delivered"
            delivery_err = None
            try:
                channel = EmailDeliveryChannel()
                channel.deliver(report_path, payload.recipient, payload.title)
            except Exception as e:
                logger.error(f"Email delivery issue: {e}")
                delivery_status = "Delivery Pending"
                delivery_err = str(e)

            # 7. Update Database Record
            report.status = "Active"
            report.size = size_str
            report.file_path = report_path
            report.datasets_used = ctx.dataset_name
            report.delivery_status = delivery_status
            report.delivery_error = delivery_err
            report.report_data = report_data.model_dump_json()

            logger.info(f"Executive Report pipeline successfully completed for report: {report_id}")

        except Exception as e:
            logger.error(f"Error executing Executive Report pipeline for ID {report_id}: {str(e)}", exc_info=True)
            report.delivery_status = "Failed"
            report.delivery_error = f"Pipeline execution error: {str(e)}"
            report.size = "0 KB"

        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report

    @staticmethod
    async def regenerate_narrative(
        db: AsyncSession,
        report_id: str,
        custom_focus: Optional[str] = None
    ) -> ReportResponse:
        """Regenerates AI narrative, insights, and recommendations for an existing report."""
        report = await ReportService.get_report_by_id(db, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found.")

        if not report.report_data:
            raise ValueError("Report contains no structured context data to regenerate.")

        data_dict = json.loads(report.report_data)
        report_data = ExecutiveReportData.model_validate(data_dict)

        # Mock context from existing report_data
        class TempContext:
            def __init__(self, rd: ExecutiveReportData):
                self.kpis = rd.kpi_overview
                self.chart_data = rd.trends_chart
                self.anomalies = rd.anomalies
                self.forecast = rd.forecast
                self.segments = rd.segmentation
                self.evidence = rd.evidence
                self.source_facts = {}

        temp_ctx = TempContext(report_data)
        summary, insights, impacts, recs = NarrativeGenerator.generate_narrative_and_insights(
            ctx=temp_ctx,
            template=report.template,
            custom_focus=custom_focus
        )

        report_data.executive_summary = summary
        report_data.key_insights = insights
        report_data.business_impact = impacts
        report_data.recommendations = recs
        report.report_data = report_data.model_dump_json()

        # Recompile file if exists
        if report.file_path:
            ext = "pdf" if report.type == "PDF" else ("pptx" if report.type in ["PowerPoint", "PPTX"] else "html")
            report_abs = os.path.abspath(report.file_path)
            template_data = report_data.model_dump()
            template_data["author"] = report.author
            template_data["workspace"] = report.workspace
            template_data["recipient"] = report.recipient

            snapshot_path = report.file_path.replace(".pdf", ".png").replace(".pptx", ".png").replace(".html", ".png").replace("report-", "snapshot-")
            if ext == "pdf":
                PDFReportGenerator.generate(report_abs, report.title, report.template, template_data, snapshot_path)
            elif ext == "pptx":
                PowerPointReportGenerator.generate(report_abs, report.title, report.template, template_data, snapshot_path)
            else:
                HTMLReportGenerator.generate(report_abs, report_data)

        db.add(report)
        await db.commit()
        await db.refresh(report)
        return ReportService._to_response(report)

    @staticmethod
    async def send_report_email(
        db: AsyncSession,
        report_id: str,
        target_recipient: Optional[str] = None
    ) -> bool:
        """Triggers email dispatch for a compiled deliverable and updates delivery status."""
        report = await ReportService.get_report_by_id(db, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found.")

        recipient = target_recipient or report.recipient
        if not report.file_path or not os.path.exists(report.file_path):
            report.delivery_status = "Failed"
            report.delivery_error = "Report deliverable file is missing on server host."
            db.add(report)
            await db.commit()
            return False

        try:
            channel = EmailDeliveryChannel()
            delivered = channel.deliver(report.file_path, recipient, report.title)
            if delivered:
                report.delivery_status = "Delivered"
                report.delivery_error = None
            else:
                report.delivery_status = "Failed"
                report.delivery_error = "SMTP channel delivery rejected."
        except Exception as e:
            report.delivery_status = "Failed"
            report.delivery_error = f"Email dispatch failed: {str(e)}"

        db.add(report)
        await db.commit()
        return report.delivery_status == "Delivered"

    @staticmethod
    def _to_response(report: Report) -> ReportResponse:
        parsed_data = None
        if report.report_data:
            try:
                parsed_data = ExecutiveReportData.model_validate_json(report.report_data)
            except Exception:
                pass

        resp = ReportResponse(
            id=report.id,
            title=report.title,
            type=report.type,
            frequency=report.frequency,
            template=report.template,
            created=report.created,
            size=report.size,
            recipient=report.recipient,
            workspace=report.workspace,
            project_id=report.project_id,
            author=report.author,
            reporting_period=report.reporting_period or "Last 30 Days",
            data_sources=report.data_sources,
            options=report.options,
            datasets_used=report.datasets_used,
            delivery_status=report.delivery_status,
            delivery_error=report.delivery_error,
            file_path=report.file_path,
            report_data=parsed_data
        )
        return resp

    @staticmethod
    async def get_reports_history(
        db: AsyncSession,
        workspace: Optional[str] = None,
        project_id: Optional[str] = None,
        report_type: Optional[str] = None,
        author: Optional[str] = None,
        delivery_status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> List[Report]:
        """Queries report history with specific query parameters, project scoping, and searches."""
        query = select(Report)

        if workspace:
            query = query.where(Report.workspace == workspace)
        if project_id:
            query = query.where(Report.project_id == project_id)
        if report_type:
            query = query.where((Report.type == report_type) | (Report.template == report_type))
        if author:
            query = query.where(Report.author == author)
        if delivery_status:
            query = query.where(Report.delivery_status == delivery_status)
        if search:
            query = query.where(Report.title.ilike(f"%{search}%"))

        query = query.order_by(Report.created.desc())
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_report_by_id(db: AsyncSession, report_id: str) -> Optional[Report]:
        result = await db.execute(select(Report).where(Report.id == report_id))
        return result.scalars().first()

    @staticmethod
    async def delete_report(db: AsyncSession, report_id: str) -> bool:
        report = await ReportService.get_report_by_id(db, report_id)
        if not report:
            return False

        if report.file_path and os.path.exists(report.file_path):
            try:
                os.remove(report.file_path)
                snapshot_path = report.file_path.replace(".pdf", ".png").replace(".pptx", ".png").replace(".html", ".png").replace("report-", "snapshot-")
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
            except Exception as e:
                logger.error(f"Error removing file {report.file_path}: {str(e)}")

        await db.delete(report)
        await db.flush()
        return True

    @staticmethod
    async def create_schedule(
        db: AsyncSession,
        payload: ReportSchedulePayload,
        author: str = "system"
    ) -> ReportSchedule:
        schedule_id = str(uuid.uuid4())
        sources_str = json.dumps(payload.data_sources) if payload.data_sources else None
        options_str = json.dumps(payload.options) if payload.options else None

        db_schedule = ReportSchedule(
            id=schedule_id,
            title=payload.title,
            workspace=payload.workspace,
            project_id=payload.project_id,
            report_type=payload.report_type,
            frequency=payload.frequency,
            template=payload.template,
            reporting_period=payload.reporting_period,
            data_sources=sources_str,
            options=options_str,
            recipient=payload.recipient,
            author=author,
            is_active=True,
            created_at=datetime.now().isoformat()
        )
        db.add(db_schedule)
        await db.flush()
        return db_schedule

    @staticmethod
    async def list_schedules(db: AsyncSession, workspace: Optional[str] = None) -> List[ReportSchedule]:
        query = select(ReportSchedule)
        if workspace:
            query = query.where(ReportSchedule.workspace == workspace)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def cancel_schedule(db: AsyncSession, schedule_id: str) -> bool:
        result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
        schedule = result.scalars().first()
        if not schedule:
            return False
        await db.delete(schedule)
        await db.flush()
        return True
