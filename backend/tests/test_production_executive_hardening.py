import os
import json
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user, MockUser
from app.features.reports.schemas import (
    GenerateReportPayload,
    ReportKPICard,
    ExecutiveReportData,
    ReportMetadata,
    RegenerateNarrativePayload,
)
from app.features.reports.context_builder import ExecutiveReportContextBuilder
from app.features.reports.validator import ReportValidationEngine, ReportValidationError
from app.features.reports.service import ReportService
from app.core.database import AsyncSessionLocal


def create_user(user_id: str, workspace_id: str, role: str = "Admin") -> MockUser:
    return MockUser(
        id=user_id,
        email=f"{user_id}@test.com",
        name=f"User {user_id}",
        workspace_id=workspace_id,
        role=role,
    )


# ---------------------------------------------------------------------------
# TEST A: Authentication & Workspace Isolation on Report Deliverable Endpoints
# ---------------------------------------------------------------------------
def test_unauthenticated_and_workspace_isolation():
    from app.core.config import settings
    import app.core.dependencies as deps
    old_bypass = settings.DEV_AUTH_BYPASS
    old_testing = deps.IS_TESTING
    settings.DEV_AUTH_BYPASS = False
    deps.IS_TESTING = False
    try:
        client = TestClient(app)

        # 1. Unauthenticated request must return 401
        app.dependency_overrides.pop(get_current_user, None)
        res_401 = client.get("/api/v1/reports/any-report-id/download?format=pdf")
        assert res_401.status_code == 401, f"Expected 401, got {res_401.status_code}"

        res_pdf_401 = client.get("/api/v1/reports/any-report-id/pdf")
        assert res_pdf_401.status_code == 401

        res_pptx_401 = client.get("/api/v1/reports/any-report-id/pptx")
        assert res_pptx_401.status_code == 401

        res_html_401 = client.get("/api/v1/reports/any-report-id/html")
        assert res_html_401.status_code == 401
    finally:
        settings.DEV_AUTH_BYPASS = old_bypass
        deps.IS_TESTING = old_testing


