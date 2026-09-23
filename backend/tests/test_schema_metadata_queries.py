import sys
import os

# Add backend directory to sys.path
backend_dir = r"d:\AI Business Intelligence Platform\backend"
sys.path.insert(0, backend_dir)

from app.features.agents.schema_inspector import (
    is_schema_metadata_query,
    classify_schema_query,
    inspect_dataset_schema,
    format_schema_response
)
from app.features.agents.agents import planner_agent

print("=== 1. Testing Schema Query Pattern Recognition ===")
test_queries = [
    ("How many total columns in the given dataset olist_geolocation_dataset.csv?", True, "column_count"),
    ("what are the total columns in olist_geolocation_dataset.csv?", True, "column_count"),
    ("how many columns in olist_geolocation_dataset.csv", True, "column_count"),
    ("what are the columns in olist_geolocation_dataset.csv", True, "column_list"),
    ("list columns in olist_geolocation_dataset.csv", True, "column_list"),
    ("show all columns for olist_geolocation_dataset.csv", True, "column_list"),
    ("how many rows in olist_geolocation_dataset.csv", True, "row_count"),
    ("how many records in olist_geolocation_dataset.csv", True, "row_count"),
    ("how many rows and columns in olist_geolocation_dataset.csv", True, "dataset_shape"),
    ("what is the schema of olist_geolocation_dataset.csv", True, "schema_structure"),
    ("describe schema for olist_geolocation_dataset.csv", True, "schema_structure"),
    # Analytical queries that should NOT be schema queries
    ("What are the top 5 product categories by total sales?", False, None),
    ("Show monthly revenue trend for 2026", False, None),
    ("Count of orders by status", False, None),
]

for query, expected_is_schema, expected_category in test_queries:
    is_schema = is_schema_metadata_query(query)
    assert is_schema == expected_is_schema, f"Failed is_schema check for: '{query}'. Got {is_schema}, expected {expected_is_schema}"
    if is_schema and expected_category:
        category = classify_schema_query(query)
        assert category == expected_category, f"Failed category for: '{query}'. Got {category}, expected {expected_category}"
print("All query pattern checks PASSED!")

print("\n=== 2. Testing Direct Schema Inspector and Formatter ===")
mock_resolved = {
    "id": "ds-geo-1",
    "filename": "olist_geolocation_dataset.csv",
    "display_name": "olist_geolocation_dataset",
    "view_name": "olist_geolocation_dataset",
    "path": None,
    "rows": 1000163,
    "schema": {
        "geolocation_zip_code_prefix": {"type": "BIGINT"},
        "geolocation_lat": {"type": "DOUBLE"},
        "geolocation_lng": {"type": "DOUBLE"},
        "geolocation_city": {"type": "VARCHAR"},
        "geolocation_state": {"type": "VARCHAR"}
    }
}

schema_info = inspect_dataset_schema(
    view_name=mock_resolved["view_name"],
    filename=mock_resolved["filename"],
    resolved=mock_resolved
)
print("Inspected schema total columns:", schema_info["total_columns"])
print("Inspected schema total rows:", schema_info["total_rows"])
assert schema_info["total_columns"] == 5, f"Expected 5 columns, got {schema_info['total_columns']}"

response_data = format_schema_response(
    "How many total columns in the given dataset olist_geolocation_dataset.csv?",
    schema_info
)
print("\nFormatted Response Preview:\n" + response_data["response"])
assert "The dataset **olist_geolocation_dataset.csv** has **5 total columns**." in response_data["response"]
assert "geolocation_zip_code_prefix" in response_data["response"]
assert "geolocation_state" in response_data["response"]
assert response_data["sql_query"] == 'DESCRIBE "olist_geolocation_dataset";'
assert len(response_data["table"]["data"]) == 5

print("\n=== 3. Testing Planner Agent Direct Dispatch for Schema Metadata ===")
state = {
    "query": "How many total columns in the given dataset olist_geolocation_dataset.csv?",
    "workspace": "default",
    "dataset": None,
    "available_datasets": [mock_resolved],
    "completed_steps": [],
    "reasoning_path": []
}

planner_result = planner_agent(state)
print("\nPlanner Agent result intent:", planner_result.get("intent"))
print("Planner Agent final response:\n", planner_result.get("final_response"))
print("Planner Agent SQL query:", planner_result.get("sql_query"))
print("Planner Agent table rows count:", len(planner_result.get("table", {}).get("data", [])))

assert planner_result["intent"] == "schema_metadata"
assert "The dataset **olist_geolocation_dataset.csv** has **5 total columns**." in planner_result["final_response"]
assert planner_result["sql_query"] == 'DESCRIBE "olist_geolocation_dataset";'
assert len(planner_result["table"]["data"]) == 5

print("\nALL SCHEMA METADATA DETECTION AND RESOLUTION TESTS PASSED!")
