import pytest
import io
import os
import json
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user, MockUser

def set_active_user(user_id: str, role: str = "Analyst"):
    mock_user = MockUser(
        id=user_id,
        email=f"{user_id}@datapilot.com",
        name=f"User {user_id.upper()}",
        role=role
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return mock_user

def test_sql_playground_dynamic_schema_and_execution():
    """Tests dynamic project dataset creation, DuckDB schema reflection, and query execution."""
    client = TestClient(app)
    set_active_user("sql_test_user")

    # 1. Create a Project
    proj_resp = client.post("/api/v1/projects", json={"name": "SQL Workspace Project", "description": "Testing dynamic SQL"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Verify empty schema for new project (no hardcoded fallback tables)
    schema_resp = client.get(f"/api/v1/sql/schema?project_id={project_id}")
    assert schema_resp.status_code == 200
    empty_schema = schema_resp.json()
    assert isinstance(empty_schema, list)
    assert len(empty_schema) == 0

    # 3. Upload a sample CSV dataset to the project
    csv_content = (
        "transaction_id,customer_name,amount,region,status\n"
        "TX-101,Acme Corp,1500.50,North,Active\n"
        "TX-102,Globex,2400.00,South,Pending\n"
        "TX-103,Initech,850.75,North,Active\n"
    )
    file_tuple = ("test_transactions.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
    upload_resp = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": file_tuple},
        data={"tableName": "test_transactions"}
    )
    assert upload_resp.status_code == 200
    dataset_data = upload_resp.json()
    table_name = dataset_data.get("duckdb_table") or "test_transactions"

    # 4. Fetch dynamic DuckDB schema for project
    schema_resp = client.get(f"/api/v1/sql/schema?project_id={project_id}")
    assert schema_resp.status_code == 200
    project_schema = schema_resp.json()
    assert len(project_schema) >= 1

    table_meta = next((t for t in project_schema if t["name"] == table_name), project_schema[0])
    assert table_meta["rowsCount"] == 3
    col_names = [c["name"] for c in table_meta["columns"]]
    assert "transaction_id" in col_names
    assert "customer_name" in col_names
    assert "amount" in col_names

    # 5. Execute SQL Query against project's DuckDB view
    query = f"SELECT customer_name, amount, region FROM {table_name} WHERE region = 'North' ORDER BY amount DESC;"
    run_resp = client.post("/api/v1/sql/run", json={"query": query, "project_id": project_id})
    assert run_resp.status_code == 200
    results = run_resp.json()
    assert "columns" in results
    assert "rows" in results
    assert len(results["rows"]) == 2
    assert results["rows"][0]["customer_name"] == "Acme Corp"
    assert results["rows"][0]["amount"] == 1500.50

    # 6. Test invalid SQL error handling
    invalid_resp = client.post("/api/v1/sql/run", json={"query": "SELECT * FROM non_existent_table_xyz;", "project_id": project_id})
    assert invalid_resp.status_code == 400
    assert "SQL execution error" in invalid_resp.json()["detail"] or "does not exist" in invalid_resp.json()["detail"]

    app.dependency_overrides.clear()
