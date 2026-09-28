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

def verify_all():
    print("=================================================================")
    print("      AZURE CONTAINER APPS PRODUCTION VERIFICATION SUITE         ")
    print(f"Target API:    {BASE_URL}")
    print(f"Client Origin: {WEB_ORIGIN}")
    print(f"Target Project: {PROJECT_ID}")
    print("=================================================================\n")
    
    # 1. Health check
    print("[STEP 1/5] Testing GET /health...")
    r = requests.get(f"{BASE_URL}/health", headers={"Origin": WEB_ORIGIN}, timeout=30)
    print(f"  Status: {r.status_code}")
    print(f"  Body:   {r.text}")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    health_json = r.json()
    assert health_json.get("status") == "healthy", "FastAPI app is not healthy"
    print("  --> GET /health: PASSED\n")

    # 2. Live check
    print("[STEP 2/5] Testing GET /live...")
    r = requests.get(f"{BASE_URL}/live", headers={"Origin": WEB_ORIGIN}, timeout=30)
    print(f"  Status: {r.status_code}")
    assert r.status_code == 200, f"Live check failed: {r.status_code}"
    print("  --> GET /live: PASSED\n")

    # 3. Forecast Schema Info
    print("[STEP 3/5] Testing GET /api/v1/projects/{project_id}/forecast/schema-info...")
    r = requests.get(
        f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/forecast/schema-info",
        headers=headers,
        timeout=30
    )
    print(f"  Status: {r.status_code}")
    print(f"  CORS Origin: {r.headers.get('access-control-allow-origin')}")
    assert r.status_code == 200, f"Schema info failed: {r.status_code} {r.text}"
    assert r.headers.get("access-control-allow-origin") == WEB_ORIGIN, "Missing or incorrect CORS header"
    schema_info = r.json()
    assert schema_info.get("has_time_series") is True, "has_time_series should be True"
    assert len(schema_info.get("candidates", [])) > 0, "No candidates returned"
    print(f"  Candidates discovered: {len(schema_info['candidates'])}")
    for c in schema_info["candidates"]:
        print(f"    - {c.get('dataset_name')} (ID: {c.get('dataset_id')})")
    print("  --> Schema Info & CORS: PASSED\n")

    # 4. Multi-Horizon Time-Series Forecasting
    print("[STEP 4/5] Testing POST /api/v1/projects/{project_id}/forecast on 99k dataset...")
    forecast_payload = {
        "dataset_id": "866c9641-9f2a-4db5-999f-f084aacc9231",
        "date_column": "review_creation_date",
        "target_column": "review_score",
        "aggregation": "monthly",
        "horizon": 6,
        "model": "auto"
    }
    r = requests.post(
        f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/forecast",
        json=forecast_payload,
        headers=headers,
        timeout=60
    )
    print(f"  Status: {r.status_code}")
    print(f"  CORS Origin: {r.headers.get('access-control-allow-origin')}")
    assert r.status_code == 200, f"Forecast endpoint failed: {r.status_code} {r.text}"
    assert r.headers.get("access-control-allow-origin") == WEB_ORIGIN, "Missing CORS header on forecast"
    f_res = r.json()
    assert f_res.get("status") == "success", f"Forecast error: {f_res.get('message')}"
    print(f"  Model Selected:     {f_res.get('selected_model')}")
    print(f"  Observations:       {len(f_res.get('timeline', []))} timeline points")
    print(f"  Metrics Count:      {len(f_res.get('metrics', []))} models evaluated")
    for m in f_res.get("metrics", []):
        print(f"    * {m.get('model_name')}: MAE={m.get('mae')}, RMSE={m.get('rmse')}, is_best={m.get('is_best')}")
    summary = f_res.get("business_summary") or {}
    print(f"  Summary Headline:   {summary.get('headline')}")
    print(f"  Growth Projected:   {summary.get('growth_percentage')}%")
    print(f"  Insights Count:     {len(f_res.get('insights', []))}")
    print(f"  Recommendations:    {len(f_res.get('recommendations', []))}")
    print("  --> Forecast Pipeline & ML Inference: PASSED\n")

    # 5. DuckDB SQL Query Execution
    print("[STEP 5/5] Testing POST /api/v1/sql/run with DuckDB query...")
    sql_payload = {
        "project_id": PROJECT_ID,
        "query": "SELECT count(*) AS total_reviews, min(review_creation_date) AS min_date, max(review_creation_date) AS max_date FROM project_proj_75cc2d62_olist_order_reviews_dataset"
    }
    r = requests.post(
        f"{BASE_URL}/api/v1/sql/run",
        json=sql_payload,
        headers=headers,
        timeout=30
    )
    print(f"  Status: {r.status_code}")
    print(f"  CORS Origin: {r.headers.get('access-control-allow-origin')}")
    assert r.status_code == 200, f"SQL run failed: {r.status_code} {r.text}"
    assert r.headers.get("access-control-allow-origin") == WEB_ORIGIN, "Missing CORS header on SQL run"
    sql_res = r.json()
    print(f"  Columns: {sql_res.get('columns')}")
    print(f"  Rows:    {sql_res.get('rows')}")
    print(f"  Elapsed: {sql_res.get('elapsedMs')}ms")
    assert len(sql_res.get("rows", [])) == 1, "Expected 1 row result"
    assert sql_res["rows"][0]["total_reviews"] == 99224, "Expected 99224 reviews"
    print("  --> DuckDB SQL Execution: PASSED\n")

    print("=================================================================")
    print(">>> ALL PRODUCTION VERIFICATION TESTS COMPLETED SUCCESSFULLY! <<<")
    print("=================================================================")

if __name__ == "__main__":
    verify_all()
