import pytest
import time
from app.features.agents.semantic_sql import (
    build_catalog_from_datasets,
    parse_and_generate_semantic_sql,
    validate_semantic_sql
)
from app.features.agents.tools import (
    list_project_datasets,
    get_dataset_schema,
    generate_sql,
    validate_sql,
    analyze_query_result
)
from app.features.agents.agents import planner_agent, sql_agent


def mock_olist_datasets():
    return [
        {
            "id": "ds-orders",
            "filename": "olist_orders_dataset.csv",
            "display_name": "olist_orders_dataset",
            "duckdb_table": "olist_orders_dataset",
            "type": "CSV",
            "schema_json": '{"order_id": {"type": "VARCHAR"}, "customer_id": {"type": "VARCHAR"}, "order_status": {"type": "VARCHAR"}, "order_purchase_timestamp": {"type": "TIMESTAMP"}}',
            "rows": 99441
        },
        {
            "id": "ds-products",
            "filename": "olist_products_dataset.csv",
            "display_name": "olist_products_dataset",
            "duckdb_table": "olist_products_dataset",
            "type": "CSV",
            "schema_json": '{"product_id": {"type": "VARCHAR"}, "product_category_name": {"type": "VARCHAR"}, "product_name_lenght": {"type": "BIGINT"}}',
            "rows": 32951
        },
        {
            "id": "ds-items",
            "filename": "olist_order_items_dataset.csv",
            "display_name": "olist_order_items_dataset",
            "duckdb_table": "olist_order_items_dataset",
            "type": "CSV",
            "schema_json": '{"order_id": {"type": "VARCHAR"}, "order_item_id": {"type": "BIGINT"}, "product_id": {"type": "VARCHAR"}, "seller_id": {"type": "VARCHAR"}, "price": {"type": "DOUBLE"}}',
            "rows": 112650
        }
    ]


def test_openrouter_exact_queries():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)

    # 1. "Show me the top 5 orders from olist_orders_dataset.csv"
    q1 = "Show me the top 5 orders from olist_orders_dataset.csv"
    res1 = parse_and_generate_semantic_sql(q1, catalog)
    assert res1["success"] is True
    assert "olist_orders_dataset" in res1["sql"]
    assert "LIMIT 5" in res1["sql"]

    # 2. "How many products are in olist_products_dataset.csv?"
    q2 = "How many products are in olist_products_dataset.csv?"
    res2 = parse_and_generate_semantic_sql(q2, catalog)
    assert res2["success"] is True
    assert "COUNT(*)" in res2["sql"].upper()
    assert "olist_products_dataset" in res2["sql"]

    # 3. "Show me the top sales by category in olist_products_dataset.csv"
    q3 = "Show me the top sales by category in olist_products_dataset.csv"
    res3 = parse_and_generate_semantic_sql(q3, catalog)
    assert res3["success"] is True
    assert "product_category_name" in res3["sql"] or "category" in res3["sql"].lower()

    # 4. "Which product categories generate the most revenue?"
    q4 = "Which product categories generate the most revenue?"
    res4 = parse_and_generate_semantic_sql(q4, catalog)
    assert res4["success"] is True
    assert "JOIN" in res4["sql"].upper() or "total_revenue" in res4["sql"]

    # 5. "Show monthly sales"
    q5 = "Show monthly sales"
    res5 = parse_and_generate_semantic_sql(q5, catalog)
    assert res5["success"] is True
    assert "strftime" in res5["sql"].lower() or "month" in res5["sql"].lower()

    # 6. "hi"
    state_hi = {
        "query": "hi",
        "workspace": "default",
        "dataset": None,
        "selected_dataset_ids": None,
        "available_datasets": datasets,
        "active_project": "proj-1",
        "history": [],
        "plan": [],
        "completed_steps": [],
        "next_agent": "",
        "sql_query": None,
        "sql_result": None,
        "execution_logs": [],
        "reasoning_path": []
    }
    res_hi = planner_agent(state_hi)
    assert res_hi["intent"] == "conversation"
    assert res_hi["sql_query"] is None
    assert "Hello" in res_hi["final_response"] or "AI Business Intelligence" in res_hi["final_response"]

    # 7. "hello"
    state_hello = {
        "query": "hello",
        "workspace": "default",
        "dataset": None,
        "selected_dataset_ids": None,
        "available_datasets": datasets,
        "active_project": "proj-1",
        "history": [],
        "plan": [],
        "completed_steps": [],
        "next_agent": "",
        "sql_query": None,
        "sql_result": None,
        "execution_logs": [],
        "reasoning_path": []
    }
    res_hello = planner_agent(state_hello)
    assert res_hello["intent"] == "conversation"
    assert res_hello["sql_query"] is None


def test_validate_sql_read_only():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)

    bad_sql = 'DROP TABLE "olist_products_dataset"'
    is_valid, reason = validate_semantic_sql(bad_sql, "drop products", catalog)
    assert is_valid is False
    assert "Forbidden SQL operation" in reason
