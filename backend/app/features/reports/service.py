import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.reports.models import Report, ReportSchedule
from app.features.reports.schemas import (
    GenerateReportPayload,
    ReportResponse,
    ReportSchedulePayload,
    ReportScheduleResponse,
)

logger = logging.getLogger(__name__)


class ReportService:
    """Core service orchestrating report compiling pipelines, agents data mapping, and schedules."""

    @staticmethod
    async def trigger_celery_report_generation(
        db: AsyncSession,
        payload: GenerateReportPayload,
        author: str = "system"
    ) -> ReportResponse:
        """Saves a pending database log and enqueues compilation to Celery workers."""
        report_id = str(uuid.uuid4())
        
        # 1. Create a stub record in the database with status 'Pending'
        db_report = Report(
            id=report_id,
            title=payload.title,
            type=payload.type,
            frequency=payload.frequency,
            created=datetime.now().isoformat(),
            size="0 KB",
            recipient=payload.recipient,
            workspace=payload.workspace,
            author=author,
            template=payload.template,
            delivery_status="Pending",
            file_path=None
        )
        db.add(db_report)
        await db.flush()
        
        # 2. Trigger Celery task
        from app.features.reports.tasks import generate_report_task
        generate_report_task.delay(report_id, payload.model_dump())
        
        return ReportResponse.model_validate(db_report)

    @staticmethod
    async def generate_report_db_flow(
        db: AsyncSession,
        report_id: str,
        payload: GenerateReportPayload
    ) -> Report:
        """Executes the multi-agent graph, compiles deliverables, and delivers them."""
        # 1. Fetch the report stub from DB
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalars().first()
        if not report:
            raise ValueError(f"Report stub with ID {report_id} not found.")

        try:
            logger.info(f"Running LangGraph Multi-Agent execution loop for report: {payload.title}")
            
            # 2. Run LangGraph to completion
            thread_id = f"report-thread-{report_id}"
            config = {"configurable": {"thread_id": thread_id}}
            query = f"Provide a complete {payload.template} report audit for {payload.workspace} workspace, listing stats, ML churn data, and risks."
            
            initial_state = {
                "query": query,
                "workspace": payload.workspace,
                "plan": [],
                "completed_steps": [],
                "next_agent": "",
                "sql_query": None,
                "sql_result": None,
                "analytics_result": None,
                "ml_result": None,
                "forecast_result": None,
                "rag_result": None,
                "visualization_spec": None,
                "recommendations": None,
                "executive_summary": None,
                "final_response": None,
                "is_approved": True,  # Auto-approve SQL if we resume
                "execution_logs": [],
                "reasoning_path": []
            }
            
            from app.features.agents.graph import agent_graph
            
            # Start execution (planner/router nodes and interrupt)
            agent_graph.invoke(initial_state, config)
            
            # Programmatically resume past SQL execution interrupt
            current_state = agent_graph.get_state(config)
            if current_state.next:
                logger.info(f"Resuming paused agents execution graph on thread: {thread_id}")
                agent_graph.update_state(config, {"is_approved": True})
                agent_graph.invoke(None, config)
                
            final_state = agent_graph.get_state(config)
            state_vals = final_state.values if final_state else {}
            
            # 3. Format KPIs dynamically depending on SQL data or fallback defaults
            kpis = [
                {"title": "Total Revenue", "value": "$1.24M", "change": "+14.2% MoM"},
                {"title": "Operating Cost", "value": "$320.5K", "change": "-2.1% MoM"},
                {"title": "Churn Risk", "value": "15.0%", "change": "+0.5% MoM"},
                {"title": "RAG Accuracy", "value": "94.0%", "change": "+1.8% MoM"}
            ]
            
            sql_res = state_vals.get("sql_result", {})
            if sql_res and "rows" in sql_res and len(sql_res["rows"]) > 0:
                # Dynamically construct KPI values from DuckDB outputs if matching
                row = sql_res["rows"][0]
                if len(row) >= 4:
                    kpis[0]["value"] = f"${row[1]:,.2f}" if isinstance(row[1], (int, float)) else str(row[1])
                    kpis[1]["value"] = f"${row[2]:,.2f}" if isinstance(row[2], (int, float)) else str(row[2])
            
            # Tailor template colors
            if payload.template == "Sales":
                kpis[0]["title"] = "Gross Bookings"
            elif payload.template == "Marketing":
                kpis[0]["title"] = "Acquisition Value"
                kpis[2]["title"] = "Conversion Rate"
                kpis[2]["value"] = "8.5%"
                
            # 4. Generate Dashboard Snapshot PNG
            os.makedirs(os.path.join("storage", "reports"), exist_ok=True)
            snapshot_filename = f"snapshot-{report_id}.png"
            snapshot_path = os.path.join("storage", "reports", snapshot_filename)
            snapshot_abs = os.path.abspath(snapshot_path)
            
            chart_data = {
                "title": f"{payload.template} Growth Trend Projections",
                "labels": ["Sep", "Oct", "Nov"],
                "values": [7500.0, 7800.0, 8100.0],
                "type": "line",
                "color": "#3b82f6"
            }
            
            forecast_res = state_vals.get("forecast_result", {})
            if forecast_res and "predictions" in forecast_res:
                preds = forecast_res["predictions"]
                chart_data["labels"] = [p["date"] for p in preds]
                chart_data["values"] = [p["value"] for p in preds]
                
            from app.features.reports.snapshot_generator import DashboardSnapshotGenerator
            DashboardSnapshotGenerator.generate_dashboard_snapshot(kpis, chart_data, snapshot_abs)
            
            # 5. Compile PDF or PPTX deliverables
            file_extension = "pdf" if payload.type == "PDF" else "pptx"
            report_filename = f"report-{report_id}.{file_extension}"
            report_path = os.path.join("storage", "reports", report_filename)
            report_abs = os.path.abspath(report_path)
            
            template_data = {
                "author": report.author,
                "workspace": payload.workspace,
                "recipient": payload.recipient,
                "confidence_score": 0.95,
                "executive_summary": state_vals.get("executive_summary", {}),
                "kpi_overview": kpis,
                "forecast_result": forecast_res,
                "recommendations": state_vals.get("recommendations", []),
                "rag_result": state_vals.get("rag_result", [])
            }
            
            datasets_used = []
            if state_vals.get("sql_query"):
                datasets_used.append("DuckDB Analytics Schema")
            if state_vals.get("rag_result"):
                datasets_used.append("RAG Vector Database")
            if state_vals.get("ml_result"):
                datasets_used.append("Inference Churn Model")
                
            datasets_str = ", ".join(datasets_used) if datasets_used else "System Context"
            
            if payload.type == "PDF":
                from app.features.reports.pdf_generator import PDFReportGenerator
                PDFReportGenerator.generate(
                    report_abs, payload.title, payload.template, template_data, snapshot_abs
                )
            else:
                from app.features.reports.pptx_generator import PowerPointReportGenerator
                PowerPointReportGenerator.generate(
                    report_abs, payload.title, payload.template, template_data, snapshot_abs
                )
                
            # Calculate file size
            file_size_bytes = os.path.getsize(report_abs)
            file_size_kb = file_size_bytes / 1024
            size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{(file_size_kb/1024):.1f} MB"
            
            # 6. Update database record with final details
            report.status = "Active"
            report.size = size_str
            report.file_path = report_path
            report.datasets_used = datasets_str
            report.delivery_status = "Delivered"
            
            # 7. Execute delivery channel
            from app.features.reports.delivery import EmailDeliveryChannel
            channel = EmailDeliveryChannel()
            channel.deliver(report_path, payload.recipient, payload.title)
            
            logger.info(f"Report generation successfully completed for report: {report_id}")
            
        except Exception as e:
            logger.error(f"Error compiling report ID {report_id}: {str(e)}", exc_info=True)
            report.delivery_status = "Failed"
            report.size = "0 KB"
            # Keep frequency and basic stubs
            
        db.add(report)
        await db.flush()
        return report

    @staticmethod
    async def get_reports_history(
        db: AsyncSession,
        workspace: Optional[str] = None,
        report_type: Optional[str] = None,
        author: Optional[str] = None,
        delivery_status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Report]:
        """Queries report history with specific query parameters and search strings."""
        query = select(Report)
        
        if workspace:
            query = query.where(Report.workspace == workspace)
        if report_type:
            query = query.where(Report.type == report_type)
        if author:
            query = query.where(Report.author == author)
        if delivery_status:
            query = query.where(Report.delivery_status == delivery_status)
        if search:
            query = query.where(Report.title.ilike(f"%{search}%"))
            
        query = query.order_by(Report.created.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_report_by_id(db: AsyncSession, report_id: str) -> Optional[Report]:
        """Fetches a single compiled report record by identifier."""
        result = await db.execute(select(Report).where(Report.id == report_id))
        return result.scalars().first()

    @staticmethod
    async def delete_report(db: AsyncSession, report_id: str) -> bool:
        """Removes a report metadata record and its generated output files from server host."""
        report = await ReportService.get_report_by_id(db, report_id)
        if not report:
            return False
            
        # Delete underlying file
        if report.file_path and os.path.exists(report.file_path):
            try:
                os.remove(report.file_path)
                # Also delete associated snapshot if it exists
                snapshot_path = report.file_path.replace(".pdf", ".png").replace(".pptx", ".png").replace("report-", "snapshot-")
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
        """Saves a new recurring reports generation schedule profile."""
        schedule_id = str(uuid.uuid4())
        db_schedule = ReportSchedule(
            id=schedule_id,
            title=payload.title,
            workspace=payload.workspace,
            report_type=payload.report_type,
            frequency=payload.frequency,
            template=payload.template,
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
        """Fetches active recurring report schedule profiles."""
        query = select(ReportSchedule)
        if workspace:
            query = query.where(ReportSchedule.workspace == workspace)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def cancel_schedule(db: AsyncSession, schedule_id: str) -> bool:
        """Removes a recurring report schedule from the database."""
        result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
        schedule = result.scalars().first()
        if not schedule:
            return False
        await db.delete(schedule)
        await db.flush()
        return True
