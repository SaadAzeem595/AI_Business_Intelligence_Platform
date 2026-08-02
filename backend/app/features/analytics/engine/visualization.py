import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class VisualizationService:
    """
    Service to generate JSON-structured chart specifications (Line, Bar, Scatter,
    Heatmap, Pie, Histogram, Boxplot) from datasets to render in frontend.
    """
    
    def generate_spec(
        self, 
        dataset_ref: str, 
        chart_type: str, 
        x_col: str, 
        y_col: Optional[str] = None, 
        group_by: Optional[str] = None,
        conn: Optional[duckdb.DuckDBPyConnection] = None
    ) -> Dict[str, Any]:
        """
        Loads dataset and returns JSON chart specifications.
        """
        df = load_dataset(dataset_ref, conn)
        return self.get_chart_specification(df, chart_type, x_col, y_col, group_by)
        
    def get_chart_specification(
        self, 
        df: pd.DataFrame, 
        chart_type: str, 
        x_col: str, 
        y_col: Optional[str] = None, 
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates chart specification JSON based on DataFrame and columns.
        """
        chart_type = chart_type.lower().strip()
        
        if len(df) == 0:
            return {"chart_type": chart_type, "series": [], "xAxis": {}, "yAxis": {}, "title": "No Data"}
            
        if chart_type == "line":
            return self._build_line_spec(df, x_col, y_col, group_by)
        elif chart_type == "bar":
            return self._build_bar_spec(df, x_col, y_col, group_by)
        elif chart_type == "scatter":
            return self._build_scatter_spec(df, x_col, y_col, group_by)
        elif chart_type == "heatmap":
            return self._build_heatmap_spec(df)
        elif chart_type == "pie":
            return self._build_pie_spec(df, x_col, y_col)
        elif chart_type == "histogram":
            return self._build_histogram_spec(df, x_col)
        elif chart_type == "boxplot":
            return self._build_boxplot_spec(df, x_col, y_col)
        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")
            
    def _build_line_spec(self, df: pd.DataFrame, x_col: str, y_col: Optional[str], group_by: Optional[str]) -> Dict[str, Any]:
        if not y_col:
            raise ValueError("Line chart requires both x_col and y_col.")
            
        temp = df[[x_col, y_col] + ([group_by] if group_by else [])].dropna()
        temp = temp.sort_values(by=x_col)
        
        series = []
        x_values = []
        
        if group_by:
            groups = temp[group_by].unique()
            x_values = sorted(temp[x_col].unique().tolist())
            
            for g in groups:
                g_data = temp[temp[group_by] == g]
                agg = g_data.groupby(x_col)[y_col].mean()
                agg = agg.reindex(x_values, fill_value=None)
                series.append({
                    "name": str(g),
                    "data": [float(v) if pd.notna(v) else None for v in agg.values]
                })
        else:
            agg = temp.groupby(x_col)[y_col].mean()
            x_values = agg.index.tolist()
            series.append({
                "name": str(y_col),
                "data": [float(v) for v in agg.values]
            })
            
        return {
            "chart_type": "line",
            "title": f"Trend of {y_col} by {x_col}",
            "xAxis": {"type": "category", "data": [str(x) for x in x_values], "label": str(x_col)},
            "yAxis": {"type": "value", "label": str(y_col)},
            "series": series
        }
        
    def _build_bar_spec(self, df: pd.DataFrame, x_col: str, y_col: Optional[str], group_by: Optional[str]) -> Dict[str, Any]:
        series = []
        x_values = []
        
        if y_col:
            temp = df[[x_col, y_col] + ([group_by] if group_by else [])].dropna()
            if group_by:
                groups = temp[group_by].unique()
                x_values = sorted(temp[x_col].unique().tolist())
                for g in groups:
                    g_data = temp[temp[group_by] == g]
                    agg = g_data.groupby(x_col)[y_col].sum()
                    agg = agg.reindex(x_values, fill_value=0.0)
                    series.append({
                        "name": str(g),
                        "data": [float(v) for v in agg.values]
                    })
            else:
                agg = temp.groupby(x_col)[y_col].sum()
                x_values = agg.index.tolist()
                series.append({
                    "name": str(y_col),
                    "data": [float(v) for v in agg.values]
                })
            title = f"Sum of {y_col} by {x_col}"
            y_label = str(y_col)
        else:
            counts = df[x_col].value_counts()
            x_values = counts.index.tolist()
            series.append({
                "name": "Count",
                "data": [int(v) for v in counts.values]
            })
            title = f"Distribution of {x_col}"
            y_label = "Count"
            
        return {
            "chart_type": "bar",
            "title": title,
            "xAxis": {"type": "category", "data": [str(x) for x in x_values], "label": str(x_col)},
            "yAxis": {"type": "value", "label": y_label},
            "series": series
        }
        
    def _build_scatter_spec(self, df: pd.DataFrame, x_col: str, y_col: Optional[str], group_by: Optional[str]) -> Dict[str, Any]:
        if not y_col:
            raise ValueError("Scatter chart requires both x_col and y_col.")
            
        temp = df[[x_col, y_col] + ([group_by] if group_by else [])].dropna()
        series = []
        
        if group_by:
            groups = temp[group_by].unique()
            for g in groups:
                g_data = temp[temp[group_by] == g]
                pts = [[float(r[x_col]), float(r[y_col])] for _, r in g_data.iterrows()]
                series.append({
                    "name": str(g),
                    "data": pts
                })
        else:
            pts = [[float(r[x_col]), float(r[y_col])] for _, r in temp.iterrows()]
            series.append({
                "name": f"{x_col} vs {y_col}",
                "data": pts
            })
            
        return {
            "chart_type": "scatter",
            "title": f"Relationship between {x_col} and {y_col}",
            "xAxis": {"type": "value", "label": str(x_col)},
            "yAxis": {"type": "value", "label": str(y_col)},
            "series": series
        }
        
    def _build_heatmap_spec(self, df: pd.DataFrame) -> Dict[str, Any]:
        numeric_df = df.select_dtypes(include=[np.number]).dropna(how='all')
        if numeric_df.empty or len(numeric_df.columns) < 2:
            return {"chart_type": "heatmap", "series": [], "xAxis": {"data": []}, "yAxis": {"data": []}}
            
        corr = numeric_df.corr().fillna(0.0)
        cols = corr.columns.tolist()
        
        data = []
        for i in range(len(cols)):
            for j in range(len(cols)):
                data.append([i, j, float(corr.iloc[i, j])])
                
        return {
            "chart_type": "heatmap",
            "title": "Correlation Matrix Heatmap",
            "xAxis": {"type": "category", "data": [str(c) for c in cols]},
            "yAxis": {"type": "category", "data": [str(c) for c in cols]},
            "series": [{
                "name": "Correlation",
                "data": data
            }]
        }
        
    def _build_pie_spec(self, df: pd.DataFrame, x_col: str, y_col: Optional[str]) -> Dict[str, Any]:
        if y_col:
            agg = df.groupby(x_col)[y_col].sum().dropna()
            data = [{"name": str(k), "value": float(v)} for k, v in agg.items()]
            title = f"Contribution of {x_col} to {y_col}"
        else:
            counts = df[x_col].value_counts().dropna()
            data = [{"name": str(k), "value": int(v)} for k, v in counts.items()]
            title = f"Composition of {x_col}"
            
        return {
            "chart_type": "pie",
            "title": title,
            "series": [{
                "name": str(x_col),
                "data": data
            }]
        }
        
    def _build_histogram_spec(self, df: pd.DataFrame, x_col: str) -> Dict[str, Any]:
        clean_data = df[x_col].dropna()
        if len(clean_data) == 0:
            return {"chart_type": "histogram", "series": []}
            
        counts, bin_edges = np.histogram(clean_data, bins="auto")
        
        bin_labels = []
        for i in range(len(counts)):
            bin_labels.append(f"{bin_edges[i]:.2f} - {bin_edges[i+1]:.2f}")
            
        return {
            "chart_type": "bar",
            "title": f"Frequency Distribution of {x_col}",
            "xAxis": {"type": "category", "data": bin_labels, "label": "Intervals"},
            "yAxis": {"type": "value", "label": "Frequency"},
            "series": [{
                "name": "Frequency",
                "data": [int(c) for c in counts]
            }]
        }
        
    def _build_boxplot_spec(self, df: pd.DataFrame, x_col: str, y_col: Optional[str]) -> Dict[str, Any]:
        series = []
        x_categories = []
        
        if y_col:
            categories = df[x_col].dropna().unique()
            for cat in categories:
                cat_data = df[df[x_col] == cat][y_col].dropna()
                if len(cat_data) > 0:
                    summary = self._compute_boxplot_summary(cat_data)
                    series.append({
                        "name": str(cat),
                        "data": summary
                    })
                    x_categories.append(str(cat))
            title = f"Distribution of {y_col} by {x_col}"
            x_label = str(x_col)
            y_label = str(y_col)
        else:
            clean_data = df[x_col].dropna()
            if len(clean_data) > 0:
                summary = self._compute_boxplot_summary(clean_data)
                series.append({
                    "name": str(x_col),
                    "data": summary
                })
                x_categories.append(str(x_col))
            title = f"Boxplot of {x_col}"
            x_label = ""
            y_label = str(x_col)
            
        return {
            "chart_type": "boxplot",
            "title": title,
            "xAxis": {"type": "category", "data": x_categories, "label": x_label},
            "yAxis": {"type": "value", "label": y_label},
            "series": series
        }
        
    def _compute_boxplot_summary(self, series: pd.Series) -> Dict[str, float]:
        q25 = float(series.quantile(0.25))
        q50 = float(series.quantile(0.50))
        q75 = float(series.quantile(0.75))
        iqr = q75 - q25
        
        lower_whisker = max(float(series.min()), q25 - 1.5 * iqr)
        upper_whisker = min(float(series.max()), q75 + 1.5 * iqr)
        
        return {
            "min": lower_whisker,
            "q25": q25,
            "median": q50,
            "q75": q75,
            "max": upper_whisker
        }
