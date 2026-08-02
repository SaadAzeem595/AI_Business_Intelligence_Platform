import os
import tempfile
import pandas as pd
import numpy as np
import joblib
from typing import Dict, Any, List, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest

from app.features.ml.preprocessing import PreprocessingService
from app.features.ml.tracking import TrackingService
from app.features.ml.evaluation import EvaluationService

# Optional ML libraries import
try:
    from xgboost import XGBRegressor, XGBClassifier
except ImportError:
    XGBRegressor = None
    XGBClassifier = None

try:
    from lightgbm import LGBMRegressor, LGBMClassifier
except ImportError:
    LGBMRegressor = None
    LGBMClassifier = None


class ProphetWrapper:
    def __init__(self, interval_width: float = 0.95):
        self.interval_width = interval_width
        self.model = None

    def fit(self, X, y):
        from prophet import Prophet
        df_prophet = pd.DataFrame({
            "ds": pd.to_datetime(X.index),
            "y": y
        })
        self.model = Prophet(interval_width=self.interval_width)
        self.model.fit(df_prophet)
        return self

    def predict(self, X):
        df_prophet = pd.DataFrame({
            "ds": pd.to_datetime(X.index)
        })
        forecast = self.model.predict(df_prophet)
        return forecast["yhat"].values


class ArimaWrapper:
    def __init__(self, order=(1, 1, 1)):
        self.order = order
        self.model_fit = None

    def fit(self, X, y):
        from statsmodels.tsa.api import ARIMA
        y_series = pd.Series(y, index=pd.to_datetime(X.index))
        try:
            y_series = y_series.asfreq(pd.infer_freq(y_series.index))
        except Exception:
            pass
        model = ARIMA(y_series, order=self.order)
        self.model_fit = model.fit()
        return self

    def predict(self, X):
        steps = len(X)
        forecast = self.model_fit.forecast(steps=steps)
        return forecast.values


class ExponentialSmoothingWrapper:
    def __init__(self, trend='add', seasonal=None, seasonal_periods=None):
        self.trend = trend
        self.seasonal = seasonal
        self.seasonal_periods = seasonal_periods
        self.model_fit = None

    def fit(self, X, y):
        from statsmodels.tsa.api import ExponentialSmoothing
        y_series = pd.Series(y, index=pd.to_datetime(X.index))
        try:
            y_series = y_series.asfreq(pd.infer_freq(y_series.index))
        except Exception:
            pass
        model = ExponentialSmoothing(
            y_series,
            trend=self.trend,
            seasonal=self.seasonal,
            seasonal_periods=self.seasonal_periods
        )
        self.model_fit = model.fit()
        return self

    def predict(self, X):
        steps = len(X)
        forecast = self.model_fit.forecast(steps=steps)
        return forecast.values


