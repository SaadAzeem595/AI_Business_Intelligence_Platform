import mlflow
import time
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

class TrackingService:
    """
    Handles logging and tracking of experiments via MLflow.
    Stores metadata (parameters, metrics, schemas) and artifacts locally.
    """
    _initialized = False
    
    @classmethod
    def init_mlflow(cls):
        if not cls._initialized:
            # Set local sqlite DB as the backend registry and log store
            mlflow.set_tracking_uri("sqlite:///mlflow.db")
            cls._initialized = True
            
    @classmethod
    @contextmanager
    def start_run(cls, experiment_name: str, run_name: Optional[str] = None):
        """Context manager to start and automatically end an MLflow run."""
        cls.init_mlflow()
        mlflow.set_experiment(experiment_name)
        
        start_time = time.perf_counter()
        run = mlflow.start_run(run_name=run_name)
        try:
            yield run
        except Exception as e:
            mlflow.log_param("error_occurred", "True")
            mlflow.log_param("error_message", str(e))
            raise e
        finally:
            duration = time.perf_counter() - start_time
            mlflow.log_metric("training_duration_seconds", duration)
            mlflow.end_run()
            
    @classmethod
    def log_params(cls, params: Dict[str, Any]):
        """Logs hyperparameters or configuration dictionaries."""
        cls.init_mlflow()
        clean_params = {}
        for k, v in params.items():
            if isinstance(v, (dict, list, set)):
                clean_params[str(k)] = str(v)[:250]
            else:
                clean_params[str(k)] = v
        mlflow.log_params(clean_params)
        
    @classmethod
    def log_metrics(cls, metrics: Dict[str, float]):
        """Logs evaluation metrics."""
        cls.init_mlflow()
        mlflow.log_metrics({str(k): float(v) for k, v in metrics.items() if v is not None})
        
    @classmethod
    def log_artifact(cls, local_path: str, artifact_path: Optional[str] = None):
        """Logs local artifact file (e.g. pickled model, preprocessor)."""
        cls.init_mlflow()
        mlflow.log_artifact(local_path, artifact_path)
        
    @classmethod
    def log_schema(cls, columns: List[str], target_col: Optional[str] = None):
        """Logs the feature schema and targets used in the run."""
        cls.init_mlflow()
        mlflow.log_param("feature_columns", ",".join(columns))
        if target_col:
            mlflow.log_param("target_column", target_col)
