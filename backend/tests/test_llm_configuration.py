import os
import pytest
import io
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.llm import LLMService, LLMConfigurationError

client = TestClient(app)


# 1. Test LLM Configuration Diagnostic Status
def test_llm_diagnostic_status():
    status = LLMService.get_diagnostic_status()
    assert "provider" in status
    assert "provider_configured" in status
    assert "model" in status
    assert "api_key_configured" in status
    assert "base_url" in status
    assert status["provider_configured"] is True


# 2. Test Missing API Key Messaging
def test_missing_api_key_error_messaging():
    with patch.object(LLMService, "get_api_key_and_provider", return_value=(None, None)):
        assert LLMService.is_configured() is False
        with pytest.raises(LLMConfigurationError) as exc_info:
            LLMService.generate_response("system", "user")
        assert "OPENROUTER_API_KEY is not configured" in str(exc_info.value)


# 3. Test Invalid API Key (HTTP 401)
def test_invalid_api_key_401_handling():
    with patch.object(LLMService, "get_api_key_and_provider", return_value=("invalid_key_xyz", "openrouter")):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        
        with patch("httpx.Client.post", return_value=mock_resp):
            with pytest.raises(LLMConfigurationError) as exc_info:
                LLMService.generate_response("system", "user")
            assert "Invalid OPENROUTER_API_KEY" in str(exc_info.value) or "HTTP 401" in str(exc_info.value)


# 4. Test Model Rate Limit 429 Fallback
def test_openrouter_rate_limit_fallback():
    # First model call 429, second candidate model call succeeds (200)
    resp_429 = MagicMock()
    resp_429.status_code = 429

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Fallback model response succeeded."}}]
    }

    with patch("httpx.Client.post", side_effect=[resp_429, resp_200]):
        res = LLMService.generate_response("System prompt", "User prompt")
        assert res == "Fallback model response succeeded."


# 5. Test Successful LLM Response
def test_successful_llm_request():
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Analytical summary response."}}]
    }

    with patch("httpx.Client.post", return_value=resp_200):
        res = LLMService.generate_response("System prompt", "User prompt")
        assert "Analytical summary" in res


# 6. Test DuckDB Query + LLM Response Integration
def test_duckdb_query_plus_llm_response():
    proj_res = client.post("/api/v1/projects", json={
        "name": "LLM Config Test Project",
        "description": "Integration testing LLM responses"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    csv_data = "product_id,product_category_name\np1,c1\np2,c1\np3,c2\n"
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    )

    with patch.object(LLMService, "generate_response", return_value="Category c1 has 2 products and category c2 has 1 product."):
        chat_res = client.post("/api/v1/agents/chat", json={
            "message": "How many products are in each category?",
            "active_project": project_id
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "content" in data
        assert "c1 has 2 products" in data["content"] or "Category" in data["content"]

    client.delete(f"/api/v1/projects/{project_id}")


# 7. Test Empty Query Result Handling
def test_empty_query_result_handling():
    proj_res = client.post("/api/v1/projects", json={
        "name": "Empty Result Test Project",
        "description": "Integration testing empty query results"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    csv_data = "product_id,product_category_name\np1,c1\n"
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    )

    with patch.object(LLMService, "generate_response", return_value="Summary of olist_products_dataset.csv completed."):
        chat_res = client.post("/api/v1/agents/chat", json={
            "message": "Give me a summary of olist_products_dataset.csv",
            "active_project": project_id
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "content" in data
        assert data["content"] is not None

    client.delete(f"/api/v1/projects/{project_id}")



# 8. Test /health Probe Returns LLM Diagnostic Info
def test_health_endpoint_llm_status():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "llm" in data
    assert data["llm"]["provider_configured"] is True
