import requests
from jose import jwt
import json

BASE_URL = "https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io"
SECRET_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
token = jwt.encode({"sub": "saadazeem626@gmail.com", "role": "Owner"}, SECRET_KEY, algorithm="HS256")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

for ws in ["proj-75cc2d62", "proj-43d2ca3d", "Acme Corp", "default"]:
    print(f"\n--- Checking workspace: {ws} ---")
    r_docs = requests.get(f"{BASE_URL}/api/v1/rag/documents?workspace={ws}", headers=headers, timeout=15)
    print("Status:", r_docs.status_code)
    try:
        docs = r_docs.json()
        print("Docs:", json.dumps(docs, indent=2))
    except Exception as e:
        print("Err:", r_docs.text)

# Also let's run a query to DuckDB via /api/v1/sql/run if available to see what's in rag_chunks table on Azure
r_sql = requests.post(f"{BASE_URL}/api/v1/sql/run", json={"query": "SELECT workspace, filename, count(*) as count FROM rag_chunks GROUP BY workspace, filename", "project_id": "proj-75cc2d62"}, headers=headers, timeout=15)
print("\nSQL on rag_chunks status:", r_sql.status_code)
if r_sql.status_code == 200:
    print("SQL rows:", json.dumps(r_sql.json(), indent=2))
else:
    print("SQL error:", r_sql.text)
