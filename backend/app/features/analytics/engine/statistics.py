import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class StatisticalAnalysisService:
    """
    Service for running statistical calculations (descriptive statistics,
    correlation, covariance, hypothesis testing, and trend analysis).
    """
    
    def get_statistics_summary(self, dataset_ref: str, conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, Any]:
        """
        Generates general descriptive statistics, correlation, and covariance matrices.
        
        Args:
            dataset_ref: File path or view name.
            conn: Optional DuckDB connection.
            
        Returns:
            Dict containing descriptive, correlation, and covariance summaries.
        """
        df = load_dataset(dataset_ref, conn)
        return {
            "descriptive": self.run_descriptive(df),
            "correlation": self.run_correlation(df),
            "covariance": self.run_covariance(df)
        }
        
    def run_descriptive(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes detailed descriptive statistics for all numeric columns.
        """
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        desc_stats = {}
        
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) > 0:
                desc_stats[str(col)] = {
                    "count": int(len(series)),
                    "mean": float(series.mean()),
                    "median": float(series.median()),
                    "std": float(series.std()) if len(series) > 1 else 0.0,
                    "var": float(series.var()) if len(series) > 1 else 0.0,
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "range": float(series.max() - series.min()),
                    "q25": float(series.quantile(0.25)),
                    "q50": float(series.quantile(0.50)),
                    "q75": float(series.quantile(0.75)),
                    "skewness": float(series.skew()) if len(series) > 2 else 0.0,
                    "kurtosis": float(series.kurtosis()) if len(series) > 3 else 0.0,
                }
        return desc_stats
        
    def run_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes Pearson and Spearman correlation matrices for numeric columns.
        """
        numeric_df = df.select_dtypes(include=[np.number]).dropna(how='all')
        if numeric_df.empty or len(numeric_df.columns) < 2:
            return {"pearson": {}, "spearman": {}}
            
        # Pearson
        pearson_corr = numeric_df.corr(method='pearson').fillna(0.0).to_dict()
        # Spearman
        spearman_corr = numeric_df.corr(method='spearman').fillna(0.0).to_dict()
        
        # Ensure all keys are strings
        p_clean = {str(k): {str(ik): float(iv) for ik, iv in v.items()} for k, v in pearson_corr.items()}
        s_clean = {str(k): {str(ik): float(iv) for ik, iv in v.items()} for k, v in spearman_corr.items()}
        
        return {
            "pearson": p_clean,
            "spearman": s_clean
        }
        
    def run_covariance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes the covariance matrix for numeric columns.
        """
        numeric_df = df.select_dtypes(include=[np.number]).dropna(how='all')
        if numeric_df.empty or len(numeric_df.columns) < 2:
            return {}
        cov_matrix = numeric_df.cov().fillna(0.0).to_dict()
        
        cov_clean = {str(k): {str(ik): float(iv) for ik, iv in v.items()} for k, v in cov_matrix.items()}
        return cov_clean
        
    def run_hypothesis_test(self, df: pd.DataFrame, test_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs specific statistical hypothesis tests.
        
        Supported tests:
        - ttest_ind: Independent two-sample t-test (params: col_a, col_b)
        - ttest_rel: Paired two-sample t-test (params: col_a, col_b)
        - chi2_contingency: Chi-Square test of independence (params: col_a, col_b)
        - anova: One-way ANOVA test (params: group_col, value_col)
        - normality: Shapiro-Wilk normality test (params: col)
        """
        test_name = test_name.lower().strip()
        
        if test_name == "ttest_ind":
            col_a = params.get("col_a")
            col_b = params.get("col_b")
            series_a = df[col_a].dropna()
            series_b = df[col_b].dropna()
            stat, p_val = stats.ttest_ind(series_a, series_b, equal_var=False)
            return {
                "test": "Independent T-Test",
                "statistic": float(stat),
                "p_value": float(p_val),
                "significant": bool(p_val < 0.05),
                "mean_a": float(series_a.mean()) if len(series_a) > 0 else 0.0,
                "mean_b": float(series_b.mean()) if len(series_b) > 0 else 0.0,
                "details": f"Comparing means of '{col_a}' and '{col_b}'. Null Hypothesis: means are equal."
            }
            
        elif test_name == "ttest_rel":
            col_a = params.get("col_a")
            col_b = params.get("col_b")
            temp = df[[col_a, col_b]].dropna()
            if len(temp) == 0:
                raise ValueError("No common non-null values between paired columns.")
            stat, p_val = stats.ttest_rel(temp[col_a], temp[col_b])
            return {
                "test": "Paired T-Test",
                "statistic": float(stat),
                "p_value": float(p_val),
                "significant": bool(p_val < 0.05),
                "mean_difference": float((temp[col_a] - temp[col_b]).mean()),
                "details": f"Comparing paired values of '{col_a}' and '{col_b}'. Null Hypothesis: mean difference is 0."
            }
            
        elif test_name == "chi2_contingency":
            col_a = params.get("col_a")
            col_b = params.get("col_b")
            contingency_table = pd.crosstab(df[col_a], df[col_b])
            if contingency_table.size == 0:
                raise ValueError("Contingency table is empty.")
            stat, p_val, dof, expected = stats.chi2_contingency(contingency_table)
            return {
                "test": "Chi-Square Test of Independence",
                "statistic": float(stat),
                "p_value": float(p_val),
                "degrees_of_freedom": int(dof),
                "significant": bool(p_val < 0.05),
                "details": f"Testing independence between '{col_a}' and '{col_b}'. Null Hypothesis: variables are independent."
            }
            
        elif test_name == "anova":
            group_col = params.get("group_col")
            value_col = params.get("value_col")
            
            groups = df[group_col].dropna().unique()
            if len(groups) < 2:
                raise ValueError("ANOVA requires at least two groups.")
            group_data = [df[df[group_col] == g][value_col].dropna() for g in groups]
            
            stat, p_val = stats.f_oneway(*group_data)
            return {
                "test": "One-Way ANOVA",
                "statistic": float(stat),
                "p_value": float(p_val),
                "significant": bool(p_val < 0.05),
                "groups_compared": list(map(str, groups)),
                "details": f"Comparing means of '{value_col}' across categories in '{group_col}'. Null Hypothesis: all group means are equal."
            }
            
        elif test_name == "normality":
            col = params.get("col")
            series = df[col].dropna()
            if len(series) < 3:
                raise ValueError("Normality test requires at least 3 values.")
            if len(series) > 5000:
                series = series.sample(5000, random_state=42)
            stat, p_val = stats.shapiro(series)
            return {
                "test": "Shapiro-Wilk Normality Test",
                "statistic": float(stat),
                "p_value": float(p_val),
                "significant_departure": bool(p_val < 0.05),
                "is_normal": bool(p_val >= 0.05),
                "details": f"Testing normality for '{col}'. Null Hypothesis: data is normally distributed."
            }
            
        else:
            raise ValueError(f"Unsupported hypothesis test: {test_name}")
            
    def run_trend_analysis(self, df: pd.DataFrame, x_col: str, y_col: str) -> Dict[str, Any]:
        """
        Runs simple linear regression to identify trends of Y versus X.
        """
        temp = df[[x_col, y_col]].dropna()
        if len(temp) < 2:
            return {"slope": 0.0, "intercept": 0.0, "p_value": 1.0, "r_squared": 0.0, "direction": "No Trend"}
            
        x_data = temp[x_col]
        if pd.api.types.is_datetime64_any_dtype(x_data) or x_data.dtype == object:
            try:
                x_numeric = pd.to_datetime(x_data).astype(np.int64) // 10**9
            except Exception:
                x_numeric = np.arange(len(temp))
        else:
            x_numeric = x_data.astype(float)
            
        y_numeric = temp[y_col].astype(float)
        
        # Fit OLS model
        X = sm.add_constant(x_numeric)
        model = sm.OLS(y_numeric, X).fit()
        
        slope = float(model.params.iloc[1]) if len(model.params) > 1 else 0.0
        intercept = float(model.params.iloc[0])
        p_val = float(model.pvalues.iloc[1]) if len(model.pvalues) > 1 else 1.0
        r_sq = float(model.rsquared)
        
        direction = "No Trend"
        if p_val < 0.05:
            direction = "Upward" if slope > 0 else "Downward"
            
        return {
            "slope": slope,
            "intercept": intercept,
            "p_value": p_val,
            "r_squared": r_sq,
            "direction": direction,
            "details": f"Linear trend analysis of '{y_col}' on '{x_col}'."
        }
