import sys
import os

backend_dir = r"d:\AI Business Intelligence Platform\backend"
sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_current_user, MockUser

client = TestClient(app)

# Simulate a Clerk user in production with an external/custom workspace_id
mock_user = MockUser(id="user_clerk_prod_999", email="saad@datapilot.com", name="Saad Alvi", role="Owner", workspace_id="ws_user_clerk_prod_999")
app.dependency_overrides[get_current_user] = lambda: mock_user

cases = [
    {
        "name": "Case 1: User asks with dataset display_name (like dropdown selection)",
        "payload": {
            "message": "How many columns in olist_geolocation_dataset dataset?",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": "olist_geolocation_dataset",
            "dataset_id": "7f8a1638-9a21-4312-9108-53df538b67d9",
            "active_project": ""
        }
    },
    {
        "name": "Case 2: User asks with dataset filename with .csv",
        "payload": {
            "message": "How many columns in olist_geolocation_dataset dataset?",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": "olist_geolocation_dataset.csv",
            "active_project": ""
        }
    },
    {
        "name": "Case 3: User mentions dataset in text without dropdown selection (dataset=None, active_project=None)",
        "payload": {
            "message": "How many columns in olist_geolocation_dataset dataset?",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": None,
            "dataset_id": None,
            "active_project": None
        }
    },
]

for test in cases:
    print(f"\n==========================================")
    print(f"Running: {test['name']}")
    print(f"Payload: {test['payload']}")
    response = client.post("/api/v1/agents/chat", json=test["payload"])
    print("Status Code:", response.status_code)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    resp_text = data.get("response") or data.get("content") or ""
    print("Final Response Content:\n", resp_text)
    
    # Assert that it DID NOT return the 'No datasets are currently available' error
    assert "No datasets are currently available" not in resp_text, f"Failed on {test['name']}: {resp_text}"
    # Assert that it returned the column count / schema information
    assert "5" in resp_text or "geolocation" in resp_text.lower(), f"Expected column info in: {resp_text}"
    print(f"PASSED: {test['name']}")

print("\nALL E2E SCHEMA CHAT TESTS PASSED SUCCESSFULLY!")
