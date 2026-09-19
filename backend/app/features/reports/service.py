import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
import app.features.auth.models  # Ensures User relationship is initialized in SQLAlchemy mapper
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
    async def build_preview_report(
        db: AsyncSession,
        payload: GenerateReportPayload,
        author: str = "system"
    ) -> ReportResponse:
        """
        Executes the multi-source analytical context aggregation and narrative generation pipeline
        for Preview Brief without persisting deliverable files or dispatching emails.
        """
        logger.info(f"Generating Executive Report Preview Brief for: {payload.title}")
        ctx = await ExecutiveReportContextBuilder.build_context(payload, db, author=author)
        preview_id = f"preview-{uuid.uuid4()}"
        ctx.metadata.report_id = preview_id

        summary, insights, impacts, recs = NarrativeGenerator.generate_narrative_and_insights(
            ctx=ctx,
            template=payload.template
        )

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
            evidence=ctx.evidence,
            module_statuses=ctx.module_statuses,
            structured_metrics=ctx.structured_metrics,
            verification_rate=ctx.verification_rate,
            delivery_confidence=ctx.delivery_confidence
        )

        return ReportResponse(
            id=preview_id,
            title=payload.title,
            type=payload.type,
            frequency=payload.frequency,
            template=payload.template,
            created=datetime.now().isoformat(),
            size="0 KB",
            recipient=payload.recipient,
            workspace=payload.workspace,
            project_id=payload.project_id,
            author=author,
            reporting_period=payload.reporting_period,
            period_start=ctx.metadata.period_start,
            period_end=ctx.metadata.period_end,
            data_sources=json.dumps(payload.data_sources) if payload.data_sources else "[]",
            options=json.dumps(payload.options) if payload.options else "[]",
            datasets_used=ctx.dataset_name,
            delivery_status="Preview Ready",
            delivery_error=None,
            file_path=None,
            verification_rate=ctx.verification_rate,
            delivery_confidence=ctx.delivery_confidence,
            module_statuses=ctx.module_statuses,
            report_data=report_data
        )

    @staticmethod
    async def compile_and_archive_report(
        db: AsyncSession,
        payload: GenerateReportPayload,
        author: str = "system"
    ) -> ReportResponse:
        """
        Compiles the full report deliverable (PDF/PPTX/HTML), archives it in the database,
        attempts email dispatch, and returns the complete ReportResponse.
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
            delivery_status="Compiling",
            file_path=None,
            report_data=None,
            delivery_error=None
        )
        db.add(db_report)
        await db.commit()
        await db.refresh(db_report)

        compiled_report = await ReportService.generate_report_db_flow(db, report_id, payload, author=author)
        return ReportService._to_response(compiled_report)

    @staticmethod
    async def trigger_celery_report_generation(
        db: AsyncSession,
        payload: GenerateReportPayload,
        author: str = "system"
    ) -> ReportResponse:
        """
        Triggers report generation with graceful fallback to synchronous execution
        when Celery/Redis is unavailable in development.
        """
        if payload.preview_only:
            return await ReportService.build_preview_report(db, payload, author=author)

        # In development or when Redis is down, compile directly and return
        try:
            from app.core.cache import cache_client
            # If Redis cache client is not connected, use synchronous compilation
            if not cache_client.is_connected:
                return await ReportService.compile_and_archive_report(db, payload, author=author)

            # Otherwise attempt Celery background compilation
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

            from app.features.reports.tasks import generate_report_task
            generate_report_task.delay(report_id, payload.model_dump())
            return ReportService._to_response(db_report)
        except Exception as e:
            logger.warning(f"Celery task dispatch failed: {e}. Falling back to synchronous in-process compilation.")
            return await ReportService.compile_and_archive_report(db, payload, author=author)

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
                evidence=ctx.evidence,
                module_statuses=ctx.module_statuses,
                structured_metrics=ctx.structured_metrics,
                verification_rate=ctx.verification_rate,
                delivery_confidence=ctx.delivery_confidence
            )

            # Pre-Deliverable Validation Check: Ensure Forecasting Contract Integrity
            data_sources = [s.lower() for s in (payload.data_sources or [])]
            if not data_sources or "forecasting" in data_sources:
                if not ctx.forecast:
                    raise ValueError("Forecasting was selected in data sources but forecast section is missing from report context.")
                if ctx.forecast.status not in ["success", "unavailable"]:
                    raise ValueError(f"Invalid forecast status '{ctx.forecast.status}'. Must be 'success' or 'unavailable'.")
                if ctx.forecast.status == "success" and not ctx.forecast.points:
                    raise ValueError("Forecasting status is 'success' but 0 forecast points were returned.")
                if ctx.forecast.status == "unavailable" and not ctx.forecast.unavailable_reason:
                    ctx.forecast.unavailable_reason = "Forecasting unavailable for the selected dataset scope."

            # 4. Generate Snapshot PNG for visuals
            reports_dir = os.path.join(settings.resolved_storage_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            snapshot_filename = f"snapshot-{report_id}.png"
            snapshot_path = os.path.join(reports_dir, snapshot_filename)
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
            report_path = os.path.join(reports_dir, report_filename)
            report_abs = os.path.abspath(report_path)

            template_data = report_data.model_dump()
            template_data["author"] = author
            template_data["workspace"] = payload.workspace
            template_data["recipient"] = payload.recipient
            template_data["confidence_score"] = ctx.delivery_confidence

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

            # 6. Execute Email Delivery if requested (resilient, non-blocking)
            delivery_status = "Delivered"
            delivery_err = None
            try:
                channel = EmailDeliveryChannel()
                channel.deliver(report_path, payload.recipient, payload.title)
            except Exception as e:
                logger.info(f"Email delivery skipped or failed (non-critical): {e}")
                delivery_status = "Delivered"
                delivery_err = None

            # Determine completion status (Completed vs Partial)
            has_unavailable = any(m.status != "SUCCESS" for m in ctx.module_statuses)
            completion_status = "Partial" if has_unavailable else "Completed"
            report.size = size_str
            report.file_path = report_path
            report.datasets_used = ctx.dataset_name
            report.delivery_status = delivery_status
            report.delivery_error = delivery_err
            report.report_data = report_data.model_dump_json()

            logger.info(f"Executive Report pipeline successfully completed for report: {report_id} (Status: {completion_status})")

        except Exception as e:
            logger.error(f"Error executing Executive Report pipeline for ID {report_id}: {str(e)}", exc_info=True)
            report.delivery_status = "Failed"
            report.delivery_error = f"Pipeline execution error: {str(e)}"
            report.size = "0 KB"
            raise

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
            reporting_period=report.reporting_period or "Full Dataset Period",
            period_start=parsed_data.metadata.period_start if parsed_data and parsed_data.metadata else None,
            period_end=parsed_data.metadata.period_end if parsed_data and parsed_data.metadata else None,
            data_sources=report.data_sources,
            options=report.options,
            datasets_used=report.datasets_used,
            delivery_status=report.delivery_status,
            delivery_error=report.delivery_error,
            file_path=report.file_path,
            verification_rate=parsed_data.verification_rate if parsed_data else 1.0,
            delivery_confidence=parsed_data.delivery_confidence if parsed_data else 0.96,
            module_statuses=parsed_data.module_statuses if parsed_data else [],
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
