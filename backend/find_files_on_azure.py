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

print("Finding all order_items csv files in /app/app/uploads:")
files = run_query("SELECT file FROM glob('/app/app/uploads/*order_items*.csv')")
if files and 'rows' in files:
    for f in files['rows']:
        fpath = f['file']
        cnt_res = run_query(f"SELECT COUNT(*) as c FROM read_csv_auto('{fpath}')")
        c = cnt_res['rows'][0]['c'] if cnt_res and 'rows' in cnt_res else 'err'
        print(f"  {fpath} -> {c} rows")
