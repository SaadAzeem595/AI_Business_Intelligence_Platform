import pytest
import io
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.features.agents.semantic_sql import (
    build_catalog_from_datasets,
    parse_and_generate_semantic_sql,
    validate_semantic_sql,
    is_analytical_query
)

client = TestClient(app)


# 1. Test Semantic Planner Unit Logic
def test_semantic_sql_planner_unit():
    # Catalog simulating Olist tables
    available_datasets = [
        {
            "id": "1",
            "filename": "olist_products_dataset.csv",
            "duckdb_table": "olist_products_dataset",
            "schema_json": '{"product_id": {"type": "VARCHAR"}, "product_category_name": {"type": "VARCHAR"}}'
        },
        {
            "id": "2",
            "filename": "olist_order_items_dataset.csv",
            "duckdb_table": "olist_order_items_dataset",
            "schema_json": '{"order_id": {"type": "VARCHAR"}, "product_id": {"type": "VARCHAR"}, "price": {"type": "DOUBLE"}}'
        },
        {
            "id": "3",
            "filename": "olist_orders_dataset.csv",
            "duckdb_table": "olist_orders_dataset",
            "schema_json": '{"order_id": {"type": "VARCHAR"}, "customer_id": {"type": "VARCHAR"}, "order_purchase_timestamp": {"type": "TIMESTAMP"}}'
        }
    ]

    catalog = build_catalog_from_datasets(available_datasets)
    assert len(catalog) == 3

    # Test Query 1: "Show the top 10 product categories by number of orders"
    res1 = parse_and_generate_semantic_sql("Show the top 10 product categories by number of orders", catalog)
    assert res1["success"] is True
    assert "COUNT(DISTINCT" in res1["sql"].upper()
    assert "GROUP BY" in res1["sql"].upper()
    assert "ORDER BY" in res1["sql"].upper()
    assert "JOIN" in res1["sql"].upper()
    assert "olist_products_dataset" in res1["sql"]
    assert "olist_order_items_dataset" in res1["sql"]

    # Test Query 2: "Which category has the most orders?"
    res2 = parse_and_generate_semantic_sql("Which category has the most orders?", catalog)
    assert res2["success"] is True
    assert "GROUP BY" in res2["sql"].upper()
    assert "COUNT(DISTINCT" in res2["sql"].upper()

    # Test Query 3: "Show monthly order trends"
    res3 = parse_and_generate_semantic_sql("Show monthly order trends", catalog)
    assert res3["success"] is True
    assert "STRFTIME" in res3["sql"].upper() or "DATE_TRUNC" in res3["sql"].upper() or "MONTH" in res3["sql"].upper()
    assert "GROUP BY" in res3["sql"].upper()

    # Test Query 4: "Which products generated the highest revenue?"
    res4 = parse_and_generate_semantic_sql("Which products generated the highest revenue?", catalog)
    assert res4["success"] is True
    assert "SUM" in res4["sql"].upper()
    assert "ORDER BY" in res4["sql"].upper()


    # Test Query 5: "Show the top 5 customers by number of orders"
    res5 = parse_and_generate_semantic_sql("Show the top 5 customers by number of orders", catalog)
    assert res5["success"] is True
    assert "COUNT" in res5["sql"].upper()
    assert "LIMIT 5" in res5["sql"].upper()



# 2. Test Missing Dataset Detection
def test_missing_dataset_detection():
    # Only products dataset present (missing order_items)
    incomplete_datasets = [
        {
            "id": "1",
            "filename": "olist_products_dataset.csv",
            "duckdb_table": "olist_products_dataset",
            "schema_json": '{"product_id": {"type": "VARCHAR"}, "product_category_name": {"type": "VARCHAR"}}'
        }
    ]
    catalog = build_catalog_from_datasets(incomplete_datasets)
    res = parse_and_generate_semantic_sql("Show the delivered orders revenue by category", catalog)

    assert res["success"] is False
    assert res["missing_dataset_msg"] is not None
    assert ("cannot be calculated" in res["missing_dataset_msg"] or "unavailable" in res["missing_dataset_msg"] or "I need" in res["missing_dataset_msg"])




