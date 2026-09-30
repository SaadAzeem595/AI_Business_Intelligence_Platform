import requests
import json

BASE_URL = "https://datapilot-api.ashyriver-d1eb08b9.uaenorth.azurecontainerapps.io"

def test_prod_forecasting():
    print("Testing GET /api/v1/forecasting/health...")
    h_res = requests.get(f"{BASE_URL}/api/v1/forecasting/health")
    print(f"Health response [{h_res.status_code}]: {h_res.text}")

    # Login to obtain token
    login_res = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": "saadazeem626@gmail.com", "password": "Password123!"}
    )
    headers = {}
    if login_res.status_code == 200:
        token = login_res.json()["accessToken"]
        headers["Authorization"] = f"Bearer {token}"
        print("Logged in successfully, token acquired.")
    else:
        print(f"Login failed [{login_res.status_code}]: {login_res.text}")

    # List projects to get Olist project
    p_res = requests.get(f"{BASE_URL}/api/v1/projects", headers=headers)
    print(f"Projects response [{p_res.status_code}]: found {len(p_res.json()) if p_res.status_code == 200 else 'none'}")
    
    olist_proj = None
    if p_res.status_code == 200:
        for p in p_res.json():
            if "olist" in p.get("name", "").lower():
                olist_proj = p
                break
        if not olist_proj and len(p_res.json()) > 0:
            olist_proj = p_res.json()[0]

    if not olist_proj:
        print("No project found!")
        return

    proj_id = olist_proj["id"]
    print(f"Selected project: {olist_proj.get('name')} ({proj_id})")

    # Get Schema info
    s_res = requests.get(f"{BASE_URL}/api/v1/projects/{proj_id}/forecast/schema-info", headers=headers)
    print(f"Schema info [{s_res.status_code}]:")
    print(json.dumps(s_res.json(), indent=2))

    # Forecast request
    payload = {
        "dataset_id": "olist_relational_derived",
        "date_column": "order_purchase_timestamp",
        "target_column": "total_order_value",
        "aggregation": "monthly",
        "horizon": 6,
        "model": "auto",
        "confidence": 0.95
    }
    print(f"\nSending forecast request: {json.dumps(payload)}")
    f_res = requests.post(f"{BASE_URL}/api/v1/projects/{proj_id}/forecast", json=payload, headers=headers, timeout=60)
    print(f"Forecast response [{f_res.status_code}]:")
    data = f_res.json()
    print(f"Status: {data.get('status')}")
    print(f"Message: {data.get('message')}")
    print(f"Model used: {data.get('model_used')}")
    print(f"Historical points: {data.get('historical_points')}")
    print(f"Forecast points: {data.get('forecast_points')}")
    print(f"Date detection: {json.dumps(data.get('date_detection'), indent=2)}")
    
    timeline = data.get("timeline", [])
    print(f"Total timeline length: {len(timeline)}")
    actuals = [t for t in timeline if t.get("actual") is not None]
    forecasts = [t for t in timeline if t.get("forecast") is not None]
    print(f"Actual points count: {len(actuals)}")
    print(f"Forecast points count: {len(forecasts)}")
    if actuals:
        print(f"Actuals range: {actuals[0]['date']} ({actuals[0]['actual']}) -> {actuals[-1]['date']} ({actuals[-1]['actual']})")
    if forecasts:
        print(f"Forecast range: {forecasts[0]['date']} ({forecasts[0]['forecast']}) -> {forecasts[-1]['date']} ({forecasts[-1]['forecast']})")

if __name__ == "__main__":
    test_prod_forecasting()
