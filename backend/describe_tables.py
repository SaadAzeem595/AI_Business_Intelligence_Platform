import requests
import json
from test_prod_forecast import headers, BASE_URL, PROJECT_ID

tables = [
    "project_proj_75cc2d62_olist_orders_dataset",
    "project_proj_75cc2d62_olist_order_items_dataset",
    "project_proj_75cc2d62_olist_customers_dataset",
    "project_proj_75cc2d62_olist_order_payments_dataset",
    "project_proj_75cc2d62_olist_order_reviews_dataset"
]
for t in tables:
    r = requests.post(f"{BASE_URL}/api/v1/sql/run", json={"query": f"DESCRIBE SELECT * FROM {t}", "project_id": PROJECT_ID}, headers=headers)
    cols = [row["column_name"] for row in r.json().get("rows", [])] if r.status_code == 200 else []
    print(t, "->", cols)
