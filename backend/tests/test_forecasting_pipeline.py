import pytest
import io
import os
import json
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user, MockUser
from app.features.analytics.engine.discovery import DatasetDiscoveryService
from app.features.analytics.engine.forecasting import ProductionForecastingEngine, validate_and_prepare_timeseries


def set_active_user(user_id: str, role: str = "Analyst"):
    mock_user = MockUser(
        id=user_id,
        email=f"{user_id}@datapilot.com",
        name=f"User {user_id.upper()}",
        role=role
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return mock_user


def test_time_series_validation_and_preparation():
    """Tests validation of invalid/insufficient observations and gap filling."""
    # 1. Test insufficient observations (<3)
    short_df = pd.DataFrame({
        "date": ["2026-01-01", "2026-02-01"],
        "revenue": [100.0, 150.0]
    })
    cleaned, err = validate_and_prepare_timeseries(short_df, "date", "revenue", aggregation="monthly")
    assert cleaned is None
    assert "only 2 observation(s) are available" in err

    # 2. Test valid dataframe with 5 observations
    valid_df = pd.DataFrame({
        "date": ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"],
        "revenue": [1000.0, 1200.0, 1150.0, 1400.0, 1600.0]
    })
    cleaned, err = validate_and_prepare_timeseries(valid_df, "date", "revenue", aggregation="monthly")
    assert err is None
    assert cleaned is not None
    assert len(cleaned) == 5


def test_production_forecasting_engine_execution():
    """Tests candidate model cross-evaluation, model selection, and business summary generation."""
    dates = pd.date_range(start="2025-01-01", periods=12, freq="MS")
    revenue = [1000, 1100, 1250, 1300, 1450, 1600, 1750, 1900, 2100, 2250, 2400, 2600]
    df = pd.DataFrame({"date_bucket": dates, "metric_value": revenue})

    res = ProductionForecastingEngine.execute_project_forecast(
        df=df,
        project_id="test_proj_1",
        dataset_id="ds_1",
        dataset_name="sales.csv",
        date_col="date_bucket",
        target_col="metric_value",
        aggregation="monthly",
        horizon=6,
        requested_model="auto",
        confidence=0.95
    )

    assert res.status == "success"
    assert res.selected_model is not None
    assert len(res.timeline) == 12 + 6  # 12 actuals + 6 forecast
    assert len(res.metrics) >= 2  # Naive + ARIMA (+ Prophet if installed)
    assert res.business_summary is not None
    assert res.business_summary.growth_percentage > 0
    assert "Upward" in res.business_summary.current_trend
    assert len(res.recommendations) >= 2


def test_olist_relational_discovery_and_query_building():
    """Tests Olist orders + items dataset discovery and DuckDB query construction."""
    sql, meta = DatasetDiscoveryService.build_time_series_query(
        project_id="proj_olist",
        dataset_id="olist_relational_derived",
        date_column="order_purchase_timestamp",
        target_column="price",
        aggregation="monthly"
    )

    assert "olist_orders_dataset" in sql
    assert "olist_order_items_dataset" in sql
    assert "order_purchase_timestamp" in sql
    assert "SUM(items.price + COALESCE(items.freight_value, 0))" in sql
    assert meta["dataset_name"] == "Olist E-Commerce (Derived Join)"


def test_forecast_api_endpoints():
    """Tests GET schema-info and POST forecast endpoints for a project."""
    client = TestClient(app)
    set_active_user("user_forecast_test")

    # 1. Create a project
    create_res = client.post("/api/v1/projects", json={"name": "Forecast API Project"})
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    # 2. Upload CSV dataset to project
    csv_content = b"order_date,amount\n2026-01-01,500\n2026-02-01,600\n2026-03-01,750\n2026-04-01,900\n2026-05-01,1100"
    csv_file = io.BytesIO(csv_content)
    files = {"file": ("time_series_data.csv", csv_file, "text/csv")}
    data = {"tableName": "time_series_data"}
    upload_res = client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["id"]

    # 3. GET Forecast Schema Info
    info_res = client.get(f"/api/v1/projects/{project_id}/forecast/schema-info")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["has_time_series"] is True
    assert len(info_data["candidates"]) >= 1

    # 4. POST Run Project Forecast
    forecast_payload = {
        "dataset_id": dataset_id,
        "date_column": "order_date",
        "target_column": "amount",
        "aggregation": "monthly",
        "horizon": 6,
        "model": "auto",
        "confidence": 0.95
    }
    run_res = client.post(f"/api/v1/projects/{project_id}/forecast", json=forecast_payload)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "success"
    assert run_data["project_id"] == project_id
    assert len(run_data["timeline"]) == 5 + 6
    assert run_data["business_summary"] is not None

    app.dependency_overrides.clear()
