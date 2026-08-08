import os
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import AsyncSessionLocal
from app.features.reports.models import Report, ReportSchedule
from app.features.reports.schemas import GenerateReportPayload, ReportSchedulePayload
from app.features.reports.service import ReportService
from app.features.reports.snapshot_generator import DashboardSnapshotGenerator
from app.features.reports.pdf_generator import PDFReportGenerator
from app.features.reports.pptx_generator import PowerPointReportGenerator
from app.features.reports.tasks import check_scheduled_reports, generate_report_task, run_check_scheduled_reports





@pytest.fixture(scope="module")
def sample_kpis():
    return [
        {"title": "Test KPI 1", "value": "$100K", "change": "+5.0% MoM"},
        {"title": "Test KPI 2", "value": "1,200", "change": "-2.4% MoM"},
        {"title": "Test KPI 3", "value": "95.5%", "change": "+1.2% MoM"}
    ]


@pytest.fixture(scope="module")
def sample_chart_data():
    return {
        "title": "Performance Over Time",
        "labels": ["Jan", "Feb", "Mar"],
        "values": [120, 150, 180],
        "type": "line",
        "color": "#1e3a8a"
    }


# 1. UNIT TESTS: Dashboard Snapshot & Rendering Generators
def test_dashboard_snapshot_rendering(sample_kpis, sample_chart_data):
    """Verifies that the dashboard snapshot generator renders clean PNG graphs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "snapshot.png")
        
        # Test standalone card
        card_path = os.path.join(tmpdir, "card.png")
        DashboardSnapshotGenerator.generate_kpi_card("Metric", "$50M", "+12%", card_path)
        assert os.path.exists(card_path)
        assert os.path.getsize(card_path) > 0
        
        # Test standalone chart
        chart_path = os.path.join(tmpdir, "chart.png")
        DashboardSnapshotGenerator.generate_trend_chart("Trend", ["A", "B"], [10, 20], chart_path, "bar")
        assert os.path.exists(chart_path)
        assert os.path.getsize(chart_path) > 0
        
        # Test combined snapshot panel
        res_path = DashboardSnapshotGenerator.generate_dashboard_snapshot(
            sample_kpis, sample_chart_data, filepath
        )
        assert res_path == filepath
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0


def test_pdf_generation(sample_kpis):
    """Verifies that the PDF generator compiles ReportLab cover pages and tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "report.pdf")
        snapshot_path = os.path.join(tmpdir, "dummy_snap.png")
        
        # Create a dummy snapshot file
        DashboardSnapshotGenerator.generate_kpi_card("Dummy", "10", "+1%", snapshot_path)
        
        data = {
            "author": "Test Author",
            "workspace": "sales",
            "recipient": "exec@company.com",
            "confidence_score": 0.98,
            "executive_summary": {
                "key_takeaways": ["Insight 1", "Insight 2"]
            },
            "kpi_overview": sample_kpis,
            "forecast_result": {
                "predictions": [{"date": "2026-12-01", "value": 9000.0, "lower": 8000.0, "upper": 10000.0}]
            },
            "recommendations": [{"insight": "Risk high", "priority": "High", "confidence_score": 0.9}],
            "rag_result": [{"citation": {"filename": "doc.pdf", "page": 2, "heading": "Intro"}, "text": "ref text"}]
        }
        
        PDFReportGenerator.generate(
            pdf_path, "CEO Strategic Report", "CEO", data, snapshot_path
        )
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


