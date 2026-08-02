import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from typing import Dict, Any, List, Optional
import joblib

class PreprocessingService:
    """
    Handles training-serving feature preprocessing configurations and persists them.
    Supports missing values imputation, numeric scaling, category encoding,
    date feature extraction, and feature selection.
    """
    def __init__(
        self,
        impute_strategy: str = "median",
        scaling_method: str = "standard",
        categorical_encoding: str = "label",
        numeric_cols: Optional[List[str]] = None,
        categorical_cols: Optional[List[str]] = None,
        date_cols: Optional[List[str]] = None,
        feature_cols: Optional[List[str]] = None,
        target_col: Optional[str] = None
    ):
        self.impute_strategy = impute_strategy
        self.scaling_method = scaling_method
        self.categorical_encoding = categorical_encoding
        
        self.numeric_cols = numeric_cols or []
        self.categorical_cols = categorical_cols or []
        self.date_cols = date_cols or []
        self.feature_cols = feature_cols or []
        self.target_col = target_col
        
        self.impute_values: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.encoders: Dict[str, LabelEncoder] = {}
        self.is_fitted = False
        
    def fit(self, df: pd.DataFrame):
        """Fits preprocessing pipelines on the training set."""
        temp = df.copy()
        
        # 1. Auto detect columns if not specified
        if not self.numeric_cols and not self.categorical_cols and not self.date_cols:
            self._auto_detect_columns(temp)
            
        # 2. Extract date features
        self._fit_extract_date_features(temp)
        
        # Update numeric columns list with newly extracted date columns
        for dcol in self.date_cols:
            for ext in ["year", "month", "day", "dayofweek", "is_weekend"]:
                ext_name = f"{dcol}_{ext}"
                if ext_name in temp.columns and ext_name not in self.numeric_cols:
                    self.numeric_cols.append(ext_name)
                    
        # 3. Fit Imputers
        for col in self.numeric_cols:
            if col in temp.columns:
                series = temp[col].dropna()
                if self.impute_strategy == "mean":
                    self.impute_values[col] = float(series.mean()) if len(series) > 0 else 0.0
                elif self.impute_strategy == "mode":
                    self.impute_values[col] = float(series.mode().iloc[0]) if len(series) > 0 else 0.0
                else: # median
                    self.impute_values[col] = float(series.median()) if len(series) > 0 else 0.0
                    
        for col in self.categorical_cols:
            if col in temp.columns:
                series = temp[col].dropna()
                self.impute_values[col] = str(series.mode().iloc[0]) if len(series) > 0 else "unknown"
                
        # Apply imputation
        for col, val in self.impute_values.items():
            if col in temp.columns:
                temp[col] = temp[col].fillna(val)
                
        # 4. Fit Encoders
        for col in self.categorical_cols:
            if col in temp.columns:
                le = LabelEncoder()
                unique_vals = list(temp[col].astype(str).unique())
                if 'unknown' not in unique_vals:
                    unique_vals.append('unknown')
                le.fit(unique_vals)
                self.encoders[col] = le
                
        # 5. Fit Scalers
        if self.scaling_method in ["standard", "minmax"] and len(self.numeric_cols) > 0:
            from sklearn.preprocessing import StandardScaler, MinMaxScaler
            scaler_class = StandardScaler if self.scaling_method == "standard" else MinMaxScaler
            for col in self.numeric_cols:
                if col in temp.columns:
                    sc = scaler_class()
                    sc.fit(temp[[col]])
                    self.scalers[col] = sc
                    
        self.is_fitted = True
        return self
        
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies fitted preprocessors to a new DataFrame."""
        if not self.is_fitted:
            raise ValueError("Preprocessing pipeline must be fitted before transforming.")
            
        temp = df.copy()
        
        # 1. Date extraction
        self._transform_extract_date_features(temp)
        
        # 2. Imputation
        for col, val in self.impute_values.items():
            if col in temp.columns:
                temp[col] = temp[col].fillna(val)
            elif col not in temp.columns and col in (self.numeric_cols + self.categorical_cols):
                temp[col] = val
                
        # 3. Categorical encoding
        for col, le in self.encoders.items():
            if col in temp.columns:
                known_classes = set(le.classes_)
                temp[col] = temp[col].astype(str).apply(lambda x: x if x in known_classes else 'unknown')
                temp[col] = le.transform(temp[col])
                
        # 4. Scaling
        for col, sc in self.scalers.items():
            if col in temp.columns:
                temp[[col]] = sc.transform(temp[[col]])
                
        # 5. Feature Selection
        selected_cols = []
        if self.feature_cols:
            selected_cols = [c for c in self.feature_cols if c in temp.columns]
        else:
            selected_cols = [c for c in self.numeric_cols + self.categorical_cols if c in temp.columns]
            
        if self.target_col and self.target_col in temp.columns:
            selected_cols.append(self.target_col)
            
        # Ensure we return at least index columns or features
        return temp[selected_cols]
        
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        self.fit(df)
        return self.transform(df)
        
    def _auto_detect_columns(self, df: pd.DataFrame):
        for col in df.columns:
            if col == self.target_col:
                continue
            if pd.api.types.is_datetime64_any_dtype(df[col]) or any(x in str(col).lower() for x in ['date', 'time', 'timestamp', 'created_at']):
                self.date_cols.append(str(col))
            elif pd.api.types.is_numeric_dtype(df[col]):
                if not any(x in str(col).lower() for x in ['id', 'key', 'index']):
                    self.numeric_cols.append(str(col))
            else:
                if not any(x in str(col).lower() for x in ['id', 'key', 'index']):
                    self.categorical_cols.append(str(col))
                    
    def _fit_extract_date_features(self, df: pd.DataFrame):
        for col in self.date_cols:
            if col in df.columns:
                try:
                    parsed = pd.to_datetime(df[col], errors='coerce')
                    median_date = parsed.dropna().median() if len(parsed.dropna()) > 0 else pd.Timestamp.now()
                    self.impute_values[col] = median_date
                except Exception:
                    self.impute_values[col] = pd.Timestamp.now()
            
            default_date = self.impute_values.get(col, pd.Timestamp.now())
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors='coerce').fillna(default_date)
            else:
                parsed = pd.Series(pd.Timestamp(default_date), index=df.index)
                
            df[f"{col}_year"] = parsed.dt.year
            df[f"{col}_month"] = parsed.dt.month
            df[f"{col}_day"] = parsed.dt.day
            df[f"{col}_dayofweek"] = parsed.dt.dayofweek
            df[f"{col}_is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype(int)
                    
    def _transform_extract_date_features(self, df: pd.DataFrame):
        for col in self.date_cols:
            default_date = self.impute_values.get(col, pd.Timestamp.now())
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors='coerce').fillna(default_date)
            else:
                parsed = pd.Series(pd.Timestamp(default_date), index=df.index)
                
            df[f"{col}_year"] = parsed.dt.year
            df[f"{col}_month"] = parsed.dt.month
            df[f"{col}_day"] = parsed.dt.day
            df[f"{col}_dayofweek"] = parsed.dt.dayofweek
            df[f"{col}_is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype(int)

            
    def save(self, filepath: str):
        """Persists the fitted preprocessor state using Joblib."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(self, filepath)
        
    @staticmethod
    def load(filepath: str) -> 'PreprocessingService':
        """Loads a persisted preprocessor state."""
        return joblib.load(filepath)
