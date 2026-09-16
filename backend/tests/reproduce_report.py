import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
import traceback
from app.features.auth.models import User
from app.features.projects.models import Project
from app.features.datasets.models import Dataset
from app.features.reports.models import Report
from app.core.database import AsyncSessionLocal
from app.features.reports.schemas import GenerateReportPayload
from app.features.reports.service import ReportService

async def test():
    async with AsyncSessionLocal() as session:
        print("\n--- TEST 1: Full Dataset Period (Preview) ---")
        payload_preview = GenerateReportPayload(
            title="Executive Intelligence & Performance Report (Preview)",
            project_id="proj-43d2ca3d",
            reporting_period="Full Dataset Period",
            template="Executive Summary",
            data_sources=["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
            type="PDF",
            options=["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
            recipient="board@company.com",
            frequency="Ad-hoc",
            workspace="default",
            preview_only=True
        )
        res_prev = await ReportService.trigger_celery_report_generation(session, payload_preview, "dev_user")
        print("PREVIEW STATUS:", res_prev.delivery_status)
        print("PREVIEW KPIs:", [(k.title, k.current_value) for k in (res_prev.report_data.kpi_overview if res_prev.report_data else [])])
        print("MODULE STATUSES:", [(m.module, m.status, m.duration_ms) for m in (res_prev.module_statuses or [])])

        print("\n--- TEST 2: Full Dataset Period (Compile & Deliver) ---")
        payload_compile = GenerateReportPayload(
            title="Executive Intelligence & Performance Report",
            project_id="proj-43d2ca3d",
            reporting_period="Full Dataset Period",
            template="Executive Summary",
            data_sources=["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
            type="PDF",
            options=["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
            recipient="board@company.com",
            frequency="Ad-hoc",
            workspace="default",
            preview_only=False
        )
        res_comp = await ReportService.trigger_celery_report_generation(session, payload_compile, "dev_user")
        print("COMPILE STATUS:", res_comp.delivery_status)
        print("COMPILE FILE:", res_comp.file_path)
        print("VERIFICATION RATE:", res_comp.verification_rate)
        print("DELIVERY CONFIDENCE:", res_comp.delivery_confidence)

        print("\n--- TEST 3: Relative 'Last 30 Days' (from dataset max date) ---")
        payload_last30 = GenerateReportPayload(
            title="Executive Intelligence - Last 30 Days",
            project_id="proj-43d2ca3d",
            reporting_period="Last 30 Days",
            template="Executive Summary",
            data_sources=["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
            type="PDF",
            options=["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
            recipient="board@company.com",
            frequency="Ad-hoc",
            workspace="default",
            preview_only=False
        )
        res_last30 = await ReportService.trigger_celery_report_generation(session, payload_last30, "dev_user")
        print("LAST 30 DAYS STATUS:", res_last30.delivery_status)
        print("LAST 30 DAYS PERIOD:", res_last30.period_start, "to", res_last30.period_end)
        print("LAST 30 DAYS KPIs:", [(k.title, k.current_value) for k in (res_last30.report_data.kpi_overview if res_last30.report_data else [])])

if __name__ == "__main__":
    asyncio.run(test())
