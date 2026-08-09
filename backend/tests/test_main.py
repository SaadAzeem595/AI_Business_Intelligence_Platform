from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health() -> None:
    """Verifies baseline health check response parameters."""
    response = client.get("/health")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "healthy"
    assert res["fastapi"] == "healthy"


def test_list_datasets() -> None:
    """Verifies that datasets list logs compile successfully."""
    response = client.get("/api/v1/datasets")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0
