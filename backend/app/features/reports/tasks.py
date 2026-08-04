import asyncio
import logging
from datetime import datetime, timedelta
import uuid

from app.worker import celery_app
from app.core.database import AsyncSessionLocal
from app.features.reports.models import Report, ReportSchedule

import time
from app.core.telemetry import BACKGROUND_TASK_LATENCY

logger = logging.getLogger(__name__)


async def run_generate_report(report_id: str, payload_dict: dict):
    """Executes the async service logic for generating a report inside the worker thread."""
    from app.features.reports.service import ReportService
    from app.features.reports.schemas import GenerateReportPayload
    
    payload = GenerateReportPayload(**payload_dict)
    async with AsyncSessionLocal() as db:
        await ReportService.generate_report_db_flow(db, report_id, payload)


@celery_app.task(name="generate_report_task")
def generate_report_task(report_id: str, payload_dict: dict) -> dict:
    """Asynchronously generates report PDF/PPTX deliverables and commits meta records."""
    logger.info(f"Starting Celery background report compilation for ID: {report_id}")
    start_time = time.perf_counter()
    try:
        asyncio.run(run_generate_report(report_id, payload_dict))
        duration = time.perf_counter() - start_time
        BACKGROUND_TASK_LATENCY.labels(task_name="generate_report_task").observe(duration)
        return {
            "report_id": report_id,
            "status": "completed",
            "recipient": payload_dict.get("recipient"),
        }
    except Exception as e:
        duration = time.perf_counter() - start_time
        BACKGROUND_TASK_LATENCY.labels(task_name="generate_report_task").observe(duration)
        logger.error(f"Celery report generation failed for ID {report_id}: {str(e)}", exc_info=True)
        return {
            "report_id": report_id,
            "status": "failed",
            "error": str(e)
        }


async def run_check_scheduled_reports():
    """Queries DB for active schedules and triggers overdue reports."""
    from sqlalchemy import select, desc
    
    async with AsyncSessionLocal() as db:
        stmt = select(ReportSchedule).where(ReportSchedule.is_active == True)
        result = await db.execute(stmt)
        schedules = result.scalars().all()
        
        now = datetime.now()
        
        for schedule in schedules:
            # Query last report generated under this schedule profile
            report_stmt = select(Report).where(
                Report.workspace == schedule.workspace,
                Report.template == schedule.template,
                Report.recipient == schedule.recipient,
                Report.frequency == schedule.frequency
            ).order_by(desc(Report.created)).limit(1)
            
            report_res = await db.execute(report_stmt)
            last_report = report_res.scalars().first()
            
            should_run = False
            if not last_report:
                should_run = True
                logger.info(f"Schedule '{schedule.title}' has no previous report. Triggering.")
            else:
                try:
                    last_created = datetime.fromisoformat(last_report.created)
                except ValueError:
                    # Fallback to force generation if string parsing is invalid
                    last_created = now - timedelta(days=365)
                
                delta = now - last_created
                
                if schedule.frequency == "Daily" and delta >= timedelta(days=1):
                    should_run = True
                elif schedule.frequency == "Weekly" and delta >= timedelta(weeks=1):
                    should_run = True
                elif schedule.frequency == "Monthly" and delta >= timedelta(days=30):
                    should_run = True
                elif schedule.frequency == "Quarterly" and delta >= timedelta(days=90):
                    should_run = True
            
            if should_run:
                report_id = str(uuid.uuid4())
                payload_dict = {
                    "title": schedule.title,
                    "type": schedule.report_type,
                    "frequency": schedule.frequency,
                    "workspace": schedule.workspace,
                    "template": schedule.template,
                    "recipient": schedule.recipient,
                    "author": schedule.author
                }
                logger.info(f"Triggering scheduled generation for '{schedule.title}' (ID: {report_id})")
                generate_report_task.delay(report_id, payload_dict)


@celery_app.task(name="check_scheduled_reports")
def check_scheduled_reports():
    """Periodic Celery task scanning database schedules and spawning generation tasks."""
    logger.info("Starting Celery scheduled reports check scan...")
    asyncio.run(run_check_scheduled_reports())
