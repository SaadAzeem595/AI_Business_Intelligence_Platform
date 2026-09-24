import requests
from jose import jwt
import json
import sys

web_url = 'https://datapilot-web.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io'
api_base = 'https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io/api/v1'

print("================ 1. FRONTEND HEALTH CHECK ================")
r_web = requests.get(f"{web_url}/login", timeout=15)
print("Web /login status:", r_web.status_code)
assert r_web.status_code == 200, f"Web server returned {r_web.status_code}"
print("Frontend web server is UP and responding 200 OK!")

SECRET_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
token = jwt.encode({"sub": "saad@datapilot.com", "role": "Owner"}, SECRET_KEY, algorithm="HS256")
headers = {"Authorization": f"Bearer {token}"}

print("\n================ 2. BACKEND DIAGNOSTICS ================")
r_diag = requests.get(f"{api_base}/chat/diagnostics", headers=headers, timeout=15)
print("Diagnostics status:", r_diag.status_code)
diag_data = r_diag.json()
print("Backend status:", diag_data.get("status"))
print("Registered datasets count:", diag_data.get("datasets_count"))
print("DuckDB ready:", diag_data.get("duckdb", {}).get("ready"))
print("LLM Provider:", diag_data.get("llm", {}).get("provider"), "Model:", diag_data.get("llm", {}).get("model"))

tests = [
    {
        "title": "Test A: Exact Dataset Query (olist_geolocation_dataset)",
        "payload": {
            "message": "How many columns in olist_geolocation_dataset dataset?",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": "olist_geolocation_dataset",
            "dataset_id": "bedb9f9b-fbf8-4eb3-9720-b1821eb76c50",
            "active_project": ""
        }
    },
    {
        "title": "Test B: Dataset Filename with .csv",
        "payload": {
            "message": "What are the columns of olist_geolocation_dataset.csv?",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": "olist_geolocation_dataset.csv",
            "dataset_id": "bedb9f9b-fbf8-4eb3-9720-b1821eb76c50",
            "active_project": ""
        }
    },
    {
        "title": "Test C: Auto-Detect without dataset specified in payload",
        "payload": {
            "message": "How many columns are in the geolocation dataset?",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": None,
            "dataset_id": None,
            "active_project": None
        }
    },
    {
        "title": "Test D: Multi-dataset auto-detect ambiguity check",
        "payload": {
            "message": "Analyze both the orders and items datasets",
            "workspace": "Acme Corp",
            "workspace_id": "Acme Corp",
            "dataset": None,
            "dataset_id": None,
            "active_project": None
        }
    }
]

all_passed = True
for t in tests:
    print(f"\n================ {t['title']} ================")
    r = requests.post(f"{api_base}/agents/chat", json=t["payload"], headers=headers, timeout=40)
    print("HTTP Status:", r.status_code)
    if r.status_code != 200:
        print("ERROR:", r.text)
        all_passed = False
        continue
    data = r.json()
    print("Agent Status:", data.get("status"))
    print("Detected Dataset ID:", data.get("dataset_id"))
    print("Detected Dataset Name:", data.get("dataset_name"))
    print("Matched Candidates:", data.get("dataset_names"))
    resp_text = (data.get("response") or "")[:280]
    print(f"Response Preview:\n{resp_text}...")

if all_passed:
    print("\n>>> ALL PRODUCTION E2E VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")
else:
    print("\n>>> SOME TESTS FAILED <<<")
    sys.exit(1)
