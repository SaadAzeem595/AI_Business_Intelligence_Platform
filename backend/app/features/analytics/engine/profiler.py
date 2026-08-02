import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class DataProfilerService:
    """
    Service to automatically profile datasets and extract column types, distribution characteristics,
    missing values, duplicate counts, cardinality, skewness, and outlier counts.
    """
    
    def profile_dataset(self, dataset_ref: str, conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, Any]:
        """
        Profiles a dataset and returns structured metadata.
        
        Args:
            dataset_ref: File path or view name.
            conn: Optional DuckDB connection.
            
        Returns:
            Dict containing detailed profile analysis.
        """
        df = load_dataset(dataset_ref, conn)
        total_rows = len(df)
        total_cols = len(df.columns)
        
        # Calculate duplicates
        duplicate_rows_count = int(df.duplicated().sum())
        
        columns_profile = {}
        for col in df.columns:
            series = df[col]
            missing_count = int(series.isna().sum())
            completeness = float((total_rows - missing_count) / total_rows * 100.0) if total_rows > 0 else 0.0
            cardinality = int(series.nunique())
            
            # Detect column types
            col_type = self._detect_column_type(series)
            
            profile = {
                "type": col_type,
                "missing_count": missing_count,
                "completeness": completeness,
                "cardinality": cardinality,
            }
            
            # If numeric, calculate distribution, skewness, outliers
            if col_type in ["numeric", "integer", "float"]:
                clean_series = series.dropna()
                if len(clean_series) > 0:
                    mean_val = float(clean_series.mean())
                    std_val = float(clean_series.std()) if len(clean_series) > 1 else 0.0
                    min_val = float(clean_series.min())
                    max_val = float(clean_series.max())
                    median_val = float(clean_series.median())
                    q25 = float(clean_series.quantile(0.25))
                    q75 = float(clean_series.quantile(0.75))
                    skewness = float(clean_series.skew()) if len(clean_series) > 2 else 0.0
                    
                    # Outliers detection via IQR
                    iqr = q75 - q25
                    lower_bound = q25 - 1.5 * iqr
                    upper_bound = q75 + 1.5 * iqr
                    outliers_mask = (clean_series < lower_bound) | (clean_series > upper_bound)
                    outliers_count = int(outliers_mask.sum())
                    
                    # Histogram calculation (limit bins to min(10, cardinality))
                    bins_cnt = max(1, min(10, cardinality))
                    counts, bin_edges = np.histogram(clean_series, bins=bins_cnt)
                    histogram = []
                    for i in range(len(counts)):
                        histogram.append({
                            "bin_start": float(bin_edges[i]),
                            "bin_end": float(bin_edges[i+1]),
                            "count": int(counts[i])
                        })
                    
                    profile.update({
                        "distribution": {
                            "mean": mean_val,
                            "std": std_val,
                            "min": min_val,
                            "max": max_val,
                            "median": median_val,
                            "q25": q25,
                            "q75": q75,
                            "histogram": histogram
                        },
                        "skewness": skewness,
                        "outliers_count": outliers_count
                    })
                else:
                    profile.update({
                        "distribution": None,
                        "skewness": 0.0,
                        "outliers_count": 0
                    })
            elif col_type in ["categorical", "boolean", "text"]:
                clean_series = series.dropna()
                if len(clean_series) > 0:
                    vc = clean_series.value_counts().head(10)
                    value_distribution = {str(k): int(v) for k, v in vc.items()}
                    profile.update({
                        "value_distribution": value_distribution
                    })
                else:
                    profile.update({
                        "value_distribution": {}
                    })
                
            columns_profile[str(col)] = profile
            
        return {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "duplicate_rows": duplicate_rows_count,
            "columns": columns_profile
        }
        
    def _detect_column_type(self, series: pd.Series) -> str:
        """
        Heuristic to detect data type of a pandas Series.
        """
        non_null = series.dropna()
        if len(non_null) == 0:
            return "empty"
            
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
            
        # Try datetime detection for object columns
        if pd.api.types.is_object_dtype(series):
            sample = non_null.head(50)
            try:
                # Exclude simple integers represented as strings (like "123")
                is_numeric_str = all(str(x).replace(".", "", 1).isdigit() for x in sample)
                if not is_numeric_str:
                    parsed = pd.to_datetime(sample, errors='coerce')
                    if parsed.notna().sum() / len(sample) > 0.8:
                        return "datetime"
            except Exception:
                pass
                
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
            
        if pd.api.types.is_integer_dtype(series):
            unique_vals = set(non_null.unique())
            if unique_vals.issubset({0, 1}) and len(unique_vals) > 0:
                return "boolean"
            return "integer"
            
        if pd.api.types.is_float_dtype(series):
            return "float"
            
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
            
        # If strings, distinguish between categorical and long text
        if len(non_null) > 0:
            unique_ratio = len(non_null.unique()) / len(non_null)
            if unique_ratio < 0.20 or len(non_null.unique()) < 50:
                return "categorical"
                
        return "text"
