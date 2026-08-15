import pytest
import io
import datetime
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# 1. Test /health and /api/v1/health endpoints
def test_health_endpoints():
    res_root = client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["status"] == "healthy"
    assert data_root["fastapi"] == "healthy"

    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    data_v1 = res_v1.json()
    assert data_v1["status"] == "healthy"


# 2. Test Invalid Project ID handling (resilient fallback)
def test_invalid_project_id_fallback():
    chat_payload = {
        "message": "Hello!",
        "active_project": "non_existent_proj_9999",
        "project_id": "non_existent_proj_9999",
    }
    res = client.post("/api/v1/agents/chat", json=chat_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["content"] is not None


# 3. Test E2E Full Project Pipeline with Olist Datasets
def test_e2e_olist_full_queries():
    # Create project
    proj_res = client.post("/api/v1/projects/", json={
        "name": "E2E AI Chat Pipeline Test Project",
        "description": "Full end-to-end integration test"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # Upload products dataset
    products_csv = (
        "product_id,product_category_name\n"
        "prod_1,bed_bath_table\n"
        "prod_2,health_beauty\n"
        "prod_3,health_beauty\n"
        "prod_4,sports_leisure\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(products_csv.encode("utf-8")), "text/csv")}
    )

    # Upload items dataset
    items_csv = (
        "order_id,order_item_id,product_id,price\n"
        "ord_1,1,prod_1,100.0\n"
        "ord_2,1,prod_2,150.0\n"
        "ord_3,1,prod_3,200.0\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_order_items_dataset.csv", io.BytesIO(items_csv.encode("utf-8")), "text/csv")}
    )

    # Query 1: "Give me a summary of olist_products_dataset.csv"
    res1 = client.post("/api/v1/agents/chat", json={
        "message": "Give me a summary of olist_products_dataset.csv",
        "active_project": project_id,
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert "olist_products_dataset" in data1["content"] or data1.get("sql_query")

    # Query 2: "How many products are in each category?"
    res2 = client.post("/api/v1/agents/chat", json={
        "message": "How many products are in each category?",
        "active_project": project_id,
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["content"] is not None

    # Query 3: "Show me the top 10 product categories by number of products."
    res3 = client.post("/api/v1/agents/chat", json={
        "message": "Show me the top 10 product categories by number of products.",
        "active_project": project_id,
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["content"] is not None

    # Query 4: "Show me the top 10 selling product categories."
    res4 = client.post("/api/v1/agents/chat", json={
        "message": "Show me the top 10 selling product categories.",
        "active_project": project_id,
    })
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["content"] is not None

    # Clean up project
    client.delete(f"/api/v1/projects/{project_id}")


# 4. Test Missing Dataset Explanation
def test_missing_dataset_explanation():
    proj_res = client.post("/api/v1/projects/", json={
        "name": "Empty Project Test",
        "description": "No datasets"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    res = client.post("/api/v1/agents/chat", json={
        "message": "Show me sales by category in non_existent_file.csv",
        "active_project": project_id,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["content"] is not None and len(data["content"]) > 0

    client.delete(f"/api/v1/projects/{project_id}")



# 5. Test DuckDB Datetime and Decimal JSON Serialization
def test_duckdb_datetime_and_decimal_serialization():
    from app.core.json_utils import make_json_serializable, safe_json_dumps

    now = datetime.datetime.now()
    today = datetime.date.today()
    val_dict = {
        "timestamp": now,
        "date": today,
        "nan_val": float("nan"),
        "inf_val": float("inf"),
        "null_val": None,
    }

    ser = make_json_serializable(val_dict)
    assert isinstance(ser["timestamp"], str)
    assert isinstance(ser["date"], str)
    assert ser["nan_val"] is None
    assert ser["inf_val"] is None

    json_str = safe_json_dumps(val_dict)
    assert "timestamp" in json_str
