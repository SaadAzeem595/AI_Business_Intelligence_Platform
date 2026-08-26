import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.anyio
async def test_cors_preflight_and_anomaly_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as ac:
        # 1. Test OPTIONS preflight request from Next.js origin (http://localhost:3000)
        options_res = await ac.options(
            "/api/v1/projects/proj-123/anomalies",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            }
        )
        assert options_res.status_code == 200
        assert options_res.headers.get("access-control-allow-origin") in ["http://localhost:3000", "*"]
        assert options_res.headers.get("access-control-allow-credentials") == "true"

        # 2. Test GET schema info route with CORS origin header
        schema_res = await ac.get(
            "/api/v1/projects/proj-123/anomalies/schema-info",
            headers={"Origin": "http://localhost:3000"}
        )
        # Should return 200 or valid error envelope with CORS headers
        assert schema_res.headers.get("access-control-allow-origin") in ["http://localhost:3000", "*"]
        assert schema_res.status_code in [200, 400, 404]

        # 3. Test POST anomaly detection route with CORS origin header
        payload = {
            "dataset_id": "ds-test",
            "timestamp_column": "date",
            "metric_column": "revenue",
            "detection_method": "zscore",
            "sensitivity": 0.05
        }
        post_res = await ac.post(
            "/api/v1/projects/proj-123/anomalies",
            json=payload,
            headers={"Origin": "http://localhost:3000"}
        )
        assert post_res.headers.get("access-control-allow-origin") in ["http://localhost:3000", "*"]
