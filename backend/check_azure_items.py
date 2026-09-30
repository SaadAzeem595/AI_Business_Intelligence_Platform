import time
import json
import requests
from jose import jwt

BASE_URL = "https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io"
WEB_ORIGIN = "https://datapilot-web.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io"
SECRET_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
PROJECT_ID = "proj-75cc2d62"

now = int(time.time())
token_payload = {
    "sub": "saadazeem626@gmail.com",
    "email": "saadazeem626@gmail.com",
    "role": "Owner",
    "iat": now,
    "exp": now + 86400
}
token = jwt.encode(token_payload, SECRET_KEY, algorithm="HS256")
headers = {
    "Authorization": f"Bearer {token}",
    "Origin": WEB_ORIGIN,
    "Content-Type": "application/json"
}

def run_query(sql):
    r = requests.post(
        f"{BASE_URL}/api/v1/sql/run",
        json={"query": sql, "project_id": PROJECT_ID},
        headers=headers,
        timeout=30
    )
    if r.status_code != 200:
        return None
    return r.json()

# Let's find MAX row count among all order items files
q = """
SELECT 
    view_name, 
    sql 
FROM duckdb_views() 
WHERE view_name LIKE '%order_items%'
"""
print(run_query(q))
