import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional, Type
import duckdb
from app.features.analytics.engine.utils import load_dataset
import logging

logger = logging.getLogger(__name__)

# Try to import optional ML libraries
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.api import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score

class BaseForecaster(ABC):
    """
    Abstract base class for all forecasting models.
    """
    @abstractmethod
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        pass

def _create_date_features(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    df_feat = pd.DataFrame(index=df.index)
    df_feat['trend'] = np.arange(len(df))
    dates = pd.to_datetime(df[date_col])
    df_feat['month'] = dates.dt.month
    df_feat['day'] = dates.dt.day
    df_feat['dayofweek'] = dates.dt.dayofweek
    df_feat['year'] = dates.dt.year
    return df_feat


class ArimaForecaster(BaseForecaster):
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col])
        temp = temp.sort_values(by=date_col)
        
        series = temp[value_col].values
        if len(series) < 3:
            # Too short for ARIMA, use simple exponential smoothing or regression
            return FallbackForecaster().fit_predict(df, date_col, value_col, periods, confidence)
            
        try:
            model = ARIMA(series, order=(1, 1, 1))
            res = model.fit()
            
            in_sample = res.predict(start=0, end=len(series)-1)
            r2 = r2_score(series, in_sample) if len(series) > 2 else 0.0
            mae = mean_absolute_error(series, in_sample) if len(series) > 0 else 0.0
            rmse = root_mean_squared_error(series, in_sample) if len(series) > 0 else 0.0
            
            forecast_res = res.get_forecast(steps=periods)
            forecast_val = forecast_res.predicted_mean
            ci = forecast_res.conf_int(alpha=1.0 - confidence)
        except Exception as e:
            logger.warning(f"ARIMA fit failed: {str(e)}. Falling back.")
            return FallbackForecaster().fit_predict(df, date_col, value_col, periods, confidence)
            
        last_date = temp[date_col].iloc[-1]
        freq = pd.infer_freq(temp[date_col]) or 'D'
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]
        
        history_points = []
        for _, row in temp.iterrows():
            history_points.append({
                "date": row[date_col].strftime("%Y-%m-%d"),
                "actual": float(row[value_col]),
                "forecast": None,
                "lower": None,
                "upper": None
            })
            
        forecast_points = []
        for i in range(periods):
            val = float(forecast_val[i])
            lower = float(ci[i, 0]) if i < len(ci) else val * 0.9
            upper = float(ci[i, 1]) if i < len(ci) else val * 1.1
            forecast_points.append({
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "actual": None,
                "forecast": val,
                "lower": max(0.0, lower),
                "upper": upper
            })
            
        metrics = {
            "r_squared": float(r2),
            "mae": float(mae),
            "rmse": float(rmse),
            "model": "ARIMA(1,1,1)"
        }
        
        return history_points + forecast_points, metrics


class ProphetForecaster(BaseForecaster):
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet library is not installed.")
            
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col])
        temp = temp.sort_values(by=date_col)
        
        pdf = pd.DataFrame({
            'ds': temp[date_col],
            'y': temp[value_col]
        })
        
        m = Prophet(interval_width=confidence)
        m.fit(pdf)
        
        in_sample = m.predict(pdf)
        r2 = r2_score(pdf['y'], in_sample['yhat'])
        mae = mean_absolute_error(pdf['y'], in_sample['yhat'])
        rmse = root_mean_squared_error(pdf['y'], in_sample['yhat'])
        
        future = m.make_future_dataframe(periods=periods)
        forecast = m.predict(future)
        
        history_points = []
        for _, row in temp.iterrows():
            history_points.append({
                "date": row[date_col].strftime("%Y-%m-%d"),
                "actual": float(row[value_col]),
                "forecast": None,
                "lower": None,
                "upper": None
            })
            
        forecast_points = []
        future_forecast = forecast.tail(periods)
        for _, row in future_forecast.iterrows():
            forecast_points.append({
                "date": row['ds'].strftime("%Y-%m-%d"),
                "actual": None,
                "forecast": float(row['yhat']),
                "lower": max(0.0, float(row['yhat_lower'])),
                "upper": float(row['yhat_upper'])
            })
            
        metrics = {
            "r_squared": float(r2),
            "mae": float(mae),
            "rmse": float(rmse),
            "model": "Prophet"
        }
        
        return history_points + forecast_points, metrics


