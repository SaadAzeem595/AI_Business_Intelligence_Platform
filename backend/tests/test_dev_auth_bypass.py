import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.core.config import settings
from app.core.dependencies import get_current_user, require_role, MockUser


def test_dev_auth_bypass_enabled():
    """
    Verifies that when DEV_AUTH_BYPASS is True (and environment is not production),
    requests are allowed without credentials, and the user resolves to Dev Admin.
    """
    # Temporarily force DEV_AUTH_BYPASS to True and ensure environment is development
    old_bypass = settings.DEV_AUTH_BYPASS
    old_env = settings.ENVIRONMENT
    old_node_env = settings.NODE_ENV
    old_app_env = settings.APP_ENV
    
    settings.DEV_AUTH_BYPASS = True
    settings.ENVIRONMENT = "development"
    settings.NODE_ENV = "development"
    settings.APP_ENV = "development"
    
    try:
        client = TestClient(app)
        
        # 1. Accessing /me endpoint should return the mock developer user with Admin role
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["id"] == "dev-user-001"
        assert user_data["email"] == "developer@datapilot.com"
        assert user_data["name"] == "Saad A."
        assert user_data["role"] == "Admin"
        
        # 2. Accessing a protected endpoint like datasets should succeed without auth headers
        response = client.get("/api/v1/datasets")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        
    finally:
        # Restore settings
        settings.DEV_AUTH_BYPASS = old_bypass
        settings.ENVIRONMENT = old_env
        settings.NODE_ENV = old_node_env
        settings.APP_ENV = old_app_env


def test_dev_auth_bypass_disabled():
    """
    Verifies that when DEV_AUTH_BYPASS is False, unauthenticated requests
    to protected endpoints are blocked (return 401).
    """
    old_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    
    try:
        client = TestClient(app)
        
        # Accessing /me without headers should return 401 in non-test mode,
        # but in test mode it falls back to the original MockUser (which has Owner role).
        # To test the real production JWT check, we can verify that bad credentials still fail.
        bad_headers = {"Authorization": "Bearer invalidtoken123"}
        response = client.get("/api/v1/auth/me", headers=bad_headers)
        assert response.status_code == 401
        
    finally:
        settings.DEV_AUTH_BYPASS = old_bypass


def test_production_environment_rejects_bypass():
    """
    Verifies that starting or validating the configuration in production mode
    with DEV_AUTH_BYPASS=True raises a ValidationError.
    """
    from app.core.config import Settings
    
    # 1. ENVIRONMENT = production
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DEV_AUTH_BYPASS=True
        )
    assert "DEV_AUTH_BYPASS cannot be enabled in a production environment" in str(excinfo.value)
    
    # 2. NODE_ENV = production
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            NODE_ENV="production",
            DEV_AUTH_BYPASS=True
        )
    assert "DEV_AUTH_BYPASS cannot be enabled in a production environment" in str(excinfo.value)

    # 3. APP_ENV = production
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            APP_ENV="production",
            DEV_AUTH_BYPASS=True
        )
    assert "DEV_AUTH_BYPASS cannot be enabled in a production environment" in str(excinfo.value)


def test_rbac_with_bypass():
    """
    Verifies that require_role checks allow the Dev Admin user
    when DEV_AUTH_BYPASS is enabled, but enforce roles normally otherwise.
    """
    test_app = FastAPI()
    
    @test_app.get("/executive-only", dependencies=[Depends(require_role(["Executive"]))])
    def executive_endpoint():
        return {"status": "authorized"}

    client = TestClient(test_app)
    
    old_bypass = settings.DEV_AUTH_BYPASS
    old_env = settings.ENVIRONMENT
    old_node_env = settings.NODE_ENV
    old_app_env = settings.APP_ENV
    
    try:
        # 1. When bypass is enabled, should be authorized
        settings.DEV_AUTH_BYPASS = True
        settings.ENVIRONMENT = "development"
        settings.NODE_ENV = "development"
        settings.APP_ENV = "development"
        
        response = client.get("/executive-only")
        assert response.status_code == 200
        assert response.json() == {"status": "authorized"}
        
        # 2. When bypass is disabled, a user without "Executive" (like Admin or Viewer) is blocked
        settings.DEV_AUTH_BYPASS = False
        
        # Inject Mock user with Admin role (which is not in ["Executive"])
        def mock_admin():
            return MockUser(id="1", email="admin@test.com", role="Admin")
            
        test_app.dependency_overrides[get_current_user] = mock_admin
        
        response = client.get("/executive-only")
        assert response.status_code == 403
        
    finally:
        settings.DEV_AUTH_BYPASS = old_bypass
        settings.ENVIRONMENT = old_env
        settings.NODE_ENV = old_node_env
        settings.APP_ENV = old_app_env
        test_app.dependency_overrides.clear()
