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

def main():
    print(f"Connecting to live production API at {BASE_URL}...")
    
    # 1. Fetch Schema Info to discover segmentation candidates
    r = requests.get(f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/segment/schema-info", headers=headers, timeout=30)
    print(f"Schema info status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    schema_data = r.json()
    candidates = schema_data.get("candidates", [])
    print(f"Discovered {len(candidates)} candidates in project {PROJECT_ID}:")
    for c in candidates:
        print(f" - [{c.get('dataset_id')}] {c.get('dataset_name')} | Eligible: {c.get('eligible')} | Rows: {c.get('row_count')} | Feats: {len(c.get('usable_features', []))} | Mode: {c.get('recommended_mode')}")

    # Find the top recommended candidate (should be Olist customer derived RFM view)
    rec_cand = next((c for c in candidates if c.get("eligible")), None)
    assert rec_cand is not None, "No eligible candidate found!"
    print(f"\nTop Candidate: {rec_cand.get('dataset_name')} (ID: {rec_cand.get('dataset_id')})")
    print(f"Usable features: {rec_cand.get('usable_features')}")
    print(f"Entity key: {rec_cand.get('entity_key')}")

    # 2. Test segmentation clustering execution
    features_to_use = rec_cand.get("usable_features", [])[:4]
    features_str = ", ".join(features_to_use)
    segment_payload = {
        "dataset_id": rec_cand["dataset_id"],
        "project_id": PROJECT_ID,
        "features": features_str,
        "clusters": 3,
        "mode": rec_cand.get("recommended_mode", "rfm"),
        "entity_key": rec_cand.get("entity_key")
    }

    print(f"\n[TESTING LIVE SEGMENTATION] Payload: {segment_payload}")
    r_seg = requests.post(f"{BASE_URL}/api/v1/projects/{PROJECT_ID}/segment", json=segment_payload, headers=headers, timeout=60)
    print(f"Segmentation response status: {r_seg.status_code}")
    assert r_seg.status_code == 200, f"Segmentation call failed ({r_seg.status_code}): {r_seg.text}"
    seg_res = r_seg.json()

    print(f"\n=== SEGMENTATION SUCCESS ===")
    eval_info = seg_res.get("evaluation") or {}
    print(f"Optimal K: {eval_info.get('optimal_k')}")
    print(f"Silhouette Score: {eval_info.get('silhouette_score')}")
    print(f"Scatter points count: {len(seg_res.get('scatter', []))}")
    print(f"Features used: {seg_res.get('features_used')}")
    print(f"Cohorts returned: {len(seg_res.get('cohorts', []))}")
    for ch in seg_res.get("cohorts", []):
        print(f"  * Cohort: '{ch.get('name')}' | Count: {ch.get('count')} | AvgSpent: ${ch.get('avgSpent')} | FreqScore: {ch.get('freqScore')} | RiskRating: {ch.get('riskRating')}")
    print(f"\nProfiles ({len(seg_res.get('profiles', []))}):")
    for p in seg_res.get("profiles", []):
        print(f"  - Cluster {p.get('cluster')} ({p.get('label')}): Size={p.get('size')} ({p.get('percentage')}%), Action={p.get('action')}")

if __name__ == "__main__":
    main()
