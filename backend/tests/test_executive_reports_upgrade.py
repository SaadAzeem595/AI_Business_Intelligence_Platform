import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_current_user, MockUser
from app.features.reports.schemas import (
    GenerateReportPayload,
    ReportKPICard,
    ReportAnomalyItem,
    ReportForecastSection,
    ReportForecastPoint,
    ReportSegmentItem,
    ReportBusinessImpact,
    ReportRecommendation,
    ReportEvidenceItem,
    ReportMetadata,
    ExecutiveReportData,
    RegenerateNarrativePayload,
)
from app.features.reports.context_builder import (
    ExecutiveReportContextBuilder,
    calculate_date_bounds,
)
from app.features.reports.validator import AntiHallucinationValidator
from app.features.reports.html_generator import HTMLReportGenerator
from app.features.reports.pdf_generator import PDFReportGenerator
from app.features.reports.pptx_generator import PowerPointReportGenerator
from app.features.reports.service import ReportService


def set_test_user(user_id: str = "tester_exec", role: str = "Admin"):
    user = MockUser(
        id=user_id,
        email=f"{user_id}@datapilot.com",
        name="Executive Tester",
        role=role
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return user


# 1. TEST: Date Filtering Bounds
def test_date_bounds_calculation():
    """Verifies date calculation logic for all period types."""
    now = datetime.now()

    start, end = calculate_date_bounds("Last 7 Days")
    assert (end - start).days >= 7

    start, end = calculate_date_bounds("Last 30 Days")
    assert (end - start).days >= 30

    start, end = calculate_date_bounds("Last 90 Days")
    assert (end - start).days >= 90

    start, end = calculate_date_bounds("Last 12 Months")
    assert (end - start).days >= 365

    start, end = calculate_date_bounds("Current Quarter")
    assert start <= now

    start, end = calculate_date_bounds("Custom Range", {"startDate": "2026-01-01", "endDate": "2026-01-15"})
    assert start.year == 2026
    assert start.month == 1
    assert start.day == 1


# 2. TEST: Anti-Hallucination Validator
def test_anti_hallucination_correction():
    """Verifies that mathematical claims in generated text are reconciled with authoritative KPIs."""
    kpis = [
        ReportKPICard(
            title="Total Revenue",
            current_value="$82,400.00",
            previous_value="$74,000.00",
            change_pct="+11.4%",
            direction="up",
            status="positive",
            source="Dashboard KPI",
            source_id="SRC-KPI-1"
        )
    ]
    source_facts = {"revenue_current": 82400.0, "revenue_previous": 74000.0}

    # Model hallucinated Revenue = $87,400 instead of $82,400.00
    hallucinated_sentence = ["Total Revenue expanded rapidly to $87,400 with positive margin gains."]
    validated = AntiHallucinationValidator.validate_and_correct_narrative(hallucinated_sentence, source_facts, kpis)

    assert len(validated) == 1
    # Check that $87,400 was corrected to $82,400.00 and source ID was attached
    assert "$82,400.00" in validated[0]
    assert "SRC-KPI-1" in validated[0]

    # Test missing data fallback
    empty_validated = AntiHallucinationValidator.validate_and_correct_narrative([], {}, [])
    assert "Insufficient data available in the selected sources." in empty_validated[0]


# 3. TEST: HTML Report Generator
def test_html_report_generation():
    """Verifies that HTMLReportGenerator creates a standalone HTML deliverable with all 11 sections."""
    meta = ReportMetadata(
        report_id="rep-test-html",
        title="Q3 Executive Review",
        project_name="Sales Operations",
        reporting_period="Last 30 Days",
        generated_at=datetime.now().strftime("%B %d, %Y"),
        author="tester",
        recipient="exec@company.com",
        confidence_score=0.98,
        sources_included=["Dashboard", "SQL", "Forecasting", "Anomalies", "Segments", "RAG"]
    )
    report_data = ExecutiveReportData(
        metadata=meta,
        executive_summary=["Primary Revenue increased by +12.4% MoM [SRC-KPI-1].", "Anomalies resolved [SRC-ANOM-1]."],
        kpi_overview=[
            ReportKPICard(
                title="Revenue",
                current_value="$1.2M",
                change_pct="+12.4%",
                direction="up",
                status="positive",
                source="Dashboard",
                source_id="SRC-KPI-1"
            )
        ],
        key_insights=[],
        trends_chart={"title": "Trend", "labels": ["Jan", "Feb"], "values": [100, 120], "type": "line", "color": "#4f46e5"},
        anomalies=[],
        segmentation=[],
        business_impact=[],
        recommendations=[],
        evidence=[
            ReportEvidenceItem(
                source_id="SRC-KPI-1",
                category="Dashboard KPI",
                claim="Revenue was $1.2M",
                source_name="DuckDB",
                details="Column revenue"
            )
        ]
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "report.html")
        res = HTMLReportGenerator.generate(out_path, report_data)
        assert os.path.exists(res)
        assert os.path.getsize(res) > 0
        with open(res, "r", encoding="utf-8") as f:
            html = f.read()
            assert "Q3 Executive Review" in html
            assert "Executive Summary" in html
            assert "Key Performance Indicators" in html
            assert "SRC-KPI-1" in html


# 4. TEST: PDF & PPTX Generation with Extended Data
def test_pdf_and_pptx_with_executive_data():
    """Verifies PDF and PPTX compilers handle new 11-section structured dictionaries."""
    data = {
        "author": "Executive Tester",
        "workspace": "sales",
        "recipient": "board@company.com",
        "confidence_score": 0.97,
        "executive_summary": ["Quarterly revenue growth reached +14.2% MoM [SRC-KPI-1]."],
        "kpi_overview": [
            {"title": "Gross Bookings", "current_value": "$1.5M", "change_pct": "+14.2%", "direction": "up", "status": "positive", "source_id": "SRC-KPI-1"}
        ],
        "key_insights": [
            {"title": "High Margin Expansion", "description": "Operating margin rose to 28%.", "severity": "High", "supporting_metric": "+5.2%"}
        ],
        "anomalies": [
            {"metric": "Revenue Outlier", "affected_date": "2026-08-15", "severity": "High", "deviation": "+3.1 Std Dev", "baseline": "$50,000"}
        ],
        "forecast": {
            "predictions": [{"date": "2026-09-01", "value": 7800.0, "lower": 7200.0, "upper": 8400.0}]
        },
        "segmentation": [
            {"name": "Enterprise Tier", "size": 120, "size_pct": "35%", "avg_spent": "$4,500", "risk_rating": "Low"}
        ],
        "recommendations": [
            {"recommendation": "Expand tier 1 account retention program.", "priority": "High", "suggested_owner": "Customer Success"}
        ],
        "evidence": [
            {"source_id": "SRC-KPI-1", "category": "Dashboard", "claim": "Revenue was $1.5M", "source_name": "DB", "details": "Table sales"}
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. PDF
        pdf_path = os.path.join(tmpdir, "exec_report.pdf")
        PDFReportGenerator.generate(pdf_path, "Executive Audit", "Executive Summary", data)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0

        # 2. PPTX
        pptx_path = os.path.join(tmpdir, "exec_report.pptx")
        PowerPointReportGenerator.generate(pptx_path, "Executive Audit", "Executive Summary", data)
        assert os.path.exists(pptx_path)
        assert os.path.getsize(pptx_path) > 0


# 5. INTEGRATION TEST: Multi-module Context Builder
@pytest.mark.anyio
async def test_context_builder_execution():
    """Verifies that the context builder aggregates all modules into a coherent context."""
    async with AsyncSessionLocal() as db:
        payload = GenerateReportPayload(
            title="Comprehensive Multi-Module Report",
            type="HTML",
            reporting_period="Last 30 Days",
            data_sources=["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
            recipient="test@datapilot.com"
        )

        ctx = await ExecutiveReportContextBuilder.build_context(payload, db, author="test_runner")
        assert ctx is not None
        assert len(ctx.kpis) > 0
        assert ctx.kpis[0].source_id.startswith("SRC-KPI")
        assert len(ctx.evidence) > 0
        assert any(e.category == "Dashboard KPI" for e in ctx.evidence)
        assert ctx.chart_data is not None
        assert len(ctx.chart_data.get("labels", [])) > 0


# 6. E2E INTEGRATION TEST: Report Generation Pipeline & API
def test_e2e_report_generation_pipeline_api():
    """Verifies complete end-to-end report generation pipeline via REST API."""
    set_test_user("exec_admin", "Admin")
    client = TestClient(app)

    payload = {
        "title": "E2E Strategic Executive Intelligence Report",
        "type": "PDF",
        "frequency": "Ad-hoc",
        "template": "Executive Summary",
        "reporting_period": "Last 30 Days",
        "data_sources": ["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
        "options": ["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
        "recipient": "board@datapilot.com"
    }

    # 1. Trigger generate report
    with patch("app.features.reports.tasks.generate_report_task.delay") as mock_delay, \
         patch("app.core.cache.cache_client.is_connected", True):
        resp = client.post("/api/v1/reports/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["title"] == payload["title"]
        report_id = data["id"]
        mock_delay.assert_called_once()

    # 2. Get report detail
    detail_resp = client.get(f"/api/v1/reports/{report_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == report_id

    # 3. List reports with filters
    list_resp = client.get("/api/v1/reports?report_type=PDF&page=1&page_size=10")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == report_id for item in items)

    # 4. Clean up / Delete report
    del_resp = client.delete(f"/api/v1/reports/{report_id}")
    assert del_resp.status_code == 200