class TrainingPipelineService:
    """
    Orchestrates the training lifecycle of various ML models (Forecasting, Churn, Segmentation, Anomaly).
    Performs train/val splitting, fits preprocessing, trains models, evaluates metrics,
    and logs everything to MLflow tracking.
    """

    def train_forecasting(
        self,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
        config: Dict[str, Any],
        experiment_name: str = "Sales_Forecasting"
    ) -> Dict[str, Any]:
        """Trains forecasting model (XGBoost, LightGBM, Prophet, or statsmodels ARIMA/ExponentialSmoothing)."""
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col])
        temp = temp.sort_values(by=date_col)
        
        # Temporal split (last 20% as validation)
        split_idx = int(len(temp) * 0.8)
        train_df = temp.iloc[:split_idx].copy()
        val_df = temp.iloc[split_idx:].copy()
        
        # Initialize Preprocessor
        preprocessor = PreprocessingService(
            impute_strategy=config.get("impute_strategy", "median"),
            scaling_method=config.get("scaling_method", "standard"),
            date_cols=[date_col],
            target_col=value_col
        )
        
        # Transform data
        train_processed = preprocessor.fit_transform(train_df)
        val_processed = preprocessor.transform(val_df)
        
        X_train = train_processed.drop(columns=[value_col])
        X_train.index = train_df[date_col]
        y_train = train_processed[value_col].values
        
        X_val = val_processed.drop(columns=[value_col])
        X_val.index = val_df[date_col]
        y_val = val_processed[value_col].values
        
        # Hyperparameters
        n_estimators = config.get("n_estimators", 100)
        max_depth = config.get("max_depth", 5)
        lr = config.get("learning_rate", 0.1)
        model_type = config.get("model_type", "xgboost").lower()
        
        if model_type == "lightgbm" and LGBMRegressor is not None:
            model = LGBMRegressor(n_estimators=n_estimators, max_depth=max_depth, learning_rate=lr, random_state=42, verbose=-1)
        elif model_type == "xgboost" and XGBRegressor is not None:
            model = XGBRegressor(n_estimators=n_estimators, max_depth=max_depth, learning_rate=lr, random_state=42)
        elif model_type == "prophet":
            confidence = config.get("confidence", 0.95)
            model = ProphetWrapper(interval_width=confidence)
        elif model_type == "arima" or model_type == "statsmodels":
            order = config.get("order", (1, 1, 1))
            model = ArimaWrapper(order=order)
        elif model_type == "exponential_smoothing":
            model = ExponentialSmoothingWrapper(trend=config.get("trend", "add"))
        else:
            # Fallback statsmodels simple Holt's linear trend wrapped in fit/predict
            from statsmodels.tsa.api import ExponentialSmoothing
            class FallbackLinearModel:
                def fit(self, X, y):
                    self.es = ExponentialSmoothing(y, trend='add').fit()
                    return self
                def predict(self, X):
                    return self.es.forecast(len(X))
            model = FallbackLinearModel()
            model_type = "fallback_es"
            
        # Log to MLflow
        with TrackingService.start_run(experiment_name, f"Forecast_{model_type}") as run:
            # Train
            model.fit(X_train, y_train)
            
            # Predict & Evaluate
            y_pred = model.predict(X_val)
            eval_results = EvaluationService.evaluate_regression(y_val, y_pred)
            metrics = eval_results["metrics"]
            
            # Persist model and preprocessor to temporary artifacts
            model_dir = tempfile.mkdtemp()
            model_path = os.path.join(model_dir, "model.joblib")
            prep_path = os.path.join(model_dir, "preprocessor.joblib")
            
            joblib.dump(model, model_path)
            preprocessor.save(prep_path)
            
            # Log params, metrics, artifacts, schemas
            TrackingService.log_params({
                "model_type": model_type,
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "learning_rate": lr,
                "date_column": date_col,
                "value_column": value_col
            })
            TrackingService.log_metrics(metrics)
            TrackingService.log_schema(list(X_train.columns), value_col)
            TrackingService.log_artifact(model_path, "model")
            TrackingService.log_artifact(prep_path, "preprocessor")
            
            return {
                "run_id": run.info.run_id,
                "model_path": model_path,
                "preprocessor_path": prep_path,
                "metrics": metrics,
                "params": config
            }


    def train_churn(
        self,
        df: pd.DataFrame,
        target_col: str,
        config: Dict[str, Any],
        experiment_name: str = "Customer_Churn"
    ) -> Dict[str, Any]:
        """Trains customer churn prediction model (XGBoost, LightGBM, or Random Forest)."""
        temp = df.dropna(subset=[target_col]).copy()
        
        # Standard classification split
        from sklearn.model_selection import train_test_split
        train_df, val_df = train_test_split(temp, test_size=0.2, random_state=42)
        
        # Initialize Preprocessor
        preprocessor = PreprocessingService(
            impute_strategy=config.get("impute_strategy", "median"),
            scaling_method=config.get("scaling_method", "standard"),
            target_col=target_col
        )
        
        # Fit transform
        train_processed = preprocessor.fit_transform(train_df)
        val_processed = preprocessor.transform(val_df)
        
        X_train = train_processed.drop(columns=[target_col])
        y_train = train_processed[target_col].values
        X_val = val_processed.drop(columns=[target_col])
        y_val = val_processed[target_col].values
        
        # Target labels encoding check (convert target to float/int if category)
        from sklearn.preprocessing import LabelEncoder
        target_le = None
        if not np.issubdtype(y_train.dtype, np.number):
            target_le = LabelEncoder()
            y_train = target_le.fit_transform(y_train.astype(str))
            y_val = target_le.transform(y_val.astype(str))
            
        # Model Params
        n_estimators = config.get("n_estimators", 100)
        max_depth = config.get("max_depth", 5)
        model_type = config.get("model_type", "random_forest").lower()
        
        if model_type == "xgboost" and XGBClassifier is not None:
            model = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        elif model_type == "lightgbm" and LGBMClassifier is not None:
            model = LGBMClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42, verbose=-1)
        else:
            model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
            model_type = "random_forest"
            
        with TrackingService.start_run(experiment_name, f"Churn_{model_type}") as run:
            model.fit(X_train, y_train)
            
            y_pred = model.predict(X_val)
            y_prob = None
            if hasattr(model, "predict_proba"):
                y_prob = model.predict_proba(X_val)
                
            eval_results = EvaluationService.evaluate_classification(y_val, y_pred, y_prob)
            metrics = eval_results["metrics"]
            
            # Persist model
            model_dir = tempfile.mkdtemp()
            model_path = os.path.join(model_dir, "model.joblib")
            prep_path = os.path.join(model_dir, "preprocessor.joblib")
            
            # Store target encoder inside preprocessor if defined
            if target_le:
                preprocessor.target_encoder = target_le
                
            joblib.dump(model, model_path)
            preprocessor.save(prep_path)
            
            # Log to MLflow
            TrackingService.log_params({
                "model_type": model_type,
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "target_column": target_col
            })
            TrackingService.log_metrics(metrics)
            TrackingService.log_schema(list(X_train.columns), target_col)
            TrackingService.log_artifact(model_path, "model")
            TrackingService.log_artifact(prep_path, "preprocessor")
            
            return {
                "run_id": run.info.run_id,
                "model_path": model_path,
                "preprocessor_path": prep_path,
                "metrics": metrics,
                "params": config
            }

    def train_segmentation(
        self,
        df: pd.DataFrame,
        config: Dict[str, Any],
        experiment_name: str = "Customer_Segmentation"
    ) -> Dict[str, Any]:
        """Trains Customer Segmentation clustering (KMeans)."""
        # Initialize Preprocessor
        preprocessor = PreprocessingService(
            impute_strategy=config.get("impute_strategy", "median"),
            scaling_method=config.get("scaling_method", "standard")
        )
        
        processed_df = preprocessor.fit_transform(df)
        X = processed_df.values
        
        n_clusters = config.get("n_clusters", 3)
        
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        
        with TrackingService.start_run(experiment_name, "Segmentation_KMeans") as run:
            labels = model.fit_predict(X)
            
            eval_results = EvaluationService.evaluate_clustering(X, labels)
            metrics = eval_results["metrics"]
            
            # Persist model
            model_dir = tempfile.mkdtemp()
            model_path = os.path.join(model_dir, "model.joblib")
            prep_path = os.path.join(model_dir, "preprocessor.joblib")
            
            joblib.dump(model, model_path)
            preprocessor.save(prep_path)
            
            # Log to MLflow
            TrackingService.log_params({
                "model_type": "kmeans",
                "n_clusters": n_clusters
            })
            TrackingService.log_metrics(metrics)
            TrackingService.log_schema(list(processed_df.columns), None)
            TrackingService.log_artifact(model_path, "model")
            TrackingService.log_artifact(prep_path, "preprocessor")
            
            return {
                "run_id": run.info.run_id,
                "model_path": model_path,
                "preprocessor_path": prep_path,
                "metrics": metrics,
                "params": config
            }

    def train_anomaly(
        self,
        df: pd.DataFrame,
        config: Dict[str, Any],
        experiment_name: str = "Anomaly_Detection"
    ) -> Dict[str, Any]:
        """Trains Anomaly Detection model (Isolation Forest)."""
        preprocessor = PreprocessingService(
            impute_strategy=config.get("impute_strategy", "median"),
            scaling_method=config.get("scaling_method", "standard")
        )
        
        processed_df = preprocessor.fit_transform(df)
        X = processed_df.values
        
        contamination = config.get("contamination", 0.05)
        
        model = IsolationForest(contamination=contamination, random_state=42)
        
        with TrackingService.start_run(experiment_name, "Anomaly_IsolationForest") as run:
            labels = model.fit_predict(X)
            
            eval_results = EvaluationService.evaluate_anomaly(labels)
            metrics = eval_results["metrics"]
            
            # Persist model
            model_dir = tempfile.mkdtemp()
            model_path = os.path.join(model_dir, "model.joblib")
            prep_path = os.path.join(model_dir, "preprocessor.joblib")
            
            joblib.dump(model, model_path)
            preprocessor.save(prep_path)
            
            # Log to MLflow
            TrackingService.log_params({
                "model_type": "isolation_forest",
                "contamination": contamination
            })
            TrackingService.log_metrics(metrics)
            TrackingService.log_schema(list(processed_df.columns), None)
            TrackingService.log_artifact(model_path, "model")
            TrackingService.log_artifact(prep_path, "preprocessor")
            
            return {
                "run_id": run.info.run_id,
                "model_path": model_path,
                "preprocessor_path": prep_path,
                "metrics": metrics,
                "params": config
            }
