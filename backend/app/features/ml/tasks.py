from app.worker import celery_app
from app.features.ml.pipelines import TrainingPipelineService
from app.features.ml.registry import ModelRegistryService
from app.features.analytics.router import resolve_dataset_path
from app.features.analytics.engine.utils import load_dataset
import logging
import time
from app.core.telemetry import BACKGROUND_TASK_LATENCY

logger = logging.getLogger(__name__)

@celery_app.task(name="retrain_model_task")
def retrain_model_task(model_type: str, dataset_id: str, config: dict) -> dict:
    """
    Celery background worker task to retrain, log, and register models.
    
    Args:
        model_type: The type of model to train (forecast, churn, segmentation, anomaly)
        dataset_id: The ID of the dataset to train on
        config: Hyperparameters and column configuration
        
    Returns:
        Dict containing training results, registered version, and metrics.
    """
    logger.info(f"Starting Celery background retraining task for model type '{model_type}'...")
    start_time = time.perf_counter()
    try:
        # Resolve dataset path and load dataset
        dataset_path = resolve_dataset_path(dataset_id)
        df = load_dataset(dataset_path)
        
        # Initialize training and registry services
        pipeline_svc = TrainingPipelineService()
        registry_svc = ModelRegistryService()
        
        res = None
        model_type = model_type.lower().strip()
        
        if model_type == "forecast":
            col_map = {col.strip().lower(): col for col in df.columns}
            date_col = next((col_map[s] for s in ['date', 'time', 'timestamp', 'transaction_date'] if s in col_map), df.columns[0])
            value_col = next((col_map[s] for s in ['revenue', 'sales', 'amount', 'profit'] if s in col_map), df.columns[-1])
            res = pipeline_svc.train_forecasting(df, date_col, value_col, config)
            registry_name = "sales_forecast"
            
        elif model_type == "churn":
            target_col = config.get("target_col", "churn")
            res = pipeline_svc.train_churn(df, target_col, config)
            registry_name = "customer_churn"
            
        elif model_type == "segmentation":
            res = pipeline_svc.train_segmentation(df, config)
            registry_name = "customer_segmentation"
            
        elif model_type == "anomaly":
            res = pipeline_svc.train_anomaly(df, config)
            registry_name = "anomaly_detector"
            
        else:
            raise ValueError(f"Unsupported model type for retraining: '{model_type}'")
            
        # Register model version in Model Registry
        reg_res = registry_svc.register_model(
            model_name=registry_name,
            run_id=res["run_id"],
            description=f"Auto-retrained via Celery on dataset {dataset_id}"
        )
        
        # Auto promote model to Production stage
        registry_svc.promote_model(
            model_name=registry_name,
            version=reg_res["version"],
            stage="Production"
        )
        
        # Invalidate ML predictions cache
        try:
            from app.core.cache import cache_client, run_async_as_sync
            run_async_as_sync(cache_client.invalidate_pattern(f"ml_predict:{registry_name}:*"))
        except Exception:
            pass
        
        duration = time.perf_counter() - start_time
        BACKGROUND_TASK_LATENCY.labels(task_name="retrain_model_task").observe(duration)
        
        return {
            "status": "success",
            "model_name": registry_name,
            "version": reg_res["version"],
            "run_id": res["run_id"],
            "metrics": res["metrics"]
        }
        
    except Exception as err:
        duration = time.perf_counter() - start_time
        BACKGROUND_TASK_LATENCY.labels(task_name="retrain_model_task").observe(duration)
        logger.error(f"Retraining task failed: {str(err)}")
        return {
            "status": "failed",
            "error": str(err)
        }


@celery_app.task(name="scheduled_retrain_task")
def scheduled_retrain_task(model_type: str) -> dict:
    """
    Periodic background task to retrain a specific model type on the active dataset.
    """
    logger.info(f"Triggering scheduled retraining for model type '{model_type}'...")
    
    config = {}
    model_type = model_type.lower().strip()
    
    if model_type == "forecast":
        config = {
            "model_type": "xgboost",
            "n_estimators": 50,
            "max_depth": 5,
            "learning_rate": 0.1,
            "impute_strategy": "median",
            "scaling_method": "standard"
        }
    elif model_type == "churn":
        config = {
            "target_col": "churn",
            "model_type": "random_forest",
            "n_estimators": 50,
            "max_depth": 5,
            "impute_strategy": "median",
            "scaling_method": "standard"
        }
    elif model_type == "segmentation":
        config = {
            "n_clusters": 4,
            "impute_strategy": "median",
            "scaling_method": "standard"
        }
    elif model_type == "anomaly":
        config = {
            "contamination": 0.05,
            "impute_strategy": "median",
            "scaling_method": "standard"
        }
    else:
        raise ValueError(f"Unsupported model type for scheduled retraining: '{model_type}'")
        
    return retrain_model_task(model_type=model_type, dataset_id=None, config=config)