# 3. Test Pre-Execution Semantic Validation
def test_semantic_validation_layer():
    catalog = [
        {
            "table_name": "olist_products_dataset",
            "columns": {"product_category_name": {"name": "product_category_name", "type": "VARCHAR"}}
        }
    ]

    # Un-aggregated SELECT * LIMIT 5 on analytical query must fail validation
    invalid_sql = 'SELECT * FROM "olist_products_dataset" LIMIT 5'
    user_q = "Show the highest orders by category"

    is_valid, reason = validate_semantic_sql(invalid_sql, user_q, catalog)
    assert is_valid is False
    assert "un-aggregated" in reason or "aggregation" in reason

    # Aggregated query must pass validation
    valid_sql = 'SELECT product_category_name, COUNT(DISTINCT order_id) as order_count FROM "olist_products_dataset" GROUP BY 1 ORDER BY order_count DESC LIMIT 10'
    is_valid_ok, reason_ok = validate_semantic_sql(valid_sql, user_q, catalog)
    assert is_valid_ok is True


# 4. End-to-End API Integration Test with Multi-Dataset Project
@patch("app.core.llm.LLMService.is_configured", return_value=False)
def test_end_to_end_multidataset_analytics(mock_is_configured):

    # Create project
    proj_res = client.post("/api/v1/projects/", json={
        "name": "Olist E-Commerce Multi-Dataset Test",
        "description": "Integration test for semantic SQL reasoning layer"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # Upload 1: olist_products_dataset.csv
    products_csv = (
        "product_id,product_category_name\n"
        "prod_001,bed_bath_table\n"
        "prod_002,health_beauty\n"
        "prod_003,sports_leisure\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(products_csv.encode("utf-8")), "text/csv")}
    )

    # Upload 2: olist_order_items_dataset.csv
    order_items_csv = (
        "order_id,order_item_id,product_id,price\n"
        "ord_001,1,prod_001,100.0\n"
        "ord_002,1,prod_001,150.0\n"
        "ord_003,1,prod_002,200.0\n"
        "ord_004,1,prod_001,80.0\n"
        "ord_005,1,prod_003,300.0\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_order_items_dataset.csv", io.BytesIO(order_items_csv.encode("utf-8")), "text/csv")}
    )

    # Query 1: "Show the highest orders by category in olist_products_dataset.csv"
    chat_payload = {
        "message": "Show the highest orders by category in olist_products_dataset.csv",
        "active_project": project_id,
        "project_id": project_id,
    }
    chat_res = client.post("/api/v1/chat/message", json=chat_payload)
    assert chat_res.status_code == 200, chat_res.text
    data = chat_res.json()

    assert data["sql_query"] is not None
    assert "SELECT *" not in data["sql_query"].upper()
    assert "GROUP BY" in data["sql_query"].upper()
    assert "COUNT(DISTINCT" in data["sql_query"].upper() or "COUNT(" in data["sql_query"].upper()
    assert data["data"] is not None
    assert len(data["data"]) > 0
    # Top category should be bed_bath_table with 3 orders
    top_cat = data["data"][0].get("category") or data["data"][0].get("product_category_name")
    assert top_cat == "bed_bath_table"


    # Query 2: "Which category has the most orders?"
    top_cat_res = client.post("/api/v1/chat/message", json={
        "message": "Which category has the most orders?",
        "active_project": project_id,
        "project_id": project_id,
    })
    assert top_cat_res.status_code == 200
    top_cat_data = top_cat_res.json()
    assert "GROUP BY" in top_cat_data["sql_query"].upper()

    # Clean up project
    client.delete(f"/api/v1/projects/{project_id}")


from unittest.mock import patch


