import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.config import settings
from app.core.cache import cache_client
from app.core.dependencies import require_role, MockUser, get_current_user

# 1. Health Endpoints Tests
def test_health_and_probes():
    client = TestClient(app)
    
    # Test Liveness probe
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    
    # Test Core Health check
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    
    # Test Readiness probe
    response = client.get("/ready")
    # Since Postgres/Redis might be offline in test environment, it could return 503 or 200
    assert response.status_code in [200, 503]
    
    # Test Prometheus Metrics
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "# HELP" in response.text

# 2. JWT and Security Authentication Tests
def test_jwt_auth_and_endpoints():
    client = TestClient(app)
    
    # Register/Login
    reg_payload = {"email": "testuser@example.com", "password": "securepassword", "name": "Test User"}
    response = client.post("/api/v1/auth/register", data=reg_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "accessToken" in token_data
    access_token = token_data["accessToken"]
    
    # Fetch profile with valid token
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "testuser@example.com"
    
    # Fetch profile with invalid token
    bad_headers = {"Authorization": "Bearer invalidtoken123"}
    response = client.get("/api/v1/auth/me", headers=bad_headers)
    assert response.status_code == 401
    
    # Test API Key Auth
    key_headers = {"X-API-Key": "admin-secret-api-key-12345"}
    response = client.get("/api/v1/auth/me", headers=key_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "api-key-client@platform.com"
    assert response.json()["role"] == "Analyst"
    
    # Test invalid API Key
    bad_key_headers = {"X-API-Key": "bad-key-999"}
    response = client.get("/api/v1/auth/me", headers=bad_key_headers)
    assert response.status_code == 401

# 3. JWT Token Refresh Tests
def test_jwt_token_refresh():
    client = TestClient(app)
    
    login_payload = {"username": "testuser@example.com", "password": "securepassword"}
    response = client.post("/api/v1/auth/login", data=login_payload)
    assert response.status_code == 200
    data = response.json()
    
    # Build a mock refresh token manually or parse it
    refresh_token = jwt.encode(
        {"sub": "testuser@example.com", "role": "Analyst"},
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    
    refresh_payload = {"refreshToken": refresh_token}
    response = client.post("/api/v1/auth/refresh", data=refresh_payload)
    assert response.status_code == 200
    new_token = response.json()
    assert "accessToken" in new_token
    assert new_token["user"]["email"] == "testuser@example.com"

# 4. Role-Based Access Control (RBAC) Tests
def test_rbac_dependency():
    # Setup a dummy app to test RBAC logic in isolation
    test_app = FastAPI()
    
    @test_app.get("/admin-only", dependencies=[require_role(["Admin"])])
    def admin_endpoint():
        return {"status": "authorized"}
        
    @test_app.get("/executive-or-analyst", dependencies=[require_role(["Executive", "Analyst"])])
    def executive_endpoint():
        return {"status": "authorized"}

    # Mock authenticate
    def mock_admin():
        return MockUser(id="1", email="admin@test.com", role="Admin")
        
    def mock_analyst():
        return MockUser(id="2", email="analyst@test.com", role="Analyst")
        
    def mock_viewer():
        return MockUser(id="3", email="viewer@test.com", role="Viewer")

    # 1. Test Admin accessing Admin-only endpoint
    test_app.dependency_overrides[get_current_user] = mock_admin
    client = TestClient(test_app)
    response = client.get("/admin-only")
    assert response.status_code == 200
    
    # 2. Test Analyst accessing Admin-only endpoint (expect 403)
    test_app.dependency_overrides[get_current_user] = mock_analyst
    response = client.get("/admin-only")
    assert response.status_code == 403
    
    # 3. Test Analyst accessing Executive/Analyst endpoint
    response = client.get("/executive-or-analyst")
    assert response.status_code == 200
    
    # 4. Test Viewer accessing Executive/Analyst endpoint (expect 403)
    test_app.dependency_overrides[get_current_user] = mock_viewer
    response = client.get("/executive-or-analyst")
    assert response.status_code == 403

# 5. Caching Layer Tests
@pytest.mark.anyio
async def test_cache_client_operations():
    # Explicitly clear
    await cache_client.clear()
    
    # Set cache
    await cache_client.set("test_key", {"data": "hello_world"}, ttl=10)
    
    # Get cache
    val = await cache_client.get("test_key")
    assert val == {"data": "hello_world"}
    
    # Invalidate cache
    await cache_client.invalidate("test_key")
    val_after = await cache_client.get("test_key")
    assert val_after is None
    
    # Pattern invalidate
    await cache_client.set("pattern:1", "val1", ttl=10)
    await cache_client.set("pattern:2", "val2", ttl=10)
    await cache_client.set("other:key", "val3", ttl=10)
    
    await cache_client.invalidate_pattern("pattern:*")
    assert await cache_client.get("pattern:1") is None
    assert await cache_client.get("pattern:2") is None
    assert await cache_client.get("other:key") == "val3"

# 6. Rate Limiting Tests
def test_rate_limiting_middleware():
    client = TestClient(app)
    
    # Override settings limit dynamically to trigger 429 quickly
    settings.RATE_LIMIT_PER_MINUTE = 5
    
    # Send 6 quick requests to triggers limit (bypass health check)
    responses = []
    for _ in range(7):
        resp = client.get("/api/v1/auth/me")
        responses.append(resp.status_code)
        
    assert 429 in responses
    
    # Reset limit
    settings.RATE_LIMIT_PER_MINUTE = 100