def test_powerpoint_generation(sample_kpis):
    """Verifies python-pptx slideshow structure layout compilation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pptx_path = os.path.join(tmpdir, "slides.pptx")
        snapshot_path = os.path.join(tmpdir, "dummy_snap.png")
        
        # Create a dummy snapshot file
        DashboardSnapshotGenerator.generate_kpi_card("Dummy", "10", "+1%", snapshot_path)
        
        data = {
            "author": "Test Designer",
            "workspace": "finance",
            "recipient": "finance@company.com",
            "confidence_score": 0.92,
            "executive_summary": {
                "key_takeaways": ["Core profit increase", "Stable expense trend"]
            },
            "kpi_overview": sample_kpis,
            "recommendations": [{"insight": "Allocate marketing cash", "priority": "Medium", "confidence_score": 0.85}]
        }
        
        PowerPointReportGenerator.generate(
            pptx_path, "Finance Quarter Review", "Finance", data, snapshot_path
        )
        assert os.path.exists(pptx_path)
        assert os.path.getsize(pptx_path) > 0


# 2. INTEGRATION TESTS: Database Operations & Service Orchestration
@pytest.mark.anyio
async def test_report_service_lifecycle():
    """Tests the database creation, retrieval, file system paths, and deletes."""
    async with AsyncSessionLocal() as db:
        payload = GenerateReportPayload(
            title="Q3 Sales Projections Audit",
            type="PDF",
            frequency="Ad-hoc",
            workspace="sales",
            template="Sales",
            recipient="test@example.com"
        )
        
        # Mock Celery delay to avoid trigger queue in unit test
        with patch("app.features.reports.tasks.generate_report_task.delay") as mock_celery:
            resp = await ReportService.trigger_celery_report_generation(db, payload, author="tester")
            assert resp.id is not None
            assert resp.title == "Q3 Sales Projections Audit"
            assert resp.workspace == "sales"
            assert resp.delivery_status == "Pending"
            mock_celery.assert_called_once()
            
            # Retrieve from DB
            db_report = await ReportService.get_report_by_id(db, resp.id)
            assert db_report is not None
            assert db_report.author == "tester"
            
            # Execute worker compilation flow synchronously (mocking LLM details)
            await ReportService.generate_report_db_flow(db, resp.id, payload)
            
            # Refresh from DB
            db_report_refreshed = await ReportService.get_report_by_id(db, resp.id)
            assert db_report_refreshed.status == "Active"
            assert db_report_refreshed.delivery_status == "Delivered"
            assert db_report_refreshed.file_path is not None
            assert os.path.exists(db_report_refreshed.file_path)
            
            # Fetch report history with filters
            history = await ReportService.get_reports_history(
                db, workspace="sales", report_type="PDF"
            )
            assert len(history) > 0
            assert any(h.id == resp.id for h in history)
            
            # Cleanup / Delete report
            success = await ReportService.delete_report(db, resp.id)
            assert success is True
            assert not os.path.exists(db_report_refreshed.file_path)


# 3. SCHEDULER TESTS: Celery Beat periodic routines trigger
@pytest.mark.anyio
async def test_scheduler_scanning_logic():
    """Verifies that check_scheduled_reports schedules overdue generation tasks."""
    async with AsyncSessionLocal() as db:
        # Create a sample schedule
        schedule_payload = ReportSchedulePayload(
            title="CEO Morning Scan Review",
            workspace="marketing",
            report_type="PowerPoint",
            frequency="Daily",
            template="CEO",
            recipient="ceo@company.com"
        )
        schedule = await ReportService.create_schedule(db, schedule_payload, author="admin")
        assert schedule.id is not None
        assert schedule.is_active is True
        
        # Test schedule scans and trigger delay tasks
        with patch("app.features.reports.tasks.generate_report_task.delay") as mock_delay:
            # First trigger (no last report generated)
            await run_check_scheduled_reports()
            mock_delay.assert_called_once()
            
            # Clear mock
            mock_delay.reset_mock()
            
            # Simulate a recently generated report to ensure it doesn't trigger again within same day
            report = Report(
                id="rec-report-123",
                title=schedule.title,
                type=schedule.report_type,
                frequency=schedule.frequency,
                created=pytest.importorskip("datetime").datetime.now().isoformat(),
                size="450 KB",
                recipient=schedule.recipient,
                workspace=schedule.workspace,
                author=schedule.author,
                template=schedule.template,
                delivery_status="Delivered"
            )
            db.add(report)
            await db.flush()
            
            # Scan again - should NOT trigger since last report is brand new
            await run_check_scheduled_reports()
            mock_delay.assert_not_called()
            
        # Cleanup schedule
        await ReportService.cancel_schedule(db, schedule.id)
        await db.delete(report)


# 4. REST API ROUTES TESTS: Swagger / Router checkpoints
def test_reports_api_routes():
    """Verify routing, status codes, payload validations, and downloads."""
    client = TestClient(app)
    
    # Authenticate or bypass mock user
    # 1. Trigger generate
    payload = {
        "title": "Marketing Report Analytics",
        "type": "PDF",
        "frequency": "Ad-hoc",
        "workspace": "marketing",
        "template": "Marketing",
        "recipient": "marketing@company.com"
    }
    
    with patch("app.features.reports.tasks.generate_report_task.delay") as mock_celery:
        response = client.post("/api/v1/reports/generate", json=payload)
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["id"] is not None
        assert resp_json["title"] == "Marketing Report Analytics"
        report_id = resp_json["id"]
        
    # 2. Get report history list
    list_resp = client.get("/api/v1/reports?workspace=marketing")
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert len(list_json) > 0
    assert any(l["id"] == report_id for l in list_json)
    
    # 3. Create schedule
    schedule_payload = {
        "title": "Marketing Weekly Newsletter Review",
        "workspace": "marketing",
        "report_type": "PDF",
        "frequency": "Weekly",
        "template": "Marketing",
        "recipient": "marketing@company.com"
    }
    sched_resp = client.post("/api/v1/reports/schedule", json=schedule_payload)
    assert sched_resp.status_code == 200
    sched_json = sched_resp.json()
    schedule_id = sched_json["id"]
    
    # 4. List schedules
    list_sched_resp = client.get("/api/v1/reports/schedules/list?workspace=marketing")
    assert list_sched_resp.status_code == 200
    assert len(list_sched_resp.json()) > 0
    
    # 5. Cancel schedule
    cancel_resp = client.delete(f"/api/v1/reports/schedules/{schedule_id}")
    assert cancel_resp.status_code == 200
    
    # Delete report record
    del_resp = client.delete(f"/api/v1/reports/{report_id}")
    assert del_resp.status_code == 200
