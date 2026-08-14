import pytest
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ai_chat_project_data_pipeline():
    # 1. Create a Project
    proj_res = client.post("/api/v1/projects/", json={
        "name": "Olist E-Commerce Analytics Project",
        "description": "Test workspace for AI Chat data pipeline"
    })
    assert proj_res.status_code == 201, proj_res.text
    proj_data = proj_res.json()
    project_id = proj_data["id"]

    # 2. Upload olist_orders_dataset.csv to the project
    csv_content = (
        "order_id,customer_id,order_status,order_purchase_timestamp,price\n"
        "ord_001,cust_101,delivered,2026-01-15 10:30:00,120.50\n"
        "ord_002,cust_102,shipped,2026-01-16 11:45:00,85.00\n"
        "ord_003,cust_103,delivered,2026-01-17 14:20:00,210.00\n"
        "ord_004,cust_101,delivered,2026-02-01 09:15:00,45.25\n"
        "ord_005,cust_104,delivered,2026-02-05 16:50:00,310.80\n"
        "ord_006,cust_105,processing,2026-02-10 18:10:00,99.99\n"
        "ord_007,cust_102,delivered,2026-02-12 20:05:00,150.00\n"
    )
    
    upload_res = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_orders_dataset.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    )
    assert upload_res.status_code == 200, upload_res.text
    dataset_info = upload_res.json()
    assert dataset_info["filename"] == "olist_orders_dataset.csv"
    assert dataset_info["rows"] == 7

    # 3. Test Primary Query: "show me the top 5 orders of olist_orders_dataset.csv"
    chat_payload = {
        "message": "show me the top 5 orders of olist_orders_dataset.csv",
        "active_project": project_id,
        "project_id": project_id,
    }
    
    chat_res = client.post("/api/v1/chat/message", json=chat_payload)
    assert chat_res.status_code == 200, chat_res.text
    res_data = chat_res.json()
    
    assert res_data["content"] is not None
    assert len(res_data["content"].strip()) > 0
    assert "no response content was returned" not in res_data["content"]
    assert res_data["sql_query"] is not None
    assert "LIMIT 5" in res_data["sql_query"].upper() or "LIMIT" in res_data["sql_query"].upper()
    assert res_data["data"] is not None
    assert len(res_data["data"]) == 5
    assert res_data["row_count"] == 5

    # 4. Test Follow-up Query: "How many orders are in the dataset?"
    count_res = client.post("/api/v1/chat/message", json={
        "message": "How many orders are in the dataset?",
        "active_project": project_id,
        "project_id": project_id,
    })
    assert count_res.status_code == 200, count_res.text
    count_data = count_res.json()
    assert count_data["content"] is not None
    assert len(count_data["data"]) == 1
    assert count_data["data"][0]["total_count"] == 7

    # 5. Test Query: "Show the columns in olist_orders_dataset.csv"
    cols_res = client.post("/api/v1/chat/message", json={
        "message": "Show the columns in olist_orders_dataset.csv",
        "active_project": project_id,
        "project_id": project_id,
    })
    assert cols_res.status_code == 200, cols_res.text
    cols_data = cols_res.json()
    assert cols_data["content"] is not None
    assert len(cols_data["data"]) >= 5

    # 6. Test Query: "Show the top 10 customers by number of orders."
    top_cust_res = client.post("/api/v1/chat/message", json={
        "message": "Show the top 10 customers by number of orders.",
        "active_project": project_id,
        "project_id": project_id,
    })
    assert top_cust_res.status_code == 200, top_cust_res.text
    top_cust_data = top_cust_res.json()
    assert top_cust_data["content"] is not None
    assert len(top_cust_data["data"]) > 0

    # Clean up project
    del_res = client.delete(f"/api/v1/projects/{project_id}")
    assert del_res.status_code == 200
