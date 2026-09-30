import requests
import json
from test_prod_forecast import headers, BASE_URL, PROJECT_ID

r = requests.get(f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/datasets", headers=headers)
print("Project datasets status:", r.status_code)
if r.status_code == 200:
    datasets = r.json()
    print(f"Total datasets in project {PROJECT_ID}: {len(datasets)}")
    for d in datasets:
        print(f"  ID: {d.get('id')} | Name: {d.get('name') or d.get('filename')} | Table: {d.get('duckdb_table')} | Storage: {d.get('storage_path')}")
else:
    print("Failed:", r.text)

r2 = requests.get(f"{BASE_URL}/api/v1/datasets", headers=headers)
print("\nAll datasets status:", r2.status_code)
if r2.status_code == 200:
    all_ds = r2.json()
    print(f"Total global datasets: {len(all_ds)}")
    for d in all_ds[:5]:
        print(f"  ID: {d.get('id')} | Name: {d.get('name') or d.get('filename')} | Proj: {d.get('project_id')}")
