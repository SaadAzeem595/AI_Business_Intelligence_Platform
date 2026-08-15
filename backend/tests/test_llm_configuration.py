import os
import pytest
import io
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.llm import LLMService, LLMConfigurationError

client = TestClient(app)


# 1. Test LLM Configuration Diagnostic Status (Available)
def test_llm_configuration_available():
    status = LLMService.get_diagnostic_status()
    assert "provider" in status
    assert "provider_configured" in status
    assert "model" in status
    assert "model_configured" in status
    assert "api_key_configured" in status
    assert "base_url" in status
    assert "base_url_configured" in status
    assert status["provider_configured"] is True
    assert status["api_key_configured"] is True


# 2. Test Missing API Key Handling
def test_missing_api_key_error_handling():
    with patch.object(LLMService, "get_api_key_and_provider", return_value=(None, None)):
        assert LLMService.is_configured() is False
        with pytest.raises(LLMConfigurationError) as exc_info:
            LLMService.generate_response("system", "user")
        assert "Missing API key" in str(exc_info.value)


# 3. Test Invalid API Key (HTTP 401 Handling)
def test_invalid_api_key_401_handling():
    with patch.object(LLMService, "get_api_key_and_provider", return_value=("invalid_key_xyz", "openrouter")):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        
        with patch("httpx.Client.post", return_value=mock_resp):
            with pytest.raises(LLMConfigurationError) as exc_info:
                LLMService.generate_response("system", "user")
            assert "Invalid API key" in str(exc_info.value) or "HTTP 401" in str(exc_info.value)


# 4. Test Invalid Model Handling (HTTP 404 Handling)
def test_invalid_model_error_handling():
    with patch.object(LLMService, "get_api_key_and_provider", return_value=("valid_key", "openrouter")):
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_resp_404.text = "Model Not Found"
        
        with patch("httpx.Client.post", return_value=mock_resp_404):
            with pytest.raises(LLMConfigurationError) as exc_info:
                LLMService.generate_response("system", "user", model_override="invalid/nonexistent-model")
            assert "was not found" in str(exc_info.value) or "404" in str(exc_info.value)


# 5. Test Successful LLM Request
def test_successful_llm_request():
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Analytical summary response."}}]
    }

    with patch("httpx.Client.post", return_value=resp_200):
        res = LLMService.generate_response("System prompt", "User prompt")
        assert "Analytical summary" in res


# 6. Test LLM Timeout Handling
def test_llm_timeout_handling():
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Request timed out")):
        with pytest.raises(LLMConfigurationError) as exc_info:
            LLMService.generate_response("System prompt", "User prompt")
        assert "timed out" in str(exc_info.value)


# 7. Test DuckDB Query + LLM Response Integration
def test_duckdb_query_plus_llm_response():
    proj_res = client.post("/api/v1/projects", json={
        "name": "DuckDB Integration Test Project",
        "description": "Integration testing LLM responses with DuckDB"
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


# 8. Test Empty Query Result Handling
def test_empty_query_result_handling():
    proj_res = client.post("/api/v1/projects", json={
        "name": "Empty Result Test Project",
        "description": "Integration testing empty query results"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    csv_data = "product_id,product_category_name\n"
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    )

    with patch.object(LLMService, "generate_response", return_value="Dataset is empty with no product rows."):
        chat_res = client.post("/api/v1/agents/chat", json={
            "message": "Give me a summary of olist_products_dataset.csv",
            "active_project": project_id
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "content" in data
        assert data["content"] is not None

    client.delete(f"/api/v1/projects/{project_id}")


# 9. Test Dataset Summary Query
def test_dataset_summary_query():
    proj_res = client.post("/api/v1/projects", json={
        "name": "Dataset Summary Test Project",
        "description": "Testing dataset summary AI response"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    csv_data = "product_id,product_category_name,product_weight_g\np1,electronics,500\np2,furniture,1200\n"
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    )

    with patch.object(LLMService, "generate_response", return_value="Here is the summary of olist_products_dataset.csv containing 2 products across electronics and furniture categories."):
        chat_res = client.post("/api/v1/agents/chat", json={
            "message": "Give me a summary of olist_products_dataset.csv",
            "active_project": project_id
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "content" in data
        assert "electronics" in data["content"] or "summary" in data["content"].lower()

    client.delete(f"/api/v1/projects/{project_id}")


# 10. Test Category Aggregation Query
def test_category_aggregation_query():
    proj_res = client.post("/api/v1/projects", json={
        "name": "Category Aggregation Test Project",
        "description": "Testing category aggregation AI query"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    csv_data = "product_id,product_category_name\np1,bed_bath_table\np2,bed_bath_table\np3,health_beauty\n"
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    )

    with patch.object(LLMService, "generate_response", return_value="The dataset contains 2 products in bed_bath_table and 1 product in health_beauty."):
        chat_res = client.post("/api/v1/agents/chat", json={
            "message": "How many products are in each category?",
            "active_project": project_id
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "content" in data
        assert "bed_bath_table" in data["content"] or "category" in data["content"].lower()

    client.delete(f"/api/v1/projects/{project_id}")


# 11. Test /health and /health/llm Probes Return LLM Diagnostic Info
def test_health_endpoints_llm_status():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "llm" in data
    assert data["llm"]["provider_configured"] is True

    probe_res = client.get("/api/v1/health/llm")
    assert probe_res.status_code == 200
    probe_data = probe_res.json()
    assert "status" in probe_data
