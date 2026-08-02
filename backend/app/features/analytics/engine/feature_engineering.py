import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class FeatureEngineeringService:
    """
    Service to automate feature engineering operations, including categorical encoding,
    numeric scaling, date extraction, automatic target detection, and generating ML-ready datasets.
    """
    
    def process_dataset(
        self, 
        dataset_ref: str, 
        conn: Optional[duckdb.DuckDBPyConnection] = None, 
        target_col: Optional[str] = None,
        scaling_method: str = "standard", 
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Loads the dataset and processes it.
        """
        df = load_dataset(dataset_ref, conn)
        return self.engineer_features(df, target_col, scaling_method, test_size)
        
    def engineer_features(
        self, 
        df: pd.DataFrame, 
        target_col: Optional[str] = None,
        scaling_method: str = "standard", 
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes feature engineering pipeline.
        """
        if len(df) == 0:
            return {
                "train_x": [], "test_x": [], "train_y": [], "test_y": [],
                "metadata": {}
            }
            
        temp_df = df.copy()
        
        # 1. Handle date columns: extract date features
        date_cols = []
        for col in temp_df.columns:
            # Check if column dtype is datetime or column name indicates a date/time
            if pd.api.types.is_datetime64_any_dtype(temp_df[col]) or any(x in str(col).lower() for x in ['date', 'timestamp', 'time']):
                try:
                    parsed_dates = pd.to_datetime(temp_df[col], errors='coerce')
                    if parsed_dates.notna().sum() > 0:
                        # Impute dates with median if missing
                        median_date = parsed_dates.dropna().median()
                        parsed_dates = parsed_dates.fillna(median_date)
                        
                        temp_df[f"{col}_year"] = parsed_dates.dt.year
                        temp_df[f"{col}_month"] = parsed_dates.dt.month
                        temp_df[f"{col}_day"] = parsed_dates.dt.day
                        temp_df[f"{col}_dayofweek"] = parsed_dates.dt.dayofweek
                        temp_df[f"{col}_is_weekend"] = parsed_dates.dt.dayofweek.isin([5, 6]).astype(int)
                        
                        date_cols.append(col)
                except Exception:
                    pass
                    
        # Drop original date columns
        temp_df = temp_df.drop(columns=date_cols)
        
        # Fill missing values
        for col in temp_df.columns:
            series = temp_df[col]
            if series.isna().sum() > 0:
                if pd.api.types.is_numeric_dtype(series):
                    temp_df[col] = series.fillna(series.median() if len(series.dropna()) > 0 else 0.0)
                else:
                    mode_vals = series.mode()
                    mode_val = mode_vals.iloc[0] if len(mode_vals) > 0 else "unknown"
                    temp_df[col] = series.fillna(mode_val)
                    
        # 2. Target Column Detection
        if not target_col:
            target_col = self._detect_target_col(temp_df)
            
        # 3. Separate Features and Target
        numeric_cols = []
        cat_cols = []
        
        for col in temp_df.columns:
            if col == target_col:
                continue
            if pd.api.types.is_numeric_dtype(temp_df[col]):
                numeric_cols.append(col)
            else:
                cat_cols.append(col)
                
        feature_metadata = {
            "original_columns": list(df.columns),
            "date_features_extracted": [str(c) for c in date_cols],
            "detected_target": target_col,
            "numeric_features": [str(c) for c in numeric_cols],
            "categorical_features": [str(c) for c in cat_cols],
            "encodings": {},
            "scaling": {}
        }
        
        # 4. Encode Categories
        for col in cat_cols:
            le = LabelEncoder()
            temp_df[col] = le.fit_transform(temp_df[col].astype(str))
            feature_metadata["encodings"][str(col)] = {str(class_name): int(idx) for idx, class_name in enumerate(le.classes_)}
            
        # 5. Scale numeric columns
        if len(numeric_cols) > 0:
            if scaling_method == "standard":
                scaler = StandardScaler()
                temp_df[numeric_cols] = scaler.fit_transform(temp_df[numeric_cols])
                for idx, col in enumerate(numeric_cols):
                    feature_metadata["scaling"][str(col)] = {
                        "method": "standard",
                        "mean": float(scaler.mean_[idx]),
                        "scale": float(scaler.scale_[idx])
                    }
            else:
                scaler = MinMaxScaler()
                temp_df[numeric_cols] = scaler.fit_transform(temp_df[numeric_cols])
                for idx, col in enumerate(numeric_cols):
                    feature_metadata["scaling"][str(col)] = {
                        "method": "minmax",
                        "min": float(scaler.data_min_[idx]),
                        "scale": float(scaler.scale_[idx])
                    }
                
        # 6. Generate ML-ready datasets (train-test split)
        X = temp_df.drop(columns=[target_col]) if target_col in temp_df.columns else temp_df
        
        if target_col in temp_df.columns:
            y = temp_df[target_col]
            if not pd.api.types.is_numeric_dtype(y):
                le_target = LabelEncoder()
                y = le_target.fit_transform(y.astype(str))
                feature_metadata["target_encoding"] = {str(class_name): int(idx) for idx, class_name in enumerate(le_target.classes_)}
            else:
                y = y.values
                
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
            
            return {
                "train_x": X_train.to_dict(orient="records"),
                "test_x": X_test.to_dict(orient="records"),
                "train_y": y_train.tolist(),
                "test_y": y_test.tolist(),
                "metadata": feature_metadata
            }
        else:
            X_train, X_test = train_test_split(X, test_size=test_size, random_state=42)
            return {
                "train_x": X_train.to_dict(orient="records"),
                "test_x": X_test.to_dict(orient="records"),
                "train_y": [],
                "test_y": [],
                "metadata": feature_metadata
            }
            
    def _detect_target_col(self, df: pd.DataFrame) -> str:
        """
        Detects target column using name heuristics and column location.
        """
        target_synonyms = ['target', 'label', 'churn', 'class', 'status', 'y', 'clicked', 'purchased', 'converted', 'revenue_group']
        for syn in target_synonyms:
            for col in df.columns:
                if str(col).lower().strip() == syn:
                    return col
                    
        for col in df.columns:
            if any(str(col).lower().endswith(syn) for syn in ['_target', '_label', '_class', '_churn']):
                return col
                
        return df.columns[-1]
