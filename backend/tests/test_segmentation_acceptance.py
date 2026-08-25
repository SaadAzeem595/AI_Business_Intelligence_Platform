import pytest
import os
import pandas as pd
import numpy as np
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.features.datasets.router import UPLOADED_PATHS_CACHE
from app.features.analytics.engine.segmentation import SegmentationService
from app.features.analytics.router import resolve_dataset_path_async


@pytest.mark.anyio
async def test_project_dataset_segmentation_isolation(tmp_path):
    """
    Acceptance test: Verify selecting Project A -> Dataset A returns results based on Dataset A,
    and switching to Project B -> Dataset B returns results based on Dataset B without fallback.
    """
    # Create Dataset A for Project A
    df_a = pd.DataFrame({
        "customer_id": [f"CUST-A{i}" for i in range(50)],
        "annual_spend": np.random.uniform(1000, 5000, 50),
        "loyalty_score": np.random.uniform(50, 100, 50)
    })
    path_a = str(tmp_path / "dataset_a.csv")
    df_a.to_csv(path_a, index=False)

    # Create Dataset B for Project B
    df_b = pd.DataFrame({
        "user_id": [f"USER-B{i}" for i in range(60)],
        "product_weight_g": np.random.uniform(10, 500, 60),
        "shipping_cost": np.random.uniform(2, 50, 60),
        "return_rate": np.random.uniform(0.01, 0.2, 60)
    })
    path_b = str(tmp_path / "dataset_b.csv")
    df_b.to_csv(path_b, index=False)

    # Register in UPLOADED_PATHS_CACHE with explicit project scoping
    UPLOADED_PATHS_CACHE["ds_a_id"] = {
        "path": path_a,
        "filename": "dataset_a.csv",
        "project_id": "proj_a"
    }
    UPLOADED_PATHS_CACHE["ds_b_id"] = {
        "path": path_b,
        "filename": "dataset_b.csv",
        "project_id": "proj_b"
    }

    # 1. Resolve Dataset A for Project A
    resolved_a = await resolve_dataset_path_async(dataset_id="ds_a_id", project_id="proj_a")
    assert resolved_a == path_a

    # Run Segmentation on Project A -> Dataset A
    service = SegmentationService()
    df_loaded_a = pd.read_csv(resolved_a)
    res_a = service.cluster_data(df_loaded_a, mode="numerical", n_clusters=3)
    
    assert res_a["entity_key"] == "customer_id"
    assert set(res_a["features_used"]) == {"annual_spend", "loyalty_score"}
    assert len(res_a["assignments"]) == 50

    # 2. Resolve Dataset B for Project B
    resolved_b = await resolve_dataset_path_async(dataset_id="ds_b_id", project_id="proj_b")
    assert resolved_b == path_b

    # Run Segmentation on Project B -> Dataset B
    df_loaded_b = pd.read_csv(resolved_b)
    res_b = service.cluster_data(df_loaded_b, mode="numerical", n_clusters=3)

    assert res_b["entity_key"] == "user_id"
    assert set(res_b["features_used"]) == {"product_weight_g", "shipping_cost", "return_rate"}
    assert len(res_b["assignments"]) == 60

    # 3. Verify cross-project dataset access restriction
    with pytest.raises(HTTPException):
        await resolve_dataset_path_async(dataset_id="ds_a_id", project_id="proj_b")

