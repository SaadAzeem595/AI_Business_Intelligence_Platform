import pytest
import pandas as pd
import numpy as np
from app.features.analytics.engine.anomaly import AnomalyDetectionService

@pytest.fixture
def anomaly_test_df():
    """Generates a dataset with clear timestamp, metric, and known outliers."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=60, freq="D")
    
    # Baseline metric centered around 100 with std dev ~10
    values = np.random.normal(100, 10, 60)
    
    # Inject 2 extreme outlier spikes
    values[15] = 450.0  # High Spike
    values[42] = 5.0    # Low Dip
    
    df = pd.DataFrame({
        "order_date": dates,
        "revenue": values,
        "customer_count": np.random.randint(5, 50, 60)
    })
    return df


def test_run_dataset_anomaly_detection_zscore(anomaly_test_df):
    service = AnomalyDetectionService()
    res = service.run_dataset_anomaly_detection(
        df=anomaly_test_df,
        timestamp_column="order_date",
        metric_column="revenue",
        detection_method="zscore",
        sensitivity=0.05,
        dataset_name="Test Dataset",
        project_id="proj-123"
    )

    assert res.status == "success"
    assert res.total_observations == 60
    assert res.anomalies_detected >= 1
    assert res.highest_severity in ["High", "Medium"]
    assert len(res.timeline) == 60
    assert len(res.logs) > 0
    assert len(res.business_impact) > 0
    assert len(res.recommended_actions) > 0

    # Verify outlier row index 15 (450.0) is flagged
    flagged_timestamps = [log.timestamp for log in res.logs]
    expected_ts = anomaly_test_df.iloc[15]["order_date"].strftime("%Y-%m-%d")
    assert expected_ts in flagged_timestamps


def test_run_dataset_anomaly_detection_iqr(anomaly_test_df):
    service = AnomalyDetectionService()
    res = service.run_dataset_anomaly_detection(
        df=anomaly_test_df,
        timestamp_column="order_date",
        metric_column="revenue",
        detection_method="iqr",
        sensitivity=0.05,
        dataset_name="Test Dataset"
    )

    assert res.status == "success"
    assert res.anomalies_detected >= 1
    assert res.upper_threshold is not None
    assert res.lower_threshold is not None


def test_run_dataset_anomaly_detection_iforest(anomaly_test_df):
    service = AnomalyDetectionService()
    res = service.run_dataset_anomaly_detection(
        df=anomaly_test_df,
        timestamp_column="order_date",
        metric_column="revenue",
        detection_method="iforest",
        sensitivity=0.05,
        dataset_name="Test Dataset"
    )

    assert res.status == "success"
    assert res.total_observations == 60
    assert res.anomalies_detected >= 1


def test_invalid_columns_raise_error(anomaly_test_df):
    service = AnomalyDetectionService()
    
    with pytest.raises(ValueError, match="Timestamp column 'missing_date' not found"):
        service.run_dataset_anomaly_detection(
            df=anomaly_test_df,
            timestamp_column="missing_date",
            metric_column="revenue"
        )

    with pytest.raises(ValueError, match="Metric column 'missing_metric' not found"):
        service.run_dataset_anomaly_detection(
            df=anomaly_test_df,
            timestamp_column="order_date",
            metric_column="missing_metric"
        )
