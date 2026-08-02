import pytest
import pandas as pd
import numpy as np
import os
from typing import Dict, Any

from app.features.analytics.engine.profiler import DataProfilerService
from app.features.analytics.engine.quality import DataQualityService
from app.features.analytics.engine.kpi import KpiEngineService
from app.features.analytics.engine.statistics import StatisticalAnalysisService
from app.features.analytics.engine.feature_engineering import FeatureEngineeringService
from app.features.analytics.engine.visualization import VisualizationService
from app.features.analytics.engine.forecasting import ForecastingService, BaseForecaster
from app.features.analytics.engine.segmentation import SegmentationService
from app.features.analytics.engine.anomaly import AnomalyDetectionService
from app.features.analytics.engine.explainability import ExplainabilityService


@pytest.fixture
def sample_business_df():
    """Generates a realistic business DataFrame for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=50, freq='D')
    
    df = pd.DataFrame({
        "date": dates,
        "customer_id": [f"C-{i % 5}" for i in range(50)],
        "revenue": np.random.uniform(100, 500, 50).tolist(),
        "cost": np.random.uniform(50, 300, 50).tolist(),
        "marketing_spend": np.random.uniform(10, 50, 50).tolist(),
        "conversions": np.random.randint(1, 5, 50).tolist(),
        "visitors": np.random.randint(10, 50, 50).tolist(),
        "x": np.random.normal(10, 2, 50).tolist(),
        "y": np.random.normal(20, 5, 50).tolist(),
        "region": ["North", "South", "East", "West", "North"] * 10
    })
    df["profit"] = df["revenue"] - df["cost"]
    # Introduce some anomalies/outliers
    df.loc[10, "revenue"] = 5000.0
    df.loc[10, "profit"] = 4800.0
    # Introduce duplicate row
    df = pd.concat([df, df.iloc[[2]]], ignore_index=True)
    # Introduce nulls
    df.loc[5, "marketing_spend"] = None
    return df


@pytest.fixture
def temp_csv_file(sample_business_df, tmp_path):
    """Saves sample df to a temporary CSV file and returns path."""
    file_path = tmp_path / "test_data.csv"
    sample_business_df.to_csv(file_path, index=False)
    return str(file_path)


def test_data_profiler(temp_csv_file):
    service = DataProfilerService()
    profile = service.profile_dataset(temp_csv_file)
    
    assert profile["total_rows"] == 51
    assert profile["total_columns"] == 11
    assert profile["duplicate_rows"] == 1
    assert "revenue" in profile["columns"]
    assert profile["columns"]["revenue"]["type"] in ["float", "numeric"]
    assert profile["columns"]["revenue"]["outliers_count"] >= 1
    assert "distribution" in profile["columns"]["revenue"]
    assert "skewness" in profile["columns"]["revenue"]
    assert "region" in profile["columns"]
    assert profile["columns"]["region"]["type"] == "categorical"
    assert "value_distribution" in profile["columns"]["region"]


def test_data_quality(temp_csv_file):
    service = DataQualityService()
    quality = service.assess_quality(temp_csv_file)
    
    assert "quality_score" in quality
    assert quality["quality_score"] < 100 # Deductions for missing, dups, outlier
    assert quality["duplicate_rows"] == 1
    assert quality["missing_values"] == 1
    assert "marketing_spend" in quality["inconsistencies"] or len(quality["recommendations"]) > 0


def test_kpi_engine(temp_csv_file):
    service = KpiEngineService()
    kpi_results = service.compute_kpis(
        temp_csv_file,
        custom_kpis={
            "ProfitMargin": "(profit / revenue) * 100",
            "TotalConversions": "sum(conversions)",
            "AvgVisitors": "mean(visitors)"
        }
    )
    
    std = kpi_results["standard_kpis"]
    custom = kpi_results["custom_kpis"]
    
    assert std["revenue"] is not None
    assert std["profit"] is not None
    assert std["cac"] is not None
    assert std["conversion_rate"] is not None
    
    assert "ProfitMargin" in custom
    assert "TotalConversions" in custom
    assert "AvgVisitors" in custom
    assert isinstance(custom["TotalConversions"], float)


def test_statistical_analysis(sample_business_df):
    service = StatisticalAnalysisService()
    
    # 1. Descriptive
    desc = service.run_descriptive(sample_business_df)
    assert "revenue" in desc
    assert desc["revenue"]["count"] == 51
    assert desc["revenue"]["mean"] > 0
    
    # 2. Correlation & Covariance
    corr = service.run_correlation(sample_business_df)
    cov = service.run_covariance(sample_business_df)
    assert "pearson" in corr
    assert "spearman" in corr
    assert "revenue" in corr["pearson"]
    assert "revenue" in cov
    
    # 3. Hypothesis testing
    # Independent t-test
    t_res = service.run_hypothesis_test(
        sample_business_df, 
        "ttest_ind", 
        {"col_a": "x", "col_b": "y"}
    )
    assert "p_value" in t_res
    assert t_res["test"] == "Independent T-Test"
    
    # Normality test
    n_res = service.run_hypothesis_test(
        sample_business_df, 
        "normality", 
        {"col": "x"}
    )
    assert "p_value" in n_res
    
    # 4. Trend analysis
    trend = service.run_trend_analysis(sample_business_df, "date", "revenue")
    assert "slope" in trend
    assert "direction" in trend


def test_feature_engineering(sample_business_df):
    service = FeatureEngineeringService()
    res = service.engineer_features(
        sample_business_df,
        target_col="region",
        scaling_method="standard"
    )
    
    assert "train_x" in res
    assert "test_x" in res
    assert "train_y" in res
    assert "test_y" in res
    assert "metadata" in res
    
    metadata = res["metadata"]
    assert metadata["detected_target"] == "region"
    assert "date_year" in res["train_x"][0] or "date_month" in res["train_x"][0]
    assert "North" in metadata["target_encoding"]
    assert "revenue" in metadata["scaling"]



def test_visualization_service(sample_business_df):
    service = VisualizationService()
    
    # Line Spec
    line_spec = service.get_chart_specification(sample_business_df, "line", "date", "revenue")
    assert line_spec["chart_type"] == "line"
    assert "series" in line_spec
    
    # Bar Spec
    bar_spec = service.get_chart_specification(sample_business_df, "bar", "region", "revenue")
    assert bar_spec["chart_type"] == "bar"
    
    # Scatter Spec
    scatter_spec = service.get_chart_specification(sample_business_df, "scatter", "x", "y")
    assert scatter_spec["chart_type"] == "scatter"
    
    # Heatmap Spec
    heatmap_spec = service.get_chart_specification(sample_business_df, "heatmap", "x")
    assert heatmap_spec["chart_type"] == "heatmap"
    
    # Pie Spec
    pie_spec = service.get_chart_specification(sample_business_df, "pie", "region")
    assert pie_spec["chart_type"] == "pie"
    
    # Histogram Spec
    hist_spec = service.get_chart_specification(sample_business_df, "histogram", "revenue")
    assert hist_spec["chart_type"] == "bar" # uses bar spec for hist columns
    
    # Boxplot Spec
    box_spec = service.get_chart_specification(sample_business_df, "boxplot", "region", "revenue")
    assert box_spec["chart_type"] == "boxplot"


def test_forecasting_service(temp_csv_file):
    service = ForecastingService()
    
    # ARIMA forecast
    arima_res = service.forecast(temp_csv_file, "arima", "date", "revenue", periods=5)
    assert arima_res["model_used"] == "arima"
    assert len(arima_res["timeline"]) > 50
    assert arima_res["timeline"][-1]["forecast"] is not None
    
    # LightGBM forecast
    lgb_res = service.forecast(temp_csv_file, "lightgbm", "date", "revenue", periods=5)
    assert lgb_res["model_used"] == "lightgbm"
    
    # XGBoost forecast
    xgb_res = service.forecast(temp_csv_file, "xgboost", "date", "revenue", periods=5)
    assert xgb_res["model_used"] == "xgboost"
    
    # Custom Pluggable Model Registration
    class CustomForecaster(BaseForecaster):
        def fit_predict(self, df, date_col, value_col, periods, confidence):
            timeline = [{"date": "2026-10-10", "actual": None, "forecast": 99.9, "lower": 90.0, "upper": 110.0}]
            return timeline, {"r_squared": 0.99, "mae": 1.0, "rmse": 1.0}
            
    service.register_model("custom_dummy", CustomForecaster)
    cust_res = service.forecast(temp_csv_file, "custom_dummy", "date", "revenue", periods=1)
    assert cust_res["model_used"] == "custom_dummy"
    assert cust_res["timeline"][0]["forecast"] == 99.9


def test_segmentation_service(sample_business_df):
    service = SegmentationService()
    
    # KMeans Clustering
    km_res = service.cluster_data(sample_business_df, method="kmeans", n_clusters=3, features=["x", "y"])
    assert "assignments" in km_res
    assert "summaries" in km_res
    assert "0" in km_res["summaries"]
    assert "percentage" in km_res["summaries"]["0"]
    
    # DBSCAN
    db_res = service.cluster_data(sample_business_df, method="dbscan", eps=2.0, min_samples=3, features=["x", "y"])
    assert "assignments" in db_res
    
    # Hierarchical
    h_res = service.cluster_data(sample_business_df, method="hierarchical", n_clusters=3, features=["x", "y"])
    assert "assignments" in h_res


def test_anomaly_detection(sample_business_df):
    service = AnomalyDetectionService()
    
    # Isolation Forest
    if_res = service.find_anomalies(sample_business_df, method="iforest", contamination=0.1, features=["revenue", "profit"])
    assert "anomalies" in if_res
    assert if_res["total_anomalies_found"] > 0
    # verify row 10 (outlier) is detected
    detected_rows = [anom["row_index"] for anom in if_res["anomalies"]]
    assert 10 in detected_rows
    
    # Local Outlier Factor
    lof_res = service.find_anomalies(sample_business_df, method="lof", contamination=0.1, features=["revenue", "profit"])
    assert "anomalies" in lof_res


def test_explainability_service(temp_csv_file):
    exp_service = ExplainabilityService()
    
    # Test Quality Explanation
    q_service = DataQualityService()
    quality = q_service.assess_quality(temp_csv_file)
    q_explanation = exp_service.explain_result("quality", quality)
    
    assert "summary" in q_explanation
    assert "insights" in q_explanation
    assert len(q_explanation["insights"]) > 0
    assert q_explanation["key_metrics"]["quality_score"] == quality["quality_score"]
    
    # Test KPI Explanation
    k_service = KpiEngineService()
    kpi_res = k_service.compute_kpis(temp_csv_file)
    k_explanation = exp_service.explain_result("kpi", kpi_res)
    assert "summary" in k_explanation
    
    # Test Forecast Explanation
    f_service = ForecastingService()
    f_res = f_service.forecast(temp_csv_file, "arima", "date", "revenue", periods=5)
    f_explanation = exp_service.explain_result("forecast", f_res)
    assert "summary" in f_explanation
    assert "insights" in f_explanation
