import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.datasets.router import UPLOADED_PATHS_CACHE
from app.features.datasets.models import Dataset
from app.features.projects.models import Project
from app.features.analytics.engine.segmentation import SegmentationService
from app.features.analytics.engine.discovery import DatasetDiscoveryService, resolve_actual_file
from app.features.analytics.router import resolve_dataset_path_async, get_project_segment_schema_info
from app.features.analytics.schemas import SegmentPayload


@pytest.fixture(autouse=True)
def clean_cache():
    UPLOADED_PATHS_CACHE.clear()
    yield
    UPLOADED_PATHS_CACHE.clear()


@pytest.mark.anyio
async def test_project_with_one_csv_dataset(tmp_path):
    """Test 1: Project with one CSV dataset."""
    csv_file = tmp_path / "single_dataset.csv"
    df = pd.DataFrame({
        "customer_id": [f"CUST_{i}" for i in range(100)],
        "recency_days": np.random.uniform(5, 300, 100),
        "total_spend": np.random.uniform(50, 2000, 100),
        "order_count": np.random.randint(1, 10, 100)
    })
    df.to_csv(csv_file, index=False)

    UPLOADED_PATHS_CACHE["ds_single"] = {
        "path": str(csv_file),
        "filename": "single_dataset.csv",
        "project_id": "proj_1"
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_1", mock_db)
    assert res.dataset_count >= 1
    assert res.eligible_count >= 1
    assert res.candidates[0].eligible is True
    assert res.candidates[0].entity_key == "customer_id"
    assert "total_spend" in res.candidates[0].usable_features


@pytest.mark.anyio
async def test_project_with_multiple_csv_datasets(tmp_path):
    """Test 2: Project with multiple CSV datasets."""
    f1 = tmp_path / "orders.csv"
    pd.DataFrame({"order_id": list(range(10)), "amount": [10.0 + i for i in range(10)], "qty": [1 + (i % 3) for i in range(10)]}).to_csv(f1, index=False)
    f2 = tmp_path / "users.csv"
    pd.DataFrame({"user_id": list(range(100, 110)), "age": [20 + i for i in range(10)], "income": [50000 + i * 1000 for i in range(10)]}).to_csv(f2, index=False)

    UPLOADED_PATHS_CACHE["ds_1"] = {"path": str(f1), "filename": "orders.csv", "project_id": "proj_multi"}
    UPLOADED_PATHS_CACHE["ds_2"] = {"path": str(f2), "filename": "users.csv", "project_id": "proj_multi"}

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_multi", mock_db)
    assert res.dataset_count == 2
    assert res.eligible_count == 2


@pytest.mark.anyio
async def test_project_with_excel_dataset(tmp_path):
    """Test 3: Project with Excel dataset."""
    xlsx_file = tmp_path / "financials.xlsx"
    xlsx_file.write_text("dummy excel content")

    UPLOADED_PATHS_CACHE["ds_excel"] = {
        "path": str(xlsx_file),
        "filename": "financials.xlsx",
        "project_id": "proj_excel"
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    fake_excel_df = pd.DataFrame({
        "account_id": [f"ACC_{i}" for i in range(50)],
        "revenue": np.random.uniform(1000, 5000, 50),
        "cost": np.random.uniform(500, 2500, 50)
    })

    from unittest.mock import patch
    with patch("app.features.analytics.engine.utils.load_dataset", return_value=fake_excel_df):
        res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_excel", mock_db)
        assert res.dataset_count >= 1
        assert res.candidates[0].eligible is True
        assert res.candidates[0].entity_key == "account_id"


@pytest.mark.anyio
async def test_project_with_relational_olist_datasets(tmp_path):
    """Test 4: Project with relational Olist datasets synthesizes customer RFM candidate."""
    UPLOADED_PATHS_CACHE["ds_orders"] = {
        "filename": "olist_orders_dataset.csv",
        "duckdb_table": "project_proj_olist_olist_orders_dataset",
        "project_id": "proj_olist"
    }
    UPLOADED_PATHS_CACHE["ds_items"] = {
        "filename": "olist_order_items_dataset.csv",
        "duckdb_table": "project_proj_olist_olist_order_items_dataset",
        "project_id": "proj_olist"
    }
    UPLOADED_PATHS_CACHE["ds_cust"] = {
        "filename": "olist_customers_dataset.csv",
        "duckdb_table": "project_proj_olist_olist_customers_dataset",
        "project_id": "proj_olist"
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_olist", mock_db)
    # Relational derived candidate should be generated and ranked first
    assert any(c.dataset_id == "olist_customer_segmentation_derived" for c in res.candidates)
    top_cand = res.candidates[0]
    assert top_cand.dataset_id == "olist_customer_segmentation_derived"
    assert top_cand.eligible is True
    assert top_cand.is_rfm_capable is True
    assert "total_spend" in top_cand.usable_features
    assert "recency_days" in top_cand.usable_features
    assert "order_count" in top_cand.usable_features


@pytest.mark.anyio
async def test_project_with_zero_datasets():
    """Test 5: Project with zero datasets returns diagnostic empty message."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_empty", mock_db)
    assert res.dataset_count == 0
    assert res.eligible_count == 0
    assert "No datasets are currently attached to this project" in (res.message or "")


@pytest.mark.anyio
async def test_dataset_with_no_numeric_features(tmp_path):
    """Test 7: Dataset with no numeric or categorical analytical features is marked ineligible."""
    text_file = tmp_path / "notes.csv"
    pd.DataFrame({"note_id": [f"N_{i}" for i in range(20)], "full_text": [f"Sample note text long description {i}" for i in range(20)]}).to_csv(text_file, index=False)

    UPLOADED_PATHS_CACHE["ds_text"] = {
        "path": str(text_file),
        "filename": "notes.csv",
        "project_id": "proj_text"
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_text", mock_db)
    assert res.candidates[0].eligible is False
    assert "No usable numeric or categorical" in res.candidates[0].reason


@pytest.mark.anyio
async def test_dataset_with_only_identifiers(tmp_path):
    """Test 8: Dataset with only identifiers excludes them from clustering."""
    ids_file = tmp_path / "identifiers.csv"
    pd.DataFrame({
        "customer_id": [f"C_{i}" for i in range(30)],
        "order_id": [f"O_{i}" for i in range(30)],
        "zip_code": [f"9021{i}" for i in range(30)]
    }).to_csv(ids_file, index=False)

    UPLOADED_PATHS_CACHE["ds_ids"] = {
        "path": str(ids_file),
        "filename": "identifiers.csv",
        "project_id": "proj_ids"
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_ids", mock_db)
    assert res.candidates[0].eligible is False
    assert "customer_id" in res.candidates[0].excluded_features


@pytest.mark.anyio
async def test_dataset_with_missing_values(tmp_path):
    """Test 9: Dataset with missing values handles imputation cleanly."""
    f = tmp_path / "missing.csv"
    pd.DataFrame({
        "customer_id": [f"C_{i}" for i in range(20)],
        "feature_1": [1.0 if i % 2 == 0 else np.nan for i in range(20)],
        "feature_2": [10.0 if i % 3 == 0 else np.nan for i in range(20)]
    }).to_csv(f, index=False)

    service = SegmentationService()
    df = pd.read_csv(f)
    result = service.cluster_data(df, mode="numerical", n_clusters=2)
    assert len(result["cohorts"]) >= 1
    assert result["evaluation"] is not None


@pytest.mark.anyio
async def test_dataset_with_mixed_features(tmp_path):
    """Test 10: Dataset with mixed numeric and categorical features."""
    f = tmp_path / "mixed.csv"
    pd.DataFrame({
        "user_id": [f"U_{i}" for i in range(40)],
        "tier": ["Gold" if i % 2 == 0 else "Silver" for i in range(40)],
        "spend": np.random.uniform(100, 1000, 40),
        "score": np.random.uniform(1, 10, 40)
    }).to_csv(f, index=False)

    UPLOADED_PATHS_CACHE["ds_mixed"] = {
        "path": str(f),
        "filename": "mixed.csv",
        "project_id": "proj_mixed"
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    res = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_mixed", mock_db)
    cand = res.candidates[0]
    assert cand.eligible is True
    assert "tier" in cand.categorical_features
    assert "spend" in cand.numerical_features


@pytest.mark.anyio
async def test_project_isolation(tmp_path):
    """Test 11 & 12: Project isolation prevents cross-project dataset access."""
    f_a = tmp_path / "dataset_a.csv"
    pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]}).to_csv(f_a, index=False)
    UPLOADED_PATHS_CACHE["ds_a"] = {"path": str(f_a), "filename": "dataset_a.csv", "project_id": "proj_a"}

    # Resolving ds_a within proj_a succeeds
    resolved = await resolve_dataset_path_async(dataset_id="ds_a", project_id="proj_a")
    assert resolved == str(f_a)

    # Resolving ds_a within proj_b fails with 400 Bad Request
    with pytest.raises(HTTPException):
        await resolve_dataset_path_async(dataset_id="ds_a", project_id="proj_b")


@pytest.mark.anyio
async def test_dataset_upload_after_page_open(tmp_path):
    """Test 15: Uploading a new dataset immediately makes it discoverable."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    # Initially empty
    res1 = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_dyn", mock_db)
    assert res1.dataset_count == 0

    # User uploads file while page was open
    new_file = tmp_path / "new_upload.csv"
    pd.DataFrame({"cust_id": [1, 2, 3, 4, 5], "x": [10, 20, 30, 40, 50], "y": [5, 4, 3, 2, 1]}).to_csv(new_file, index=False)
    UPLOADED_PATHS_CACHE["ds_new"] = {"path": str(new_file), "filename": "new_upload.csv", "project_id": "proj_dyn"}

    # Next call reflects uploaded dataset immediately
    res2 = await DatasetDiscoveryService.discover_project_segmentation_candidates("proj_dyn", mock_db)
    assert res2.dataset_count == 1
    assert res2.candidates[0].filename == "new_upload.csv"
