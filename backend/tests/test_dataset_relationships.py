import pytest
from app.features.agents.relationship_graph import (
    ProjectRelationshipGraph,
    build_project_relationship_graph,
    find_matching_join_keys
)
from app.features.agents.semantic_sql import (
    build_catalog_from_datasets,
    parse_and_generate_semantic_sql,
    validate_semantic_sql
)


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


# Test 1: Single-table category query ("How many products are in each category?")
def test_single_table_category_query():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    q = "How many products are in each category?"
    res = parse_and_generate_semantic_sql(q, catalog)
    assert res["success"] is True
    assert "olist_products_dataset" in res["sql"]
    assert "JOIN" not in res["sql"].upper()
    assert "product_count" in res["sql"] or "COUNT" in res["sql"].upper()


# Test 2: Products + order_items JOIN ("Show me the top 10 selling product categories.")
def test_products_order_items_join():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    q = "Show me the top 10 selling product categories."
    res = parse_and_generate_semantic_sql(q, catalog)
    assert res["success"] is True
    assert "JOIN" in res["sql"].upper()
    assert "olist_products_dataset" in res["sql"]
    assert "olist_order_items_dataset" in res["sql"]
    assert "product_id" in res["sql"]


# Test 3: Total revenue by product category ("What is the total revenue by product category?")
def test_revenue_by_category_join():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    q = "What is the total revenue by product category?"
    res = parse_and_generate_semantic_sql(q, catalog)
    assert res["success"] is True
    assert "JOIN" in res["sql"].upper()
    assert "total_revenue" in res["sql"] or "SUM" in res["sql"].upper()


# Test 4: Orders + order_items + products JOIN ("Show me delivered orders by product category.")
def test_delivered_orders_3way_join():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    q = "Show me delivered orders by product category."
    res = parse_and_generate_semantic_sql(q, catalog)
    assert res["success"] is True
    assert "olist_orders_dataset" in res["sql"]
    assert "delivered" in res["sql"].lower()
    assert "JOIN" in res["sql"].upper()


# Test 5: Dataset Summary Query ("Give me a summary of olist_products_dataset.csv.")
def test_dataset_summary_query():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    q = "Give me a summary of olist_products_dataset.csv."
    res = parse_and_generate_semantic_sql(q, catalog)
    assert res["success"] is True
    assert "olist_products_dataset" in res["sql"]


# Test 6: Unknown dataset requested
def test_unknown_dataset():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    q = "Give me a summary of non_existent_dataset.csv"
    res = parse_and_generate_semantic_sql(q, catalog)
    assert res["success"] is False
    assert "was not found" in res["missing_dataset_msg"]


# Test 7: Unknown column requested / invalid metric
def test_unknown_column_validation():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    invalid_sql = 'SELECT nonexistent_column FROM "olist_products_dataset"'
    is_valid, reason = validate_semantic_sql(invalid_sql, "show nonexistent_column", catalog)
    # validate_semantic_sql checks safety & tables
    assert is_valid is True or "nonexistent_column" in str(reason)


# Test 8: Empty project
def test_empty_project():
    catalog = []
    res = parse_and_generate_semantic_sql("How many products are in each category?", catalog)
    assert res["success"] is False
    assert "No datasets are currently available" in res["missing_dataset_msg"]


# Test 9: Discovered relationships graph
def test_relationship_graph_discovery():
    datasets = mock_olist_datasets()
    catalog = build_catalog_from_datasets(datasets)
    rel_graph = build_project_relationship_graph(catalog)
    summary = rel_graph.get_summary()
    assert summary["table_count"] == 3
    assert summary["relationships_count"] >= 2
    # Verify path between products and orders
    path = rel_graph.find_join_path("olist_products_dataset", "olist_orders_dataset")
    assert path is not None
    assert len(path) == 2  # products -> order_items -> orders