class XGBoostForecaster(BaseForecaster):
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost library is not installed.")
            
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col])
        temp = temp.sort_values(by=date_col)
        
        X = _create_date_features(temp, date_col)
        y = temp[value_col].values
        
        from xgboost import XGBRegressor
        model = XGBRegressor(n_estimators=50, max_depth=4, learning_rate=0.1, random_state=42)
        model.fit(X, y)
        
        in_sample = model.predict(X)
        r2 = r2_score(y, in_sample) if len(y) > 2 else 0.0
        mae = mean_absolute_error(y, in_sample) if len(y) > 0 else 0.0
        rmse = root_mean_squared_error(y, in_sample) if len(y) > 0 else 0.0
        
        last_date = temp[date_col].iloc[-1]
        freq = pd.infer_freq(temp[date_col]) or 'D'
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]
        
        future_df = pd.DataFrame({date_col: future_dates})
        future_df.index = np.arange(len(temp), len(temp) + periods)
        
        X_future = pd.DataFrame(index=future_df.index)
        X_future['trend'] = future_df.index
        X_future['month'] = future_df[date_col].dt.month
        X_future['day'] = future_df[date_col].dt.day
        X_future['dayofweek'] = future_df[date_col].dt.dayofweek
        X_future['year'] = future_df[date_col].dt.year
        
        forecast_val = model.predict(X_future)
        
        residuals = y - in_sample
        std_resid = np.std(residuals) if len(residuals) > 1 else y.mean() * 0.1
        z = 1.96
        
        history_points = []
        for _, row in temp.iterrows():
            history_points.append({
                "date": row[date_col].strftime("%Y-%m-%d"),
                "actual": float(row[value_col]),
                "forecast": None,
                "lower": None,
                "upper": None
            })
            
        forecast_points = []
        for i in range(periods):
            val = float(forecast_val[i])
            forecast_points.append({
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "actual": None,
                "forecast": val,
                "lower": max(0.0, val - z * std_resid),
                "upper": val + z * std_resid
            })
            
        metrics = {
            "r_squared": float(r2),
            "mae": float(mae),
            "rmse": float(rmse),
            "model": "XGBoost Regressor"
        }
        
        return history_points + forecast_points, metrics


class LightGBMForecaster(BaseForecaster):
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("LightGBM library is not installed.")
            
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col])
        temp = temp.sort_values(by=date_col)
        
        X = _create_date_features(temp, date_col)
        y = temp[value_col].values
        
        from lightgbm import LGBMRegressor
        model = LGBMRegressor(n_estimators=50, max_depth=4, learning_rate=0.1, random_state=42, verbose=-1)
        model.fit(X, y)
        
        in_sample = model.predict(X)
        r2 = r2_score(y, in_sample) if len(y) > 2 else 0.0
        mae = mean_absolute_error(y, in_sample) if len(y) > 0 else 0.0
        rmse = root_mean_squared_error(y, in_sample) if len(y) > 0 else 0.0
        
        last_date = temp[date_col].iloc[-1]
        freq = pd.infer_freq(temp[date_col]) or 'D'
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]
        
        future_df = pd.DataFrame({date_col: future_dates})
        future_df.index = np.arange(len(temp), len(temp) + periods)
        
        X_future = pd.DataFrame(index=future_df.index)
        X_future['trend'] = future_df.index
        X_future['month'] = future_df[date_col].dt.month
        X_future['day'] = future_df[date_col].dt.day
        X_future['dayofweek'] = future_df[date_col].dt.dayofweek
        X_future['year'] = future_df[date_col].dt.year
        
        forecast_val = model.predict(X_future)
        
        residuals = y - in_sample
        std_resid = np.std(residuals) if len(residuals) > 1 else y.mean() * 0.1
        z = 1.96
        
        history_points = []
        for _, row in temp.iterrows():
            history_points.append({
                "date": row[date_col].strftime("%Y-%m-%d"),
                "actual": float(row[value_col]),
                "forecast": None,
                "lower": None,
                "upper": None
            })
            
        forecast_points = []
        for i in range(periods):
            val = float(forecast_val[i])
            forecast_points.append({
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "actual": None,
                "forecast": val,
                "lower": max(0.0, val - z * std_resid),
                "upper": val + z * std_resid
            })
            
        metrics = {
            "r_squared": float(r2),
            "mae": float(mae),
            "rmse": float(rmse),
            "model": "LightGBM Regressor"
        }
        
        return history_points + forecast_points, metrics


