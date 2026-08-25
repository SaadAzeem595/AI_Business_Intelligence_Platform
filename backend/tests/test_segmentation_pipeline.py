import pytest
import pandas as pd
import numpy as np
from app.features.analytics.engine.segmentation import SegmentationService


@pytest.fixture
def sample_transactional_df():
    """Generates sample transactional e-commerce dataset for RFM segmentation testing."""
    np.random.seed(42)
    n_rows = 150
    customers = [f"CUST-{i:03d}" for i in range(1, 21)]
    dates = pd.date_range("2026-01-01", periods=150, freq="D")

    rand_indices = np.random.randint(0, len(dates), n_rows)
    data = {
        "customer_id": [np.random.choice(customers) for _ in range(n_rows)],
        "order_id": [f"ORD-{1000 + i}" for i in range(n_rows)],
        "order_purchase_timestamp": [dates[i].strftime("%Y-%m-%d %H:%M:%S") for i in rand_indices],
        "price": np.random.uniform(20.0, 500.0, n_rows).round(2),
        "freight_value": np.random.uniform(5.0, 30.0, n_rows).round(2),
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_generic_numerical_df():
    """Generates generic numerical tabular dataset for non-RFM clustering testing."""
    np.random.seed(42)
    n_rows = 80

    # 3 natural clusters in 2D space
    c1 = np.random.normal(loc=[10, 80], scale=2, size=(30, 2))
    c2 = np.random.normal(loc=[50, 20], scale=3, size=(30, 2))
    c3 = np.random.normal(loc=[90, 90], scale=2, size=(20, 2))

    data_matrix = np.vstack([c1, c2, c3])
    df = pd.DataFrame(data_matrix, columns=["feature_x", "feature_y"])
    df["product_id"] = [f"PROD-{i:03d}" for i in range(n_rows)]
    df["sales_volume"] = np.random.randint(10, 500, n_rows)
    return df


# Test 1: Automatic Entity Key & Transactional Attribute Detection
def test_detect_entity_key_and_transactional(sample_transactional_df):
    service = SegmentationService()

    entity_key = service.detect_entity_key(sample_transactional_df)
    assert entity_key == "customer_id"

    trans_cols = service.detect_transactional_columns(sample_transactional_df)
    assert trans_cols["date_col"] == "order_purchase_timestamp"
    assert trans_cols["monetary_col"] in ["price", "freight_value"]


# Test 2: RFM Feature Engineering & Clustering Execution
def test_rfm_segmentation_pipeline(sample_transactional_df):
    service = SegmentationService()

    res = service.cluster_data(sample_transactional_df, mode="rfm", n_clusters=3)

    assert "assignments" in res
    assert "summaries" in res
    assert "scatter" in res
    assert "cohorts" in res
    assert "evaluation" in res
    assert "profiles" in res

    assert res["dataset_type"].startswith("Transactional RFM")
    assert res["entity_key"] == "customer_id"
    assert len(res["scatter"]) > 0
    assert len(res["cohorts"]) == 3

    # Check evaluation metrics structure
    eval_m = res["evaluation"]
    assert "optimal_k" in eval_m
    assert "silhouette_score" in eval_m
    assert "davies_bouldin_index" in eval_m
    assert "calinski_harabasz_index" in eval_m


# Test 3: Generic Numerical Feature Segmentation
def test_generic_numerical_segmentation(sample_generic_numerical_df):
    service = SegmentationService()

    res = service.cluster_data(
        sample_generic_numerical_df,
        mode="numerical",
        n_clusters=3,
        features=["feature_x", "feature_y"]
    )

    assert res["dataset_type"] == "Generic Numerical Feature Clustering"
    assert res["features_used"] == ["feature_x", "feature_y"]
    assert len(res["cohorts"]) == 3
    assert len(res["profiles"]) == 3

    # Check 2D scatter coordinates
    for pt in res["scatter"]:
        assert "x" in pt
        assert "y" in pt
        assert "cluster" in pt


# Test 4: Optimal K Selection Metric Evaluation
def test_evaluate_optimal_k(sample_generic_numerical_df):
    service = SegmentationService()

    cleaned_df = sample_generic_numerical_df[["feature_x", "feature_y"]]
    from sklearn.preprocessing import StandardScaler
    scaled = StandardScaler().fit_transform(cleaned_df)

    optimal_k, eval_dict = service.evaluate_optimal_k(scaled, max_k=6)

    assert 2 <= optimal_k <= 6
    assert "metrics_by_k" in eval_dict
    assert len(eval_dict["metrics_by_k"]) >= 2
    # Verify silhouette score is bounded [-1, 1]
    for k, m in eval_dict["metrics_by_k"].items():
        assert -1.0 <= m["silhouette_score"] <= 1.0


# Test 5: Dynamic Business Profile Naming & Recommendations
def test_business_profile_generation(sample_transactional_df):
    service = SegmentationService()
    res = service.cluster_data(sample_transactional_df, mode="rfm", n_clusters=3)

    profiles = res["profiles"]
    assert len(profiles) == 3

    for prof in profiles:
        assert "name" in prof
        assert "characteristics" in prof
        assert "recommendation" in prof
        assert prof["risk_rating"] in ["Low", "Medium", "High"]
        assert len(prof["recommendation"]) > 10


# Test 6: Error Handling for Invalid / Edge Case Inputs
def test_segmentation_error_handling():
    service = SegmentationService()

    # Empty dataframe
    empty_df = pd.DataFrame()
    with pytest.raises(ValueError, match="dataset is empty"):
        service.cluster_data(empty_df)

    # Single row dataframe
    single_df = pd.DataFrame({"x": [1.0], "y": [2.0]})
    with pytest.raises(ValueError, match="Insufficient rows"):
        service.cluster_data(single_df, n_clusters=3)

    # DataFrame with no numeric columns
    str_df = pd.DataFrame({"col_a": ["A", "B", "C"], "col_b": ["X", "Y", "Z"]})
    with pytest.raises(ValueError, match="No clusterable numerical features"):
        service.cluster_data(str_df, mode="numerical")
