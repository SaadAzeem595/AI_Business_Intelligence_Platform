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
    app.dependency_overrides.clear()


def test_strict_date_column_validation():
    """Tests strict date column validation and rejection of numeric/product attribute columns."""
    from app.features.analytics.engine.discovery import is_valid_date_column

    # 1. Product attributes / numeric columns MUST be rejected
    df = pd.DataFrame({
        "product_width_cm": [10.5, 12.0, 14.5, 20.0],
        "product_height_cm": [5.0, 6.0, 7.0, 8.0],
        "product_length_cm": [15.0, 16.0, 17.0, 18.0],
        "product_name_lenght": [30, 45, 50, 60],
        "price": [99.99, 149.99, 199.99, 299.99],
        "quantity": [1, 2, 5, 10],
        "created_at": ["2026-01-01 10:00:00", "2026-01-02 11:00:00", "2026-01-03 12:00:00", "2026-01-04 13:00:00"],
        "order_purchase_timestamp": ["2026-02-01", "2026-02-02", "2026-02-03", "2026-02-04"]
    })

    assert is_valid_date_column(df, "product_width_cm") is False
    assert is_valid_date_column(df, "product_height_cm") is False
    assert is_valid_date_column(df, "product_length_cm") is False
    assert is_valid_date_column(df, "product_name_lenght") is False
    assert is_valid_date_column(df, "price") is False
    assert is_valid_date_column(df, "quantity") is False

    # Valid date columns must be accepted
    assert is_valid_date_column(df, "created_at") is True
    assert is_valid_date_column(df, "order_purchase_timestamp") is True


def test_product_width_cm_rejected_in_forecast_api():
    """Tests API rejection of non-temporal date column requests (product_width_cm)."""
    client = TestClient(app)
    set_active_user("user_date_test")

    create_res = client.post("/api/v1/projects", json={"name": "Date Validation Project"})
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    forecast_payload = {
        "dataset_id": "ds_test",
        "date_column": "product_width_cm",
        "target_column": "product_name_lenght",
        "aggregation": "monthly",
        "horizon": 6
    }
    run_res = client.post(f"/api/v1/projects/{project_id}/forecast", json=forecast_payload)
    assert run_res.status_code == 422
    assert "non-temporal attribute" in run_res.json()["detail"]

    app.dependency_overrides.clear()