class FallbackForecaster(BaseForecaster):
    def fit_predict(
        self, 
        df: pd.DataFrame, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        temp = df[[date_col, value_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col])
        temp = temp.sort_values(by=date_col)
        
        series = temp[value_col].values
        if len(series) == 0:
            return [], {"r_squared": 0.0, "mae": 0.0, "rmse": 0.0, "model": "Empty Model"}
            
        try:
            # Simple Exponential Smoothing
            model = ExponentialSmoothing(series, trend='add', seasonal=None)
            res = model.fit()
            forecast_val = res.forecast(periods)
            in_sample = res.fittedvalues
        except Exception:
            # Constant fallback to last observed value
            in_sample = np.full(len(series), series[-1])
            forecast_val = np.full(periods, series[-1])
            
        r2 = r2_score(series, in_sample) if len(series) > 2 else 0.0
        mae = mean_absolute_error(series, in_sample) if len(series) > 0 else 0.0
        rmse = root_mean_squared_error(series, in_sample) if len(series) > 0 else 0.0
        
        last_date = temp[date_col].iloc[-1]
        freq = pd.infer_freq(temp[date_col]) or 'D'
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]
        
        std_val = np.std(series) if len(series) > 1 else series[0] * 0.1
        
        history_points = []
        for _, row in temp.iterrows():
            history_points.append({
                "date": row[date_col].strftime("%Y-%m-%d"),
                "actual": float(row[value_col]),
                "forecast": None,
                "lower": None,
                "upper": None
            })
            
        forecast_points = []
        for i in range(periods):
            val = float(forecast_val[i])
            forecast_points.append({
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "actual": None,
                "forecast": val,
                "lower": max(0.0, val - 1.96 * std_val),
                "upper": val + 1.96 * std_val
            })
            
        metrics = {
            "r_squared": float(r2),
            "mae": float(mae),
            "rmse": float(rmse),
            "model": "Exponential Smoothing (Fallback)"
        }
        
        return history_points + forecast_points, metrics


class ForecastingService:
    """
    Forecasting service with pluggable, registerable model backends.
    """
    _registry: Dict[str, Type[BaseForecaster]] = {}
    
    @classmethod
    def register_model(cls, name: str, forecaster_class: Type[BaseForecaster]):
        """
        Registers a pluggable forecasting model.
        """
        cls._registry[name.lower().strip()] = forecaster_class
        
    def forecast(
        self, 
        dataset_ref: str, 
        model_name: str, 
        date_col: str, 
        value_col: str, 
        periods: int, 
        confidence: float = 0.95,
        conn: Optional[duckdb.DuckDBPyConnection] = None
    ) -> Dict[str, Any]:
        """
        Executes forecasting on the dataset using the specified pluggable model.
        """
        df = load_dataset(dataset_ref, conn)
        
        model_key = model_name.lower().strip()
        forecaster_cls = self._registry.get(model_key)
        
        if not forecaster_cls:
            logger.warning(f"Forecasting model '{model_name}' not found. Falling back to ARIMA.")
            forecaster_cls = ArimaForecaster
            
        forecaster = forecaster_cls()
        try:
            timeline, metrics = forecaster.fit_predict(df, date_col, value_col, periods, confidence)
            return {
                "model_used": model_name,
                "timeline": timeline,
                "metrics": metrics
            }
        except Exception as err:
            logger.error(f"Model '{model_name}' failed with error: {str(err)}. Executing fallback.")
            fallback = FallbackForecaster()
            timeline, metrics = fallback.fit_predict(df, date_col, value_col, periods, confidence)
            return {
                "model_used": f"{model_name} (Fallback to ES)",
                "timeline": timeline,
                "metrics": metrics
            }

# Register default models
ForecastingService.register_model("arima", ArimaForecaster)
ForecastingService.register_model("prophet", ProphetForecaster)
ForecastingService.register_model("xgboost", XGBoostForecaster)
ForecastingService.register_model("lightgbm", LightGBMForecaster)
