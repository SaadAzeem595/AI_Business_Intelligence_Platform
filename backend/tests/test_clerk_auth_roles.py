import pytest
import io
import uuid
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.dependencies import (
    get_current_user,
    require_role,
    MockUser,
    extract_role_from_payload,
)
from app.core.database import get_db_session
from app.features.auth.models import User


def test_extract_role_from_payload_defaults_and_metadata():
    """Verifies that role extraction properly parses various Clerk metadata formats and defaults to Owner."""
    # 1. Default when no role is present
    assert extract_role_from_payload({"sub": "user_123"}) == "Owner"
    assert extract_role_from_payload({}) == "Owner"

    # 2. Direct role claim
    assert extract_role_from_payload({"role": "admin"}) == "Admin"
    assert extract_role_from_payload({"role": "Analyst"}) == "Analyst"

    # 3. Public metadata
    assert extract_role_from_payload({"public_metadata": {"role": "executive"}}) == "Executive"

    # 4. Unsafe metadata
    assert extract_role_from_payload({"unsafe_metadata": {"role": "admin"}}) == "Admin"

    # 5. Org role
    assert extract_role_from_payload({"org_role": "org:admin"}) == "Admin"
    assert extract_role_from_payload({"org_role": "org:member"}) == "Analyst"

    # 6. User details fallback
    assert extract_role_from_payload(
        {"sub": "user_123"},
        user_details={"public_metadata": {"role": "Admin"}}
    ) == "Admin"


def test_require_role_owner_bypass_and_case_insensitivity():
    """Verifies that Owner bypasses all checks, and role matching is case-insensitive."""
    test_app = FastAPI()

    @test_app.get("/analyst-admin-endpoint", dependencies=[Depends(require_role(["Analyst", "Admin"]))])
    def protected_endpoint():
        return {"status": "authorized"}

    client = TestClient(test_app)

    # 1. Owner bypasses check even though "Owner" is not in ["Analyst", "Admin"]
    def mock_owner():
        return MockUser(id="owner-1", email="owner@test.com", role="Owner")
    test_app.dependency_overrides[get_current_user] = mock_owner
    res = client.get("/analyst-admin-endpoint")
    assert res.status_code == 200
    assert res.json() == {"status": "authorized"}

    # 2. Lowercase "owner" also bypasses
    def mock_lowercase_owner():
        return MockUser(id="owner-2", email="owner2@test.com", role="owner")
    test_app.dependency_overrides[get_current_user] = mock_lowercase_owner
    res = client.get("/analyst-admin-endpoint")
    assert res.status_code == 200

    # 3. Lowercase "admin" matches "Admin"
    def mock_lowercase_admin():
        return MockUser(id="admin-1", email="admin@test.com", role="admin")
    test_app.dependency_overrides[get_current_user] = mock_lowercase_admin
    res = client.get("/analyst-admin-endpoint")
    assert res.status_code == 200

    # 4. Viewer is rejected
    def mock_viewer():
        return MockUser(id="viewer-1", email="viewer@test.com", role="Viewer")
    test_app.dependency_overrides[get_current_user] = mock_viewer
    res = client.get("/analyst-admin-endpoint")
    assert res.status_code == 403
    assert "Access denied: insufficient permission privileges." in res.json()["detail"]


@pytest.mark.anyio
async def test_clerk_user_default_owner_and_auto_heal():
    """
    Tests that a new Clerk user without role claim receives Owner role,
    and an existing DB user stuck with Viewer is auto-healed to Owner.
    """
    client = TestClient(app)

    # Use a unique clerk ID to avoid collisions
    unique_clerk_id = f"clerk_test_{uuid.uuid4().hex[:8]}"

    # Simulate request with mock_clerk_token_unknown (which has no role claim)
    # Token format in testing: mock_clerk_token_<type>
    headers = {"Authorization": f"Bearer mock_clerk_token_{unique_clerk_id}"}

    # 1. Create a project - should succeed and assign Owner
    create_payload = {"name": f"Clerk Project {unique_clerk_id[:4]}"}
    resp = client.post("/api/v1/projects", json=create_payload, headers=headers)
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # 2. Upload dataset to the project - should succeed without 403 Forbidden
    csv_file = io.BytesIO(b"id,name,value\n1,Product A,100\n2,Product B,200")
    files = {"file": ("test_clerk.csv", csv_file, "text/csv")}
    upload_resp = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files=files,
        data={"tableName": "test_clerk_table"},
        headers=headers
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["project_id"] == project_id
    assert upload_resp.json()["rows"] == 2


@pytest.mark.anyio
async def test_existing_viewer_user_auto_healed():
    """
    Directly tests that an existing user created in DB with role='Viewer'
    is promoted to 'Owner' when making an authenticated request.
    """
    client = TestClient(app)
    suffix = uuid.uuid4().hex[:8]
    viewer_clerk_id = f"clerk_id_{suffix}"

    # Manually seed a user with Viewer role in DB
    session_generator = get_db_session()
    db = await anext(session_generator)
    try:
        stuck_user = User(
            id=str(uuid.uuid4()),
            clerk_user_id=viewer_clerk_id,
            email=f"{viewer_clerk_id}@test.com",
            name="Stuck User",
            role="Viewer",  # Simulating the old bug
            is_active=True,
            hashed_password="hash"
        )
        db.add(stuck_user)
        await db.commit()
    finally:
        await db.close()

    # Now make request as this user with a token without explicit role
    headers = {"Authorization": f"Bearer mock_clerk_token_{suffix}"}
    create_payload = {"name": "Auto-Heal Test Project"}
    resp = client.post("/api/v1/projects", json=create_payload, headers=headers)
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # Upload dataset - should succeed because user was promoted from Viewer to Owner
    csv_file = io.BytesIO(b"metric,score\nlatency,15\nthroughput,500")
    files = {"file": ("healed.csv", csv_file, "text/csv")}
    upload_resp = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files=files,
        data={"tableName": "healed_table"},
        headers=headers
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["rows"] == 2

    # Verify that DB row now has role='Owner'
    db = await anext(get_db_session())
    try:
        stmt = select(User).where(User.clerk_user_id == viewer_clerk_id)
        res = await db.execute(stmt)
        updated_user = res.scalars().first()
        assert updated_user is not None
        assert updated_user.role == "Owner"
    finally:
        await db.close()
