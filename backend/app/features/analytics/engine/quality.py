import pandas as pd
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class DataQualityService:
    """
    Service to assess data quality, compute cleanliness scores, identify inconsistent values,
    invalid dates, mixed types, duplicate rows, missing values, and recommend fixes.
    """
    
    def assess_quality(self, dataset_ref: str, conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, Any]:
        """
        Assesses data quality metrics of a dataset.
        
        Args:
            dataset_ref: File path or view name.
            conn: Optional DuckDB connection.
            
        Returns:
            Dict containing detailed data quality metrics and recommendations.
        """
        df = load_dataset(dataset_ref, conn)
        total_rows = len(df)
        total_cols = len(df.columns)
        total_cells = total_rows * total_cols
        
        if total_cells == 0:
            return {
                "quality_score": 100,
                "missing_values": 0,
                "duplicate_rows": 0,
                "inconsistencies": {},
                "mixed_types": {},
                "invalid_dates": {},
                "recommendations": []
            }
            
        # Detect missing values
        missing_by_col = df.isna().sum().to_dict()
        total_missing = sum(missing_by_col.values())
        missing_percentage = (total_missing / total_cells) * 100.0
        
        # Detect duplicate rows
        duplicate_rows = int(df.duplicated().sum())
        duplicate_percentage = (duplicate_rows / total_rows * 100.0) if total_rows > 0 else 0.0
        
        inconsistencies = {}
        mixed_types = {}
        invalid_dates = {}
        recommendations = []
        
        for col in df.columns:
            series = df[col]
            non_null = series.dropna()
            
            # Detect mixed types
            types = non_null.map(type).unique()
            if len(types) > 1:
                mixed_types[str(col)] = [t.__name__ for t in types]
                recommendations.append({
                    "column": str(col),
                    "issue": "Mixed data types detected",
                    "details": f"Contains multiple python types: {', '.join([t.__name__ for t in types])}",
                    "fix": f"Cast column '{col}' to a single type (e.g. string or numeric)."
                })
                
            # Missing value recommendation
            col_missing = int(missing_by_col[col])
            if col_missing > 0:
                rec_fix = f"Impute missing values in '{col}' using the median for numerical data, or mode for categorical data."
                if pd.api.types.is_numeric_dtype(series):
                    median_val = non_null.median() if len(non_null) > 0 else 0.0
                    rec_fix = f"Fill the {col_missing} missing values in '{col}' with its median value ({median_val:.2f})."
                elif pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                    if len(non_null) > 0:
                        mode_vals = non_null.mode()
                        mode_val = mode_vals[0] if len(mode_vals) > 0 else "unknown"
                        rec_fix = f"Fill the {col_missing} missing values in '{col}' with its most frequent category ('{mode_val}')."
                recommendations.append({
                    "column": str(col),
                    "issue": f"{col_missing} missing values",
                    "details": f"{col_missing} cells are empty ({col_missing / total_rows * 100.0:.1f}% missing)",
                    "fix": rec_fix
                })
                
            # If string-like, detect inconsistent values
            if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
                str_series = non_null.astype(str)
                
                # Check for whitespace inconsistencies
                has_whitespace = str_series.str.strip().ne(str_series).any()
                
                # Check capitalization inconsistencies
                lowercased = str_series.str.lower()
                unique_original = str_series.unique()
                unique_lower = lowercased.unique()
                has_casing_issue = len(unique_original) > len(unique_lower)
                
                col_inconsistencies = []
                if has_whitespace:
                    col_inconsistencies.append("leading/trailing whitespace")
                    recommendations.append({
                        "column": str(col),
                        "issue": "Leading or trailing whitespaces",
                        "details": "Some text values contain leading/trailing whitespaces.",
                        "fix": f"Strip whitespaces from values in column '{col}'."
                    })
                if has_casing_issue:
                    col_inconsistencies.append("mixed capitalization casing")
                    recommendations.append({
                        "column": str(col),
                        "issue": "Inconsistent casing in category names",
                        "details": "Found same word written in multiple cases.",
                        "fix": f"Standardize text casing in '{col}' to lowercase or uppercase."
                    })
                    
                if col_inconsistencies:
                    inconsistencies[str(col)] = col_inconsistencies
                    
                # Try to detect invalid dates if column is likely a date column
                if any(x in str(col).lower() for x in ['date', 'time', 'created', 'updated']):
                    parsed = pd.to_datetime(str_series, errors='coerce')
                    unparseable_cnt = int(parsed.isna().sum())
                    if unparseable_cnt > 0:
                        invalid_dates[str(col)] = unparseable_cnt
                        recommendations.append({
                            "column": str(col),
                            "issue": "Invalid date strings",
                            "details": f"{unparseable_cnt} values in this date column could not be parsed.",
                            "fix": f"Correct or remove the {unparseable_cnt} unparseable date values in '{col}'."
                        })
                        
        # Duplicate row recommendation
        if duplicate_rows > 0:
            recommendations.append({
                "column": "Multiple",
                "issue": f"{duplicate_rows} duplicate rows",
                "details": f"{duplicate_rows} rows have identical values across all columns.",
                "fix": "Remove the duplicate rows."
            })
            
        # Composite Quality Score calculation
        score_deductions = 0.0
        score_deductions += missing_percentage * 1.0
        score_deductions += duplicate_percentage * 2.0
        score_deductions += len(mixed_types) * 10.0
        score_deductions += len(inconsistencies) * 5.0
        score_deductions += len(invalid_dates) * 5.0
        
        quality_score = max(0, min(100, int(100 - score_deductions)))
        
        return {
            "quality_score": quality_score,
            "missing_values": total_missing,
            "duplicate_rows": duplicate_rows,
            "inconsistencies": inconsistencies,
            "mixed_types": mixed_types,
            "invalid_dates": invalid_dates,
            "recommendations": recommendations
        }
