from typing import Dict, Any, List

class ExplainabilityService:
    """
    Service to generate structured, machine-readable, and deterministic explanations
    for every analytical result produced by the Data Intelligence Engine without using LLMs.
    """
    
    def explain_result(self, analysis_type: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates structured explanation dictionary for the given analysis results.
        
        Args:
            analysis_type: The type of analysis (profiler, quality, kpi, stats, feature_eng, forecast, segment, anomaly)
            result_data: The output dictionary from the corresponding analytical service.
            
        Returns:
            Dict containing summary text, bullet-point insights, and key metrics.
        """
        analysis_type = str(analysis_type).lower().strip()
        
        if analysis_type == "profiler":
            return self._explain_profiler(result_data)
        elif analysis_type == "quality":
            return self._explain_quality(result_data)
        elif analysis_type == "kpi":
            return self._explain_kpi(result_data)
        elif analysis_type == "statistics" or analysis_type == "stats":
            return self._explain_stats(result_data)
        elif analysis_type == "feature_engineering" or analysis_type == "feature_eng":
            return self._explain_feature_eng(result_data)
        elif analysis_type == "forecasting" or analysis_type == "forecast":
            return self._explain_forecast(result_data)
        elif analysis_type == "segmentation" or analysis_type == "segment":
            return self._explain_segment(result_data)
        elif analysis_type == "anomaly":
            return self._explain_anomaly(result_data)
        else:
            return {
                "summary": "Unknown analysis type.",
                "insights": ["No explanation template registered for this analysis type."],
                "key_metrics": {}
            }
            
    def _explain_profiler(self, data: Dict[str, Any]) -> Dict[str, Any]:
        rows = data.get("total_rows", 0)
        cols = data.get("total_columns", 0)
        dups = data.get("duplicate_rows", 0)
        
        summary = f"Dataset profiled containing {rows} rows and {cols} columns. We detected {dups} fully duplicate rows."
        
        insights = []
        for col_name, col_prof in data.get("columns", {}).items():
            col_type = col_prof.get("type", "unknown")
            comp = col_prof.get("completeness", 0.0)
            card = col_prof.get("cardinality", 0)
            
            insight = f"Column '{col_name}' detected as {col_type} (completeness: {comp:.1f}%, cardinality: {card})."
            if "outliers_count" in col_prof and col_prof["outliers_count"] > 0:
                insight += f" Identified {col_prof['outliers_count']} outlier values."
            insights.append(insight)
            
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": {
                "total_rows": rows,
                "total_columns": cols,
                "duplicate_rows": dups
            }
        }
        
    def _explain_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        score = data.get("quality_score", 100)
        missing = data.get("missing_values", 0)
        dups = data.get("duplicate_rows", 0)
        incons = len(data.get("inconsistencies", {}))
        mixed = len(data.get("mixed_types", {}))
        
        summary = f"Data quality check generated a score of {score}/100. We identified {missing} missing values and {dups} duplicate rows."
        
        insights = []
        if score == 100:
            insights.append("Excellent! The dataset has no missing values, duplicates, mixed types, or casing inconsistencies.")
        else:
            if missing > 0:
                insights.append(f"Found {missing} missing cells needing imputation.")
            if dups > 0:
                insights.append(f"Found {dups} identical duplicate rows that should be removed.")
            if mixed > 0:
                insights.append(f"Mixed types detected across {mixed} columns, which can lead to parsing issues.")
            if incons > 0:
                insights.append(f"Inconsistent text formats (casing or spacing) found in {incons} columns.")
                
        recs = [rec.get("fix") for rec in data.get("recommendations", [])]
        
        return {
            "summary": summary,
            "insights": insights,
            "recommendations": recs,
            "key_metrics": {
                "quality_score": score,
                "missing_values": missing,
                "duplicate_rows": dups
            }
        }
        
    def _explain_kpi(self, data: Dict[str, Any]) -> Dict[str, Any]:
        std_kpi = data.get("standard_kpis", {})
        cust_kpi = data.get("custom_kpis", {})
        
        revenue = std_kpi.get("revenue")
        profit = std_kpi.get("profit")
        growth = std_kpi.get("growth")
        
        parts = []
        if revenue is not None:
            parts.append(f"Revenue computed to ${revenue:,.2f}")
        if profit is not None:
            parts.append(f"Profit computed to ${profit:,.2f}")
        if growth is not None:
            parts.append(f"Growth computed to {growth:.2f}% MoM")
            
        summary = "Computed KPIs: " + (", ".join(parts) if parts else "No standard columns matched for KPI computation.")
        
        insights = []
        for k, v in std_kpi.items():
            if v is not None:
                if k == "retention":
                    insights.append(f"Customer Retention Rate is {v:.2f}%.")
                elif k == "cac":
                    insights.append(f"Customer Acquisition Cost (CAC) is ${v:,.2f}.")
                elif k == "ltv":
                    insights.append(f"Customer Lifetime Value (LTV) is ${v:,.2f}.")
                elif k == "conversion_rate":
                    insights.append(f"Marketing/Sales Conversion Rate is {v:.2f}%.")
                    
        for name, val in cust_kpi.items():
            if isinstance(val, (int, float)):
                insights.append(f"Custom KPI '{name}' calculated to {val:,.2f}.")
            else:
                insights.append(f"Custom KPI '{name}' calculation returned code: {val}.")
                
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": {k: v for k, v in std_kpi.items() if v is not None}
        }
        
    def _explain_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        descriptive = data.get("descriptive", {})
        correlation = data.get("correlation", {}).get("pearson", {})
        
        summary = f"Statistical calculations completed for {len(descriptive)} numerical columns."
        
        insights = []
        # Describe general numeric spreads
        for col, stats_info in list(descriptive.items())[:3]: # limit to top 3
            insights.append(f"Column '{col}' ranges from {stats_info['min']:.2f} to {stats_info['max']:.2f} (mean: {stats_info['mean']:.2f}, std: {stats_info['std']:.2f}).")
            
        # Describe high correlations
        for col_a, row_corr in correlation.items():
            for col_b, val in row_corr.items():
                if col_a < col_b and abs(val) > 0.6: # avoid double counting & select high correlations
                    direction = "positive" if val > 0 else "negative"
                    strength = "strong" if abs(val) > 0.8 else "moderate"
                    insights.append(f"Found a {strength} {direction} correlation (r={val:.2f}) between '{col_a}' and '{col_b}'.")
                    
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": {}
        }
        
    def _explain_feature_eng(self, data: Dict[str, Any]) -> Dict[str, Any]:
        metadata = data.get("metadata", {})
        target = metadata.get("detected_target", "None")
        num_feats = len(metadata.get("numeric_features", []))
        cat_feats = len(metadata.get("categorical_features", []))
        
        summary = f"Feature engineering complete. Target column detected as '{target}'. Model-ready features: {num_feats} numeric (scaled) and {cat_feats} categorical (encoded)."
        
        insights = []
        if metadata.get("date_features_extracted"):
            insights.append(f"Extracted cyclical features from date columns: {', '.join(metadata['date_features_extracted'])}.")
        insights.append(f"Prepared {len(data.get('train_x', []))} training samples and {len(data.get('test_x', []))} testing samples.")
        
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": {
                "train_samples": len(data.get("train_x", [])),
                "test_samples": len(data.get("test_x", [])),
                "num_numeric_features": num_feats,
                "num_categorical_features": cat_feats
            }
        }
        
    def _explain_forecast(self, data: Dict[str, Any]) -> Dict[str, Any]:
        model = data.get("model_used", "ARIMA")
        timeline = data.get("timeline", [])
        metrics = data.get("metrics", {})
        
        # Calculate general trajectory
        forecast_pts = [p for p in timeline if p.get("forecast") is not None]
        history_pts = [p for p in timeline if p.get("actual") is not None]
        
        r2 = metrics.get("r_squared", 0.0)
        
        if forecast_pts and history_pts:
            start_f = forecast_pts[0]["forecast"]
            end_f = forecast_pts[-1]["forecast"]
            change = ((end_f - start_f) / start_f * 100.0) if start_f != 0 else 0.0
            direction = "an upward" if change > 0 else "a downward"
            summary = f"Forecasting using '{model}' indicates {direction} trend of {abs(change):.1f}% over the next {len(forecast_pts)} periods (ending at {end_f:,.2f})."
        else:
            summary = f"Forecasting model '{model}' fitted successfully."
            
        insights = [
            f"Forecast R-Squared (fit precision) score: {r2:.2f}.",
            f"Mean Absolute Error (MAE): ${metrics.get('mae', 0.0):,.2f}.",
            f"Root Mean Square Error (RMSE): ${metrics.get('rmse', 0.0):,.2f}."
        ]
        
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": metrics
        }
        
    def _explain_segment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        feats = data.get("features_used", [])
        summaries = data.get("summaries", {})
        
        summary = f"Dataset segmented into {len(summaries)} distinct cohorts based on features: {', '.join(feats)}."
        
        insights = []
        for cid, info in summaries.items():
            name = info.get("name")
            size = info.get("size")
            pct = info.get("percentage")
            char = info.get("characteristics")
            insights.append(f"Cohort '{name}' contains {size} rows ({pct:.1f}%): {char}")
            
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": {
                "num_clusters": len(summaries)
            }
        }
        
    def _explain_anomaly(self, data: Dict[str, Any]) -> Dict[str, Any]:
        total = data.get("total_anomalies_found", 0)
        feats = data.get("features_used", [])
        
        summary = f"Anomaly scanning across {len(feats)} features detected {total} outlier data points."
        
        insights = []
        anomalies = data.get("anomalies", [])
        for idx, anom in enumerate(anomalies[:5]): # limit to top 5 outliers
            insights.append(f"Outlier {idx+1} (Row index {anom['row_index']}, score: {anom['anomaly_score']:.2f}): {anom['explanation']}")
            
        return {
            "summary": summary,
            "insights": insights,
            "key_metrics": {
                "total_anomalies": total
            }
        }