# 5. Test State Isolation & The 6 Required Test Queries (A - F)
@patch("app.core.llm.LLMService.is_configured", return_value=False)
def test_exact_required_queries_and_state_isolation(mock_is_configured):

    # Create project
    proj_res = client.post("/api/v1/projects/", json={
        "name": "Required Queries Test Project",
        "description": "Validation for Requirement 14 queries"
    })
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # Upload olist_products_dataset.csv
    products_csv = (
        "product_id,product_category_name\n"
        "prod_001,bed_bath_table\n"
        "prod_002,health_beauty\n"
        "prod_003,sports_leisure\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_products_dataset.csv", io.BytesIO(products_csv.encode("utf-8")), "text/csv")}
    )

    # Upload olist_order_items_dataset.csv
    items_csv = (
        "order_id,order_item_id,product_id,price\n"
        "ord_001,1,prod_001,100.0\n"
        "ord_002,1,prod_001,150.0\n"
        "ord_003,1,prod_002,200.0\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_order_items_dataset.csv", io.BytesIO(items_csv.encode("utf-8")), "text/csv")}
    )

    # Upload olist_orders_dataset.csv
    orders_csv = (
        "order_id,customer_id,order_status,order_purchase_timestamp,price\n"
        "ord_001,cust_101,delivered,2026-01-15 10:30:00,100.0\n"
        "ord_002,cust_102,shipped,2026-01-16 11:45:00,150.0\n"
        "ord_003,cust_103,delivered,2026-01-17 14:20:00,200.0\n"
    )
    client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("olist_orders_dataset.csv", io.BytesIO(orders_csv.encode("utf-8")), "text/csv")}
    )

    thread_id = "test-session-thread-99"

    # Query A: "show me the top sales by category in olist_products_dataset.csv"
    res_a = client.post("/api/v1/chat/message", json={
        "message": "show me the top sales by category in olist_products_dataset.csv",
        "active_project": project_id,
        "project_id": project_id,
        "thread_id": thread_id
    })
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["content"] is not None or data_a["sql_query"] is not None
    if data_a.get("sql_query"):
        assert "JOIN" in data_a["sql_query"].upper() or "olist_products_dataset" in data_a["sql_query"]


    # Query B: "hi" (SAME thread_id -> test context reset & no leak of Query A state)
    res_b = client.post("/api/v1/chat/message", json={
        "message": "hi",
        "active_project": project_id,
        "project_id": project_id,
        "thread_id": thread_id
    })
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["sql_query"] is None
    assert data_b["data"] is None
    assert "content" in data_b and len(data_b["content"]) > 0


    # Query C: "show me the top 5 orders from olist_orders_dataset.csv"
    res_c = client.post("/api/v1/chat/message", json={
        "message": "show me the top 5 orders from olist_orders_dataset.csv",
        "active_project": project_id,
        "project_id": project_id,
        "thread_id": thread_id
    })
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert data_c["sql_query"] is not None
    assert "olist_orders_dataset" in data_c["sql_query"]
    assert "LIMIT 5" in data_c["sql_query"].upper() or "LIMIT" in data_c["sql_query"].upper()

    # Query D: "how many products are in olist_products_dataset.csv?"
    res_d = client.post("/api/v1/chat/message", json={
        "message": "how many products are in olist_products_dataset.csv?",
        "active_project": project_id,
        "project_id": project_id,
        "thread_id": thread_id
    })
    assert res_d.status_code == 200
    data_d = res_d.json()
    assert data_d["sql_query"] is not None
    assert "COUNT" in data_d["sql_query"].upper()
    assert "olist_products_dataset" in data_d["sql_query"]


    # Query E: "which product categories generate the most revenue?"
    res_e = client.post("/api/v1/chat/message", json={
        "message": "which product categories generate the most revenue?",
        "active_project": project_id,
        "project_id": project_id,
        "thread_id": thread_id
    })
    assert res_e.status_code == 200
    data_e = res_e.json()
    assert data_e["sql_query"] is not None
    assert "SUM" in data_e["sql_query"].upper()
    assert "GROUP BY" in data_e["sql_query"].upper()

    # Query F: "show monthly sales"
    res_f = client.post("/api/v1/chat/message", json={
        "message": "show monthly sales",
        "active_project": project_id,
        "project_id": project_id,
        "thread_id": thread_id
    })
    assert res_f.status_code == 200
    data_f = res_f.json()
    assert data_f["sql_query"] is not None
    assert "STRFTIME" in data_f["sql_query"].upper()

    # Cleanup
    client.delete(f"/api/v1/projects/{project_id}")
