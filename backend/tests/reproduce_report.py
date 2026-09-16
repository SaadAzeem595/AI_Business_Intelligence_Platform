import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
import traceback
import uuid
from datetime import datetime
from app.features.auth.models import User
from app.features.projects.models import Project
from app.features.datasets.models import Dataset
from app.features.reports.models import Report
from app.core.database import AsyncSessionLocal
from app.features.reports.schemas import GenerateReportPayload
from app.features.reports.service import ReportService

payload = GenerateReportPayload(
    title="Executive Intelligence & Performance Report",
    project_id="proj-43d2ca3d",
    reporting_period="Last 30 Days",
    template="Executive Summary",
    data_sources=["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
    type="PDF",
    options=["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
    recipient="board@company.com",
    frequency="Ad-hoc",
    workspace="default"
)

async def test():
    async with AsyncSessionLocal() as session:
        report_id = str(uuid.uuid4())
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
            author="dev_user",
            template=payload.template,
            reporting_period=payload.reporting_period,
            data_sources='["dashboard","sql","forecasting","segmentation","anomaly","rag"]',
            options='["kpis","charts","summary","insights","impact","recommendations","evidence"]',
            delivery_status="Pending"
        )
        session.add(db_report)
        await session.commit()
        print(f"Report stub created: {report_id}")
        try:
            res = await ReportService.generate_report_db_flow(session, report_id, payload, "dev_user")
            print("SUCCESS generate_report_db_flow:", res.delivery_status)
            print("Delivery error:", res.delivery_error)
            print("File path:", res.file_path)
        except Exception as e:
            print("EXCEPTION IN generate_report_db_flow:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