def test_electric_production_forecast():
    """Integration test verifying Electric_Production.csv forecasting with DATE and IPG2211A2N."""
    client = TestClient(app)
    set_active_user("user_electric_prod_test")

    # 1. Create a test project
    create_res = client.post("/api/v1/projects", json={"name": "Electric Production Project", "description": "Testing monthly forecast"})
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    # 2. Upload Electric_Production.csv format dataset
    csv_content = (
        b"DATE,IPG2211A2N\n"
        b"1985-01-01,72.5052\n"
        b"1985-02-01,70.6720\n"
        b"1985-03-01,62.4502\n"
        b"1985-04-01,57.4714\n"
        b"1985-05-01,55.3151\n"
        b"1985-06-01,58.0904\n"
        b"1985-07-01,62.6202\n"
        b"1985-08-01,63.2525\n"
        b"1985-09-01,60.5846\n"
        b"1985-10-01,56.3154\n"
        b"1985-11-01,58.0005\n"
        b"1985-12-01,68.7149\n"
    )
    csv_file = io.BytesIO(csv_content)
    files = {"file": ("Electric_Production.csv", csv_file, "text/csv")}
    data = {"tableName": "Electric_Production"}
    upload_res = client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert upload_res.status_code == 200
    dataset_id = upload_res.json()["id"]

    # 3. Resolve schema info
    info_res = client.get(f"/api/v1/projects/{project_id}/forecast/schema-info")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["has_time_series"] is True

    candidate = next(c for c in info_data["candidates"] if c["dataset_id"] == dataset_id or "Electric_Production" in c["dataset_name"])
    assert candidate["suggested_date"] == "DATE"
    assert candidate["suggested_metric"] == "IPG2211A2N"

    # 4. Request monthly forecasting for 6 periods
    forecast_payload = {
        "dataset_id": dataset_id,
        "date_column": "DATE",
        "target_column": "IPG2211A2N",
        "aggregation": "monthly",
        "horizon": 6,
        "model": "auto",
        "confidence": 0.95
    }
    run_res = client.post(f"/api/v1/projects/{project_id}/forecast", json=forecast_payload)
    assert run_res.status_code == 200
    run_data = run_res.json()

    # 5. Verify response fields
    assert run_data["status"] == "success", f"Forecast error message: {run_data.get('message')}"
    assert run_data["project_id"] == project_id
    assert run_data["dataset_id"] == dataset_id

    # Verify timeline contains 12 historical actuals + 6 forecast points = 18 total
    timeline = run_data["timeline"]
    actual_pts = [p for p in timeline if p["actual"] is not None]
    forecast_pts = [p for p in timeline if p["forecast"] is not None]

    assert len(actual_pts) == 12
    assert len(forecast_pts) == 6

    # Verify numeric values and valid bounds
    for pt in forecast_pts:
        assert isinstance(pt["forecast"], (int, float))
        assert pt["lower"] is not None and isinstance(pt["lower"], (int, float))
        assert pt["upper"] is not None and isinstance(pt["upper"], (int, float))
        assert pt["lower"] <= pt["upper"]
        assert len(pt["date"]) == 10  # YYYY-MM-DD

    app.dependency_overrides.clear()


def test_multi_date_format_and_excel_date_detection():
    """Tests date column validation and safe parsing across DD/MM/YYYY, MM/DD/YYYY, YYYY/MM/DD, and Excel dates."""
    from app.features.analytics.engine.discovery import is_valid_date_column
    from app.features.analytics.engine.forecasting import safe_parse_datetime_series

    # 1. DD/MM/YYYY strings
    df_dd_mm = pd.DataFrame({
        "transaction_date": ["15/01/2026", "16/01/2026", "17/01/2026", "18/01/2026"],
        "sales": [100, 200, 300, 400]
    })
    assert is_valid_date_column(df_dd_mm, "transaction_date") is True
    parsed = safe_parse_datetime_series(df_dd_mm["transaction_date"])
    assert parsed.isna().sum() == 0

    # 2. MM/DD/YYYY strings
    df_mm_dd = pd.DataFrame({
        "order_date": ["01/15/2026", "01/16/2026", "01/17/2026", "01/18/2026"],
        "sales": [100, 200, 300, 400]
    })
    assert is_valid_date_column(df_mm_dd, "order_date") is True
    parsed_mm = safe_parse_datetime_series(df_mm_dd["order_date"])
    assert parsed_mm.isna().sum() == 0

    # 3. Excel serial numbers (e.g. 44196 = 2021-01-01)
    df_excel = pd.DataFrame({
        "timestamp_col": [44196, 44227, 44255, 44286],
        "metric": [50.0, 60.0, 70.0, 80.0]
    })
    parsed_excel = safe_parse_datetime_series(df_excel["timestamp_col"])
    assert parsed_excel.isna().sum() == 0
    assert parsed_excel.dt.year.iloc[0] in [2020, 2021]


def test_forecasting_health_check_endpoint():
    """Tests GET /api/v1/forecasting/health and GET /api/v1/projects/{project_id}/forecast/health."""
    client = TestClient(app)
    set_active_user("user_health_test")

    res1 = client.get("/api/v1/forecasting/health")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["api"] == "ok"
    assert data1["forecasting_router"] == "ok"

    res2 = client.get("/api/v1/projects/proj_test_123/forecast/health")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["api"] == "ok"
    assert data2["project_id"] == "proj_test_123"

    app.dependency_overrides.clear()



