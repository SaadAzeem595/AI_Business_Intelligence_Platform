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
        print(f"Error {r.status_code}: {r.text}")
        return None
    return r.json()

print("Columns in olist_orders_dataset:")
cols = run_query("DESCRIBE olist_orders_dataset")
print(cols)

print("\nSample rows from olist_orders_dataset:")
sample = run_query("SELECT * FROM olist_orders_dataset LIMIT 3")
print(sample)
