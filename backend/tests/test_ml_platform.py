import pytest
import os
import shutil
import tempfile
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.features.ml.preprocessing import PreprocessingService
from app.features.ml.pipelines import TrainingPipelineService
from app.features.ml.registry import ModelRegistryService
from app.features.ml.inference import InferenceService
from app.features.ml.evaluation import EvaluationService
from app.features.ml.tasks import retrain_model_task


@pytest.fixture(scope="module")
def sample_ml_df():
    """Generates synthetic dataframe for classification, regression, clustering, and anomaly checks."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=60, freq='D')
    
    df = pd.DataFrame({
        "date": dates,
        "customer_id": [f"C-{i % 6}" for i in range(60)],
        "revenue": np.random.uniform(200, 800, 60).tolist(),
        "cost": np.random.uniform(80, 400, 60).tolist(),
        "marketing_spend": np.random.uniform(20, 100, 60).tolist(),
        "conversions": np.random.randint(1, 10, 60).tolist(),
        "visitors": np.random.randint(20, 150, 60).tolist(),
        "x": np.random.normal(5, 1, 60).tolist(),
        "y": np.random.normal(10, 3, 60).tolist(),
        "region": ["North", "South", "East", "West", "North", "South"] * 10,
        "churn": [0, 1, 0, 0, 1, 0] * 10
    })
    return df


@pytest.fixture(scope="module")
def temp_dataset_file(sample_ml_df):
    """Caches dataframe to a local CSV in temp directory."""
    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, "test_dataset.csv")
    sample_ml_df.to_csv(filepath, index=False)
    yield filepath
    shutil.rmtree(tmpdir)


def test_ml_preprocessing(sample_ml_df):
    # Test auto detection of features
    preprocessor = PreprocessingService(target_col="churn")
    transformed = preprocessor.fit_transform(sample_ml_df)
    
    assert preprocessor.is_fitted
    assert "date_year" in transformed.columns
    assert "date_month" in transformed.columns
    assert "churn" in transformed.columns
    
    # Verify save & load serialization parity
    temp_dir = tempfile.mkdtemp()
    save_path = os.path.join(temp_dir, "prep.joblib")
    preprocessor.save(save_path)
    
    loaded_prep = PreprocessingService.load(save_path)
    assert loaded_prep.is_fitted
    assert loaded_prep.target_col == "churn"
    
    shutil.rmtree(temp_dir)


def test_ml_pipelines_and_registry(sample_ml_df):
    pipeline_svc = TrainingPipelineService()
    registry_svc = ModelRegistryService()
    
    # 1. Train forecasting model (uses fallback or XGBoost/LightGBM based on library availability)
    forecasting_config = {
        "model_type": "xgboost",
        "n_estimators": 10,
        "max_depth": 3,
        "learning_rate": 0.1,
        "impute_strategy": "median",
        "scaling_method": "standard"
    }
    
    f_res = pipeline_svc.train_forecasting(
        df=sample_ml_df,
        date_col="date",
        value_col="revenue",
        config=forecasting_config
    )
    
    assert "run_id" in f_res
    assert "model_path" in f_res
    assert "metrics" in f_res
    assert "mae" in f_res["metrics"]
    
    # Register forecasting model in Model Registry
    f_reg = registry_svc.register_model("test_sales_forecast", f_res["run_id"], "Unit Testing Forecast Model")
    assert f_reg["name"] == "test_sales_forecast"
    assert f_reg["version"] >= 1
    
    # Promote forecasting model to Production stage
    f_prom = registry_svc.promote_model("test_sales_forecast", f_reg["version"], "Production")
    assert f_prom["stage"] == "Production"
    
    # 2. Train customer churn classifier
    churn_config = {
        "model_type": "random_forest",
        "n_estimators": 5,
        "max_depth": 3,
        "impute_strategy": "median",
        "scaling_method": "standard"
    }
    
    c_res = pipeline_svc.train_churn(
        df=sample_ml_df,
        target_col="churn",
        config=churn_config
    )
    
    assert "run_id" in c_res
    assert "model_path" in c_res
    assert "accuracy" in c_res["metrics"]
    
    c_reg = registry_svc.register_model("test_customer_churn", c_res["run_id"], "Unit Testing Churn Model")
    assert c_reg["name"] == "test_customer_churn"
    
    c_prom = registry_svc.promote_model("test_customer_churn", c_reg["version"], "Production")
    assert c_prom["stage"] == "Production"


def test_ml_inference(sample_ml_df):
    inf_svc = InferenceService()
    
    # Batch inputs
    inputs = sample_ml_df.head(5).to_dict(orient="records")
    
    # 1. Run inference on churn classifier (Production stage)
    churn_preds = inf_svc.predict(model_name="test_customer_churn", inputs=inputs, stage="Production")
    assert churn_preds["model_name"] == "test_customer_churn"
    assert len(churn_preds["predictions"]) == 5
    assert "probabilities" in churn_preds["predictions"][0]
    
    # 2. Run inference on forecasting model (Production stage)
    forecast_preds = inf_svc.predict(model_name="test_sales_forecast", inputs=inputs, stage="Production")
    assert forecast_preds["model_name"] == "test_sales_forecast"
    assert "confidence_lower" in forecast_preds["predictions"][0]
    assert "confidence_upper" in forecast_preds["predictions"][0]


def test_retrain_celery_task(temp_dataset_file):
    # Mocking cache registration to direct file loading in resolve_dataset_path
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    mock_id = "test-retrain-id"
    UPLOADED_PATHS_CACHE[mock_id] = {
        "path": temp_dataset_file,
        "filename": "test_dataset.csv"
    }
    
    # Test running retraining task synchronously
    retrain_config = {
        "target_col": "churn",
        "model_type": "random_forest",
        "n_estimators": 5,
        "max_depth": 3,
        "impute_strategy": "median",
        "scaling_method": "standard"
    }
    
    task_res = retrain_model_task(
        model_type="churn",
        dataset_id=mock_id,
        config=retrain_config
    )
    
    assert task_res["status"] == "success"
    assert task_res["model_name"] == "customer_churn"
    assert task_res["version"] >= 1
    
    # Cleanup mock path
    UPLOADED_PATHS_CACHE.pop(mock_id)


def test_api_routes(temp_dataset_file):
    # Mock cache
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    mock_id = "test-api-id"
    UPLOADED_PATHS_CACHE[mock_id] = {
        "path": temp_dataset_file,
        "filename": "test_dataset.csv"
    }
    
    client = TestClient(app)
    
    # Simulate Authentication:
    # Router uses get_current_user dependency, which has mock fallback.
    # In app/core/dependencies.py, get_current_user returns MockUser if no Authorization header,
    # let's verify if client works directly.
    
    # 1. Trigger training synchronously via API
    train_payload = {
        "model_type": "churn",
        "dataset_id": mock_id,
        "config": {
            "target_col": "churn",
            "model_type": "random_forest",
            "n_estimators": 5,
            "max_depth": 3
        },
        "background": False # Sync for testing returns results directly
    }
    
    train_response = client.post("/api/v1/ml/train", json=train_payload)
    assert train_response.status_code == 200
    train_json = train_response.json()
    assert train_json["status"] == "success"
    assert train_json["model_name"] == "customer_churn"
    
    # 2. Trigger predictions via API
    predict_payload = {
        "model_name": "customer_churn",
        "inputs": [
            {
                "date": "2026-06-01",
                "customer_id": "C-1",
                "revenue": 500.0,
                "cost": 200.0,
                "marketing_spend": 50.0,
                "conversions": 3,
                "visitors": 80,
                "x": 4.5,
                "y": 9.2,
                "region": "West"
            }
        ],
        "stage": "Production"
    }
    
    predict_response = client.post("/api/v1/ml/predict", json=predict_payload)
    assert predict_response.status_code == 200
    predict_json = predict_response.json()
    assert predict_json["model_name"] == "customer_churn"
    assert len(predict_json["predictions"]) == 1
    assert "probabilities" in predict_json["predictions"][0]
    
    # 3. List registered models via API
    list_response = client.get("/api/v1/ml/models")
    assert list_response.status_code == 200
    list_json = list_response.json()
    assert len(list_json) > 0
    
    # 4. Promote model via API
    promote_payload = {
        "model_name": "customer_churn",
        "version": 1,
        "stage": "Staging"
    }
    promote_response = client.post("/api/v1/ml/models/promote", json=promote_payload)
    assert promote_response.status_code == 200
    promote_json = promote_response.json()
    assert promote_json["stage"] == "Staging"
    
    # Cleanup mock
    UPLOADED_PATHS_CACHE.pop(mock_id)
