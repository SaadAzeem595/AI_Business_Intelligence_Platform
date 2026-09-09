import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_current_user, MockUser

def set_test_user(user_id: str, role: str = "Analyst", workspace_id: str = "default"):
    mock_user = MockUser(
        id=user_id,
        email=f"{user_id}@datapilot.com",
        name=f"User {user_id.capitalize()}",
        role=role,
        workspace_id=workspace_id,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return mock_user

def test_new_user_starts_with_zero_projects():
    """Verify that a brand new user receives an empty list and NEVER any demo/mock projects."""
    client = TestClient(app)
    set_test_user("brand_new_user_999")
    
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    projects = response.json()
    assert isinstance(projects, list)
    assert len(projects) == 0, f"Expected 0 projects for new user, got: {projects}"

def test_no_unauthorized_demo_projects_returned():
    """Verify unauthorized demo projects never appear in the API response."""
    client = TestClient(app)
    set_test_user("audit_user_888")
    
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    project_names = [p["name"] for p in response.json()]
    
    assert "E-Commerce Executive Analytics" not in project_names
    assert "Financial Operations & Margin Control" not in project_names

def test_multi_user_workspace_strict_isolation():
    """Verify that projects created by User 1 are inaccessible and invisible to User 2."""
    client = TestClient(app)
    
    # 1. User Alpha creates project
    set_test_user("user_alpha")
    res1 = client.post("/api/v1/projects", json={"name": "Alpha Confidential Q4"})
    assert res1.status_code == 201
    alpha_proj_id = res1.json()["id"]
    
    # 2. User Beta lists projects
    set_test_user("user_beta")
    beta_list = client.get("/api/v1/projects")
    assert beta_list.status_code == 200
    beta_project_ids = [p["id"] for p in beta_list.json()]
    assert alpha_proj_id not in beta_project_ids, "User Beta should not see User Alpha's project"
    
    # 3. User Beta attempts direct access to Alpha's project -> 403 Forbidden
    beta_get = client.get(f"/api/v1/projects/{alpha_proj_id}")
    assert beta_get.status_code == 403, "User Beta must be forbidden from accessing User Alpha's project"

def test_project_lifecycle_authoritative_source_of_truth():
    """Verify creation, authoritative listing, and immediate removal upon deletion."""
    client = TestClient(app)
    set_test_user("lifecycle_user_777")
    
    # 1. Create project
    create_res = client.post("/api/v1/projects", json={
        "name": "Lifecycle Verified Workspace",
        "description": "Testing create, list, and delete consistency."
    })
    assert create_res.status_code == 201
    proj_id = create_res.json()["id"]
    
    # 2. List projects: project must appear
    list_res = client.get("/api/v1/projects")
    assert list_res.status_code == 200
    ids = [p["id"] for p in list_res.json()]
    assert proj_id in ids
    
    # 3. Delete project
    del_res = client.delete(f"/api/v1/projects/{proj_id}")
    assert del_res.status_code in (200, 204)
    
    # 4. List projects: project must be gone
    list_after_del = client.get("/api/v1/projects")
    assert list_after_del.status_code == 200
    ids_after = [p["id"] for p in list_after_del.json()]
    assert proj_id not in ids_after
