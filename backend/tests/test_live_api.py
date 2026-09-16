import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
import httpx
from app.main import app

async def test_api():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("Testing GET /api/v1/reports...")
        r = await client.get("/api/v1/reports")
        print("GET status:", r.status_code)
        reports = r.json()
        print(f"Retrieved {len(reports)} archived reports.")
        if reports:
            print("Latest report:", reports[0].get("title"), "-", reports[0].get("delivery_status"))

        print("\nTesting POST /api/v1/reports/generate (Preview)...")
        payload = {
            "title": "API Test Preview Report",
            "project_id": "proj-43d2ca3d",
            "reporting_period": "Full Dataset Period",
            "template": "Executive Summary",
            "data_sources": ["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
            "type": "PDF",
            "options": ["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
            "recipient": "board@company.com",
            "frequency": "Ad-hoc",
            "preview_only": True
        }
        r = await client.post("/api/v1/reports/generate", json=payload)
        print("PREVIEW status:", r.status_code)
        res = r.json()
        print("Preview delivery_status:", res.get("delivery_status"))
        kpis = res.get("report_data", {}).get("kpi_overview", [])
        print("Preview KPIs:", [(k.get("title"), k.get("current_value")) for k in kpis])

        print("\nTesting POST /api/v1/reports/generate (Compile & Deliver)...")
        payload = {
            "title": "API Test Compile Deliver Report",
            "project_id": "proj-43d2ca3d",
            "reporting_period": "Full Dataset Period",
            "template": "Executive Summary",
            "data_sources": ["dashboard", "sql", "forecasting", "segmentation", "anomaly", "rag"],
            "type": "PDF",
            "options": ["kpis", "charts", "summary", "insights", "impact", "recommendations", "evidence"],
            "recipient": "board@company.com",
            "frequency": "Ad-hoc",
            "preview_only": False
        }
        r = await client.post("/api/v1/reports/generate", json=payload)
        print("COMPILE status:", r.status_code)
        res = r.json()
        print("Compile delivery_status:", res.get("delivery_status"))
        print("Compile file_path:", res.get("file_path"))
        print("Compile verification_rate:", res.get("verification_rate"))
        print("Compile delivery_confidence:", res.get("delivery_confidence"))

        print("\nTesting NO_DATA_IN_PERIOD exception handling...")
        payload = {
            "title": "Out of bounds test",
            "project_id": "proj-43d2ca3d",
            "reporting_period": "Custom Range",
            "custom_date_range": {
                "startDate": "2025-01-01",
                "endDate": "2025-01-31"
            },
            "template": "Executive Summary",
            "data_sources": ["sql"],
            "type": "PDF",
            "options": ["kpis"],
            "recipient": "board@company.com",
            "frequency": "Ad-hoc",
            "preview_only": True
        }
        r = await client.post("/api/v1/reports/generate", json=payload)
        print("OUT OF BOUNDS status:", r.status_code)
        print("OUT OF BOUNDS error:", r.json().get("error", {}).get("code"), "-", r.json().get("error", {}).get("message"))

if __name__ == "__main__":
    asyncio.run(test_api())
