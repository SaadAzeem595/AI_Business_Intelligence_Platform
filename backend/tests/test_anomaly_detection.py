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
    assert res.min_observed is not None
    assert res.max_observed is not None
    assert res.mean_observed is not None
    assert res.std_observed is not None
    assert res.sensitivity_explanation is not None
    assert "Z-Score" in res.sensitivity_explanation
    assert len(res.timeline) == 60
    assert len(res.logs) > 0
    assert len(res.business_impact) > 0
    assert len(res.recommended_actions) > 0

    # Verify outlier row index 15 (450.0) is flagged
    flagged_timestamps = [log.timestamp for log in res.logs]
    expected_ts = anomaly_test_df.iloc[15]["order_date"].strftime("%Y-%m-%d")
    assert expected_ts in flagged_timestamps

    # Verify dataset-grounded explanation contains dataset_name and metric_column
    top_log = res.logs[0]
    assert "revenue" in top_log.explanation
    assert "Test Dataset" in top_log.explanation
    assert top_log.threshold_formatted is not None
    assert top_log.expected_value_formatted is not None
    assert top_log.deviation_pct is not None


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
    assert res.sensitivity_explanation is not None
    assert "IQR" in res.sensitivity_explanation


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
    assert res.sensitivity_explanation is not None
    assert "Isolation Forest" in res.sensitivity_explanation


def test_zero_anomalies_reporting():
    """Generates a perfectly uniform dataset without anomalies and checks zero-anomaly response."""
    service = AnomalyDetectionService()
    dates = pd.date_range(start="2026-01-01", periods=30, freq="D")
    # Values very close to 100 with negligible variation
    df = pd.DataFrame({
        "date": dates,
        "revenue": [100.0 + (i % 3) * 0.5 for i in range(30)]
    })

    res = service.run_dataset_anomaly_detection(
        df=df,
        timestamp_column="date",
        metric_column="revenue",
        detection_method="zscore",
        sensitivity=0.01,
        dataset_name="Uniform Dataset"
    )

    assert res.status == "success"
    assert res.total_observations == 30
    assert res.anomalies_detected == 0
    assert res.anomaly_rate == 0.0
    assert res.min_observed == 100.0
    assert res.max_observed == 101.0
    assert res.lower_threshold is not None
    assert res.upper_threshold is not None
    assert res.min_observed >= res.lower_threshold
    assert res.max_observed <= res.upper_threshold
    assert any("Zero anomalies detected" in ins for ins in res.business_impact)
    assert any("statistically stable" in rec for rec in res.recommended_actions)


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

