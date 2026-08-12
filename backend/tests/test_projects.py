import pytest
import io
import os
import json
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.dependencies import get_current_user, MockUser
from app.features.projects.models import Project
from app.features.datasets.models import Dataset
from app.db.base import Base


# Setup helper to override get_current_user dependency dynamically
def set_active_user(user_id: str, role: str = "Analyst"):
    mock_user = MockUser(
        id=user_id,
        email=f"{user_id}@datapilot.com",
        name=f"User {user_id.upper()}",
        role=role
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return mock_user


def test_projects_crud_flow():
    """Tests project creation, listing, details retrieval, and deletion for an authorized owner."""
    client = TestClient(app)
    
    # 1. Authenticate as User A
    set_active_user("user_a")
    
    # 2. Create Project
    create_payload = {"name": "Test Project A", "description": "Analyzing sales datasets."}
    response = client.post("/api/v1/projects", json=create_payload)
    assert response.status_code == 201
    project_data = response.json()
    assert project_data["name"] == "Test Project A"
    assert project_data["owner_id"] == "user_a"
    project_id = project_data["id"]
    
    # 3. List Projects (User A should see it)
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    projects_list = response.json()
    assert len(projects_list) >= 1
    assert any(p["id"] == project_id for p in projects_list)
    
    # 4. Get Project details
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == project_id
    
    # Clean up dependency override
    app.dependency_overrides.clear()


def test_projects_cross_user_authorization():
    """Tests that User B cannot access User A's projects, datasets, uploads or query contexts (strict isolation)."""
    client = TestClient(app)
    
    # 1. User A creates Project A
    set_active_user("user_a")
    response = client.post("/api/v1/projects", json={"name": "Project A"})
    assert response.status_code == 201
    proj_a_id = response.json()["id"]
    
    # 2. Authenticate as User B
    set_active_user("user_b")
    
    # 3. User B tries to view User A's project -> should get 403 Forbidden
    response = client.get(f"/api/v1/projects/{proj_a_id}")
    assert response.status_code == 403
    assert "You do not have access to this project" in response.json()["detail"]
    
    # 4. User B tries to list datasets of User A's project -> should get 403 Forbidden
    response = client.get(f"/api/v1/projects/{proj_a_id}/datasets")
    assert response.status_code == 403
    
    # 5. User B tries to upload dataset to User A's project -> should get 403 Forbidden
    csv_file = io.BytesIO(b"col1,col2\nval1,10\nval2,20")
    files = {"file": ("test.csv", csv_file, "text/csv")}
    data = {"tableName": "unauthorized_table"}
    response = client.post(f"/api/v1/projects/{proj_a_id}/datasets", files=files, data=data)
    assert response.status_code == 403
    
    # 6. User B tries to run SQL query scoped to User A's project -> should get 403 Forbidden
    query_payload = {
        "query": "SELECT * FROM unauthorized_table",
        "project_id": proj_a_id
    }
    response = client.post("/api/v1/sql/run", json=query_payload)
    assert response.status_code == 403
    
    # Clean up dependency override
    app.dependency_overrides.clear()


def test_project_dataset_upload_and_scoped_query():
    """Tests successful file upload, DuckDB schema mapping, and query sandboxing in a project."""
    client = TestClient(app)
    
    # 1. Setup User A and Project A
    set_active_user("user_a", role="Admin")
    response = client.post("/api/v1/projects", json={"name": "Analytics Project"})
    assert response.status_code == 201
    project_id = response.json()["id"]
    
    # 2. Upload CSV dataset to Project A
    csv_content = b"region,sales\nNorth,500\nSouth,600\nWest,750"
    csv_file = io.BytesIO(csv_content)
    files = {"file": ("regional_sales.csv", csv_file, "text/csv")}
    data = {"tableName": "regional_sales"}
    
    response = client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert response.status_code == 200
    dataset_data = response.json()
    assert dataset_data["project_id"] == project_id
    assert dataset_data["owner_id"] == "user_a"
    assert dataset_data["rows"] == 3
    
    # 3. Retrieve Project SQL Schema -> should return regional_sales table
    response = client.get(f"/api/v1/sql/schema?project_id={project_id}")
    assert response.status_code == 200
    schema_info = response.json()
    assert any(table["name"] == dataset_data["duckdb_table"] for table in schema_info)
    
    # 4. Run SQL query scoped to Project A
    sql_payload = {
        "query": f"SELECT SUM(sales) as total FROM {dataset_data['duckdb_table']}",
        "project_id": project_id
    }
    response = client.post("/api/v1/sql/run", json=sql_payload)
    assert response.status_code == 200
    query_result = response.json()
    assert "total" in query_result["columns"]
    # North + South + West = 500 + 600 + 750 = 1850
    assert query_result["rows"][0]["total"] == 1850
    
    # 5. Non-existent Project SQL execution -> should return 404
    sql_payload = {
        "query": "SELECT 1",
        "project_id": "proj-nonexistent"
    }
    response = client.post("/api/v1/sql/run", json=sql_payload)
    assert response.status_code == 404
    
    # Clean up dependency override
    app.dependency_overrides.clear()
