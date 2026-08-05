import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_chat_pipeline_missing_values():
    client = TestClient(app)
    chat_payload = {
        "message": "Show missing values in customer_churn_data.csv",
        "workspace": "sales"
    }
    response = client.post("/api/v1/agents/chat", json=chat_payload)
    assert response.status_code == 200
    resp_json = response.json()
    assert "analytics_agent" in resp_json["reasoning_path"]
    assert "customer_churn_data" in resp_json["response"]
    assert resp_json["table"] is not None
    assert len(resp_json["table"]["data"]) > 0

def test_chat_pipeline_summarize_products():
    client = TestClient(app)
    chat_payload = {
        "message": "Summarize products in the database",
        "workspace": "sales"
    }
    response = client.post("/api/v1/agents/chat", json=chat_payload)
    assert response.status_code == 200
    resp_json = response.json()
    
    # Needs approval for SQL execution - since we pause before SQL agent
    assert resp_json["status"] == "paused"
    assert resp_json["sql_query"] is not None
    assert "product_inventory_data" in resp_json["sql_query"]
    
    # Auto-resume / approve SQL
    approve_payload = {
        "thread_id": resp_json["thread_id"],
        "approved": True
    }
    approve_resp = client.post("/api/v1/agents/approve", json=approve_payload)
    assert approve_resp.status_code == 200
    approve_json = approve_resp.json()
    assert approve_json["status"] == "completed"
    assert "sql_agent" in approve_json["reasoning_path"]
    assert approve_json["table"] is not None

def test_chat_pipeline_duplicate_rows():
    client = TestClient(app)
    chat_payload = {
        "message": "Show duplicate rows in customer_churn",
        "workspace": "sales"
    }
    response = client.post("/api/v1/agents/chat", json=chat_payload)
    assert response.status_code == 200
    resp_json = response.json()
    assert "analytics_agent" in resp_json["reasoning_path"]
    assert "customer_churn" in resp_json["response"]

def test_chat_pipeline_forecasting():
    client = TestClient(app)
    chat_payload = {
        "message": "Forecast monthly revenue in sales_data.csv",
        "workspace": "sales"
    }
    response = client.post("/api/v1/agents/chat", json=chat_payload)
    assert response.status_code == 200
    resp_json = response.json()
    assert "forecast_agent" in resp_json["reasoning_path"]
    assert "sales_data" in resp_json["response"]

def test_chat_pipeline_unknown_dataset():
    client = TestClient(app)
    chat_payload = {
        "message": "Show the missing values in olist_orders_dataset.csv",
        "workspace": "default"
    }
    response = client.post("/api/v1/agents/chat", json=chat_payload)
    
    # Validation rejection should return HTTP 400 Bad Request
    assert response.status_code == 400
    resp_json = response.json()
    assert "I couldn't analyze the requested dataset because" in resp_json["detail"]