@pytest.mark.anyio
async def test_end_to_end_preview_and_authenticated_exports():
    """Tests preview creation, DB persistence, validation, and PDF/PPTX/HTML downloads."""
    user_a = create_user("owner_a", "workspace_alpha", "Admin")
    app.dependency_overrides[get_current_user] = lambda: user_a

    client = TestClient(app)

    # 1. Generate a preview report with real Olist/analytics context
    payload = {
        "title": "Q3 Executive Performance & Intelligence Brief",
        "template": "Executive Summary",
        "reporting_period": "Full Dataset Period",
        "status_filter": "Delivered",
        "data_sources": ["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
        "options": ["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
        "preview_only": True,
        "recipient": "executives@company.com",
        "frequency": "Ad-hoc"
    }

    res = client.post("/api/v1/reports/generate", json=payload)
    assert res.status_code == 200, f"Generate failed: {res.text}"
    report_data = res.json()
    report_id = report_data["id"]

    assert report_id.startswith("preview-")
    assert report_data["delivery_status"] == "Preview Ready"
    assert report_data["workspace"] == "workspace_alpha"

    # Verify real metrics were generated (not hardcoded placeholders or zeros)
    rd = report_data["report_data"]
    kpis = rd["kpi_overview"]
    assert len(kpis) == 4

    rev_kpi = next(k for k in kpis if "revenue" in k["title"].lower())
    orders_kpi = next(k for k in kpis if "orders" in k["title"].lower())

    # Ensure values are not $0.00 or 0
    assert rev_kpi["current_value"] not in ["$0.00", "$0", "0"]
    assert orders_kpi["current_value"] not in ["0", "0.0"]

    # Verify no fabricated percentage on Full Dataset Period baseline
    assert rev_kpi["change_pct"] in ["Full period baseline", "Baseline period", "0.0%"]

    # Verify forecasting
    fc = rd.get("forecast")
    assert fc is not None
    assert fc["status"] in ["success", "unavailable"]
    if fc["status"] == "success":
        assert len(fc["points"]) > 0
        assert fc["model_used"] != ""

    # Verify segmentation
    segments = rd.get("segmentation")
    assert len(segments) > 0

    # Verify anomalies
    anomalies = rd.get("anomalies")
    assert isinstance(anomalies, list)

    # 2. Authenticated PDF download for Owner A
    res_pdf = client.get(f"/api/v1/reports/{report_id}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000  # Non-empty valid PDF binary

    # 3. Authenticated PPTX download for Owner A
    res_pptx = client.get(f"/api/v1/reports/{report_id}/pptx")
    assert res_pptx.status_code == 200
    assert "presentation" in res_pptx.headers["content-type"]
    assert len(res_pptx.content) > 1000

    # 4. Authenticated HTML download for Owner A
    res_html = client.get(f"/api/v1/reports/{report_id}/html")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert len(res_html.content) > 500

    # 5. Wrong Workspace Isolation: User B from workspace_beta must receive 403
    user_b = create_user("attacker_b", "workspace_beta", "Admin")
    app.dependency_overrides[get_current_user] = lambda: user_b

    res_forbidden_get = client.get(f"/api/v1/reports/{report_id}")
    assert res_forbidden_get.status_code == 403

    res_forbidden_pdf = client.get(f"/api/v1/reports/{report_id}/pdf")
    assert res_forbidden_pdf.status_code == 403


# ---------------------------------------------------------------------------
# TEST B: 15-Rule Report Validation Engine
# ---------------------------------------------------------------------------
def test_validation_engine_integrity_rules():
    """Validates that the 15-rule ReportValidationEngine catches invalid reports."""
    # Test Rule 9: Fabricated percentage with 0 value
    bad_kpis = [
        ReportKPICard(
            title="Total Revenue",
            current_value="$0.00",
            previous_value="$0.00",
            change_pct="+13.6%",  # Fabricated!
            direction="up",
            status="positive",
            source="Test",
            source_id="SRC-KPI-1"
        )
    ]
    meta = ReportMetadata(
        report_id="test-1",
        title="Test Report",
        project_name="P1",
        reporting_period="Last 30 Days",
        period_start="Jan 01, 2026",
        period_end="Jan 30, 2026",
        generated_at="Jan 30, 2026",
        author="tester",
        recipient="executives@company.com",
        confidence_score=0.95,
        verification_rate=1.0,
    )
    mock_data = ExecutiveReportData(
        metadata=meta,
        executive_summary=["Overall performance $0.00 [SRC-KPI-1]."],
        kpi_overview=bad_kpis,
        key_insights=[],
        trends_chart={"labels": ["Jan"], "values": [0.0]},
        anomalies=[],
        segmentation=[],
        business_impact=[],
        recommendations=[],
        evidence=[]
    )

    with pytest.raises(ReportValidationError) as exc_info:
        ReportValidationEngine.validate(mock_data)
    assert exc_info.value.rule_id == 9

    # Test Rule 12: Unsupported business claim (Operating margins when no margin KPI exists)
    good_kpis = [
        ReportKPICard(
            title="Total Orders",
            current_value="1,200",
            previous_value="1,000",
            change_pct="+20.0%",
            direction="up",
            status="positive",
            source="Test",
            source_id="SRC-KPI-1"
        )
    ]
    bad_summary_data = ExecutiveReportData(
        metadata=meta,
        executive_summary=["Operating margins maintain stability at 1,200 [SRC-KPI-1]."],  # Hallucinated margin claim!
        kpi_overview=good_kpis,
        key_insights=[],
        trends_chart={"labels": ["Jan"], "values": [1200.0]},
        anomalies=[],
        segmentation=[],
        business_impact=[],
        recommendations=[],
        evidence=[]
    )
    with pytest.raises(ReportValidationError) as exc_info2:
        ReportValidationEngine.validate(bad_summary_data)
    assert exc_info2.value.rule_id == 12
