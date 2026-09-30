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

print(f"Connecting to live production API at {BASE_URL}...")
# 1. Fetch Schema Info to discover Olist dataset candidates
r = requests.get(f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/forecast/schema-info", headers=headers, timeout=30)
print(f"Schema info status: {r.status_code}")
schema_data = r.json()
candidates = schema_data.get("candidates", [])
print(f"Discovered {len(candidates)} candidates:")

olist_cand = next((c for c in candidates if c.get("dataset_id") == "olist_relational_derived"), None)
if not olist_cand:
    olist_cand = next((c for c in candidates if "order_purchase_timestamp" in c.get("date_columns", [])), candidates[0])

print(f"\nTarget Candidate: {olist_cand.get('dataset_name')} (ID: {olist_cand.get('dataset_id')})")
target_dataset_id = olist_cand["dataset_id"]
date_col = "order_purchase_timestamp"
target_metric = olist_cand["metric_columns"][0]

print(f"[TESTING LIVE FORECAST] Target: dataset={target_dataset_id}, date={date_col}, metric={target_metric}")
forecast_payload = {
    "dataset_id": target_dataset_id,
    "date_column": date_col,
    "target_column": target_metric,
    "aggregation": "monthly",
    "horizon": 6,
    "model": "auto",
    "confidence": 0.95
}

r_fc = requests.post(f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/forecast", json=forecast_payload, headers=headers, timeout=60)
print(f"Forecast response status: {r_fc.status_code}")
res_json = r_fc.json()

if res_json.get("status") == "error":
    print("Forecast returned error status:")
    print(f"  Message: {res_json.get('message')}")
    print(json.dumps(res_json, indent=2))
    exit(1)

print("\nSUCCESS! Live forecast response received:")
print(f"  Status: {res_json.get('status')}")
print(f"  Model Selected: {res_json.get('selected_model')}")
date_detection = res_json.get("date_detection") or {}
print(f"  Date Detection Metadata:")
print(f"    Detected Format: {date_detection.get('format')}")
print(f"    DuckDB Format:   {date_detection.get('duckdb_format')}")
print(f"    Parse Success:   {date_detection.get('parse_success_rate')}")
print(f"    Valid Count:     {date_detection.get('valid_count')}")
print(f"    Invalid Count:   {date_detection.get('invalid_count')}")
print(f"    Min Date:        {date_detection.get('min')}")
print(f"    Max Date:        {date_detection.get('max')}")

timeline = res_json.get("timeline", [])
historical = [t for t in timeline if not t.get("is_forecast")]
forecasted = [t for t in timeline if t.get("is_forecast")]
print(f"  Total timeline points: {len(timeline)}")
print(f"  Historical observations: {len(historical)}")
print(f"  Forecasted future points: {len(forecasted)}")
assert len(historical) > 1, f"Expected multiple historical observations, got {len(historical)}"
assert len(forecasted) == 6, f"Expected 6 forecasted points, got {len(forecasted)}"

print("\nTimeline sample (first 3 actuals and last 3 forecasts):")
for t in timeline[:3]:
    print(f"    [ACTUAL]   {t.get('date')} | val={t.get('actual')}")
for t in timeline[-3:]:
    print(f"    [FORECAST] {t.get('date')} | val={t.get('forecast')} | bounds=({t.get('lower_bound')}, {t.get('upper_bound')})")

summary = res_json.get("business_summary") or {}
print(f"\nBusiness Summary Headline: {summary.get('headline')}")
print(f"Projected Growth: {summary.get('growth_percentage')}%")
print(f"Insights Count: {len(res_json.get('insights', []))}")
for ins in res_json.get("insights", []):
    print(f"  - {ins.get('type')}: {ins.get('message')}")
