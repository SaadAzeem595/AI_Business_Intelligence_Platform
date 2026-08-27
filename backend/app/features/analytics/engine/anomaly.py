import pandas as pd
import numpy as np
from scipy.stats import norm
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset
from app.features.analytics.schemas import (
    ProjectAnomalyResponse,
    AnomalyTimelinePointDetailed,
    AnomalyLogDetailed
)

class AnomalyDetectionService:
    """
    Service to perform anomaly detection using Z-Score, IQR, Isolation Forest, and LOF
    and generate feature-level explanations for outliers.
    """

    def run_dataset_anomaly_detection(
        self,
        df: pd.DataFrame,
        timestamp_column: str,
        metric_column: str,
        detection_method: str = "zscore",
        sensitivity: float = 0.05,
        dataset_name: str = "Dataset",
        dataset_id: Optional[str] = None,
        project_id: Optional[str] = None,
        display_metric_name: Optional[str] = None,
    ) -> ProjectAnomalyResponse:
        """
        Production-grade anomaly detection on time-series dataset.
        Validates columns, parses timestamps, handles invalid/missing values,
        executes chosen detection algorithm, calculates boundaries & severities,
        and generates context-aware business recommendations.
        """
        if df is None or df.empty:
            return ProjectAnomalyResponse(
                status="error",
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                message="Dataset is empty or invalid."
            )

        if timestamp_column not in df.columns:
            raise ValueError(f"Timestamp column '{timestamp_column}' not found in dataset.")

        if metric_column not in df.columns:
            raise ValueError(f"Metric column '{metric_column}' not found in dataset.")

        # Clean & validate numeric metric
        clean_df = df[[timestamp_column, metric_column]].copy()
        clean_df[metric_column] = pd.to_numeric(clean_df[metric_column], errors="coerce")
        
        # Parse timestamp column
        try:
            clean_df[timestamp_column] = pd.to_datetime(clean_df[timestamp_column], errors="coerce", format="mixed")
        except Exception:
            clean_df[timestamp_column] = pd.to_datetime(clean_df[timestamp_column], errors="coerce")

        # Drop NaN values
        clean_df = clean_df.dropna(subset=[timestamp_column, metric_column]).copy()
        if clean_df.empty:
            return ProjectAnomalyResponse(
                status="error",
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                timestamp_column=timestamp_column,
                metric_column=metric_column,
                message="No valid observations found after parsing timestamps and metric numeric values."
            )

        # Sort chronologically by timestamp
        clean_df = clean_df.sort_values(by=timestamp_column).reset_index(drop=True)

        values = clean_df[metric_column].values
        timestamps = clean_df[timestamp_column]
        total_obs = len(values)

        min_val = float(np.min(values))
        max_val = float(np.max(values))
        mean_val = float(np.mean(values))
        std_val = float(np.std(values)) if np.std(values) > 0 else 1.0

        # Method Execution: Z-Score, IQR, or Isolation Forest
        method = detection_method.lower().strip()
        sens = min(0.20, max(0.01, sensitivity))
        sens_pct = round(sens * 100.0, 1)

        is_anomaly_mask = np.zeros(total_obs, dtype=bool)
        anomaly_scores = np.zeros(total_obs, dtype=float)

        metric_display = display_metric_name or metric_column
        is_currency = any(kw in metric_display.lower() for kw in ["revenue", "price", "sales", "cost", "profit", "amount", "spend", "value", "freight"])

        def format_val(val: float) -> str:
            if is_currency:
                return f"${val:,.2f}" if abs(val) < 1000 else f"${val:,.0f}"
            return f"{val:,.2f}" if abs(val) < 100 else f"{val:,.0f}"

        if method in ["zscore", "z-score"]:
            # Mathematical Z-Score quantiles: Z_thresh = norm.ppf(1 - sens/2)
            z_thresh = float(norm.ppf(1.0 - (sens / 2.0)))
            z_scores = np.abs((values - mean_val) / std_val)
            anomaly_scores = z_scores
            is_anomaly_mask = z_scores > z_thresh

            upper_limit = float(mean_val + z_thresh * std_val)
            lower_limit = float(mean_val - z_thresh * std_val)
            sensitivity_explanation = (
                f"Z-Score evaluates standard normal distribution quantiles. At sensitivity α={sens_pct}%, "
                f"the critical threshold is Z={z_thresh:.2f} standard deviations from baseline average (Mean={format_val(mean_val)}, Std Dev={format_val(std_val)}). "
                f"Statistical boundary bounds are set at [{format_val(lower_limit)}, {format_val(upper_limit)}]."
            )

        elif method in ["iqr", "interquartile"]:
            q1 = float(np.percentile(values, 25))
            q3 = float(np.percentile(values, 75))
            iqr = q3 - q1 if (q3 - q1) > 0 else 1.0

            # Mathematical Tukey fence multiplier derived from sensitivity
            iqr_mult = float(max(1.0, min(3.0, 1.5 * np.sqrt(0.05 / sens))))
            upper_limit = float(q3 + iqr_mult * iqr)
            lower_limit = float(q1 - iqr_mult * iqr)

            is_anomaly_mask = (values > upper_limit) | (values < lower_limit)
            anomaly_scores = np.where(
                values > upper_limit, 
                (values - upper_limit) / iqr, 
                np.where(values < lower_limit, (lower_limit - values) / iqr, 0.0)
            )
            sensitivity_explanation = (
                f"IQR uses Tukey's boxplot fence rule. At sensitivity α={sens_pct}%, "
                f"the fence multiplier is k={iqr_mult:.2f} (Q1={format_val(q1)}, Q3={format_val(q3)}, IQR={format_val(iqr)}). "
                f"Outlier fences are calculated as Q1 - {iqr_mult:.2f}×IQR ({format_val(lower_limit)}) and Q3 + {iqr_mult:.2f}×IQR ({format_val(upper_limit)})."
            )

        elif method in ["iforest", "isolation_forest"]:
            scaler = StandardScaler()
            scaled_vals = scaler.fit_transform(values.reshape(-1, 1))

            model = IsolationForest(contamination=sens, random_state=42)
            preds = model.fit_predict(scaled_vals)
            dec_scores = -model.decision_function(scaled_vals)

            is_anomaly_mask = preds == -1
            anomaly_scores = dec_scores

            # Empirical upper & lower boundary estimation from non-anomalous inliers
            inliers = values[preds == 1]
            if len(inliers) > 0:
                upper_limit = float(np.max(inliers))
                lower_limit = float(np.min(inliers))
            else:
                upper_limit = float(mean_val + 2.0 * std_val)
                lower_limit = float(mean_val - 2.0 * std_val)

            sensitivity_explanation = (
                f"Isolation Forest isolates anomalies using randomized decision trees with contamination rate α={sens_pct}%. "
                f"Empirical non-outlier decision boundaries define the expected operational bounds as [{format_val(lower_limit)}, {format_val(upper_limit)}]."
            )
        else:
            raise ValueError(f"Unsupported anomaly detection algorithm: '{detection_method}'. Choose 'zscore', 'iqr', or 'iforest'.")

        timeline: List[AnomalyTimelinePointDetailed] = []
        logs: List[AnomalyLogDetailed] = []
        anomalies_count = 0
        severities_found = []

        for idx in range(total_obs):
            val = float(values[idx])
            ts = timestamps.iloc[idx]
            ts_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)

            is_anom = bool(is_anomaly_mask[idx])
            score = float(anomaly_scores[idx])

            # Determine severity level
            if not is_anom:
                sev = "None"
            else:
                anomalies_count += 1
                z_diff = (val - mean_val) / std_val
                abs_z = abs(z_diff)

                if method in ["zscore", "z-score"]:
                    if abs_z > 3.5:
                        sev = "High"
                    elif abs_z > 2.5:
                        sev = "Medium"
                    else:
                        sev = "Low"
                else:
                    if score > 2.0 or val > upper_limit * 1.3 or val < lower_limit * 0.7:
                        sev = "High"
                    elif score > 1.0 or val > upper_limit * 1.1 or val < lower_limit * 0.9:
                        sev = "Medium"
                    else:
                        sev = "Low"

                severities_found.append(sev)

                bound_ref = upper_limit if val > upper_limit else lower_limit
                dev_pct = float(((val - mean_val) / abs(mean_val)) * 100.0) if mean_val != 0 else 0.0
                sign_str = "+" if dev_pct >= 0 else ""
                dev_str = f"{'+' if z_diff > 0 else ''}{z_diff:.2f} Std Dev ({sign_str}{dev_pct:.1f}% vs mean)"

                if val > upper_limit:
                    explanation = (
                        f"On {ts_str}, '{metric_display}' in dataset '{dataset_name}' spiked to {format_val(val)}, "
                        f"exceeding the upper threshold of {format_val(upper_limit)} (+{dev_pct:.1f}% above baseline average {format_val(mean_val)})."
                    )
                else:
                    explanation = (
                        f"On {ts_str}, '{metric_display}' in dataset '{dataset_name}' dropped to {format_val(val)}, "
                        f"falling below the lower threshold of {format_val(lower_limit)} ({dev_pct:.1f}% below baseline average {format_val(mean_val)})."
                    )

                logs.append(
                    AnomalyLogDetailed(
                        id=f"ANOM-{anomalies_count:03d}",
                        timestamp=ts_str,
                        metric=metric_display,
                        value=round(val, 2),
                        value_formatted=format_val(val),
                        score=round(score, 2),
                        deviation=dev_str,
                        severity=sev,
                        status="Unresolved",
                        explanation=explanation,
                        threshold=round(bound_ref, 2),
                        threshold_formatted=format_val(bound_ref),
                        expected_value=round(mean_val, 2),
                        expected_value_formatted=format_val(mean_val),
                        deviation_pct=round(dev_pct, 2)
                    )
                )

            timeline.append(
                AnomalyTimelinePointDetailed(
                    timestamp=ts_str,
                    value=round(val, 2),
                    upper_limit=round(upper_limit, 2),
                    lower_limit=round(lower_limit, 2),
                    is_anomaly=is_anom,
                    anomaly_score=round(score, 2),
                    severity=sev
                )
            )

        # Sort logs by severity (High > Medium > Low) then score
        sev_rank = {"High": 3, "Medium": 2, "Low": 1, "None": 0}
        logs = sorted(logs, key=lambda x: (sev_rank.get(x.severity, 0), x.score), reverse=True)

        highest_sev = "None"
        if "High" in severities_found:
            highest_sev = "High"
        elif "Medium" in severities_found:
            highest_sev = "Medium"
        elif "Low" in severities_found:
            highest_sev = "Low"

        anomaly_rate = round((anomalies_count / total_obs) * 100.0, 2) if total_obs > 0 else 0.0

        # Business Impact & Actionable Recommendations synthesis strictly grounded in dataset findings
        impact_insights = []
        recommendations = []

        start_date = timestamps.iloc[0].strftime("%Y-%m-%d") if hasattr(timestamps.iloc[0], "strftime") else str(timestamps.iloc[0])
        end_date = timestamps.iloc[-1].strftime("%Y-%m-%d") if hasattr(timestamps.iloc[-1], "strftime") else str(timestamps.iloc[-1])

        if anomalies_count > 0:
            top_anom = logs[0]
            impact_insights.append(
                f"Identified {anomalies_count} anomaly observation(s) out of {total_obs} data points ({anomaly_rate}% anomaly rate) in dataset '{dataset_name}' between {start_date} and {end_date}."
            )
            impact_insights.append(
                f"Highest severity outlier recorded on {top_anom.timestamp} where '{metric_display}' reached {top_anom.value_formatted} ({top_anom.deviation})."
            )
            impact_insights.append(
                f"Baseline distribution for '{metric_display}' has a mean of {format_val(mean_val)} and standard deviation of {format_val(std_val)} (Observed Range: {format_val(min_val)} to {format_val(max_val)})."
            )
            impact_insights.append(sensitivity_explanation)

            # Generate dynamic dataset-specific recommendations from actual findings
            # 1. Top peak anomaly action
            recommendations.append(
                f"Audit operational data for '{metric_display}' around {top_anom.timestamp} where value peaked at {top_anom.value_formatted} ({top_anom.deviation}) to confirm whether this reflects authentic volume or a data pipeline anomaly."
            )

            # 2. Check if low dips exist
            low_dips = [l for l in logs if l.value < lower_limit]
            if low_dips:
                worst_dip = min(low_dips, key=lambda x: x.value)
                recommendations.append(
                    f"Investigate the low outlier on {worst_dip.timestamp} where '{metric_display}' dropped to {worst_dip.value_formatted} ({worst_dip.deviation_pct:.1f}% below average), checking for potential service outage or missing logs."
                )

            # 3. Alerting recommendation with exact bounds
            recommendations.append(
                f"Configure automated monitoring alerts for '{metric_display}' whenever daily values breach upper boundary ({format_val(upper_limit)}) or lower boundary ({format_val(lower_limit)})."
            )

            # 4. Anomaly rate recommendation
            if anomaly_rate > 10.0:
                recommendations.append(
                    f"High anomaly rate of {anomaly_rate}% detected across {total_obs} observations. Consider reducing sensitivity below {sens_pct}% or applying rolling average aggregation to smooth series variance."
                )
        else:
            impact_insights.append(
                f"Analyzed {total_obs} observations for '{metric_display}' in dataset '{dataset_name}' across the time series from {start_date} to {end_date}."
            )
            impact_insights.append(
                f"Observed values ranged from a minimum of {format_val(min_val)} to a maximum of {format_val(max_val)} (Mean: {format_val(mean_val)}, Std Dev: {format_val(std_val)})."
            )
            impact_insights.append(
                f"Calculated statistical bounds for {detection_method.upper()}: Lower Limit = {format_val(lower_limit)}, Upper Limit = {format_val(upper_limit)}."
            )
            impact_insights.append(
                f"Zero anomalies detected (0.00% anomaly rate). All {total_obs} observations fell strictly within the calculated statistical boundaries [{format_val(lower_limit)}, {format_val(upper_limit)}]."
            )
            impact_insights.append(sensitivity_explanation)

            recommendations.append(
                f"Metric distribution for '{metric_display}' in '{dataset_name}' is statistically stable across all {total_obs} observations within expected bounds [{format_val(lower_limit)}, {format_val(upper_limit)}]."
            )
            recommendations.append(
                f"To capture subtle variance shifts in '{metric_display}', consider increasing algorithm sensitivity above {sens_pct}% (e.g. {min(15.0, round(sens_pct * 2.0, 1))}%)."
            )
            recommendations.append(
                f"Maintain real-time threshold alerts at lower bound {format_val(lower_limit)} and upper bound {format_val(upper_limit)} for future dataset ingestions."
            )

        return ProjectAnomalyResponse(
            status="success",
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            timestamp_column=timestamp_column,
            metric_column=metric_display,
            detection_method=detection_method,
            sensitivity=sensitivity,
            total_observations=total_obs,
            anomalies_detected=anomalies_count,
            anomaly_rate=anomaly_rate,
            highest_severity=highest_sev,
            upper_threshold=round(upper_limit, 2),
            lower_threshold=round(lower_limit, 2),
            min_observed=round(min_val, 2),
            max_observed=round(max_val, 2),
            mean_observed=round(mean_val, 2),
            std_observed=round(std_val, 2),
            sensitivity_explanation=sensitivity_explanation,
            timeline=timeline,
            logs=logs,
            business_impact=impact_insights,
            recommended_actions=recommendations
        )

    def detect_anomalies(
        self, 
        dataset_ref: str, 
        method: str = "iforest", 
        contamination: float = 0.05, 
        features: Optional[List[str]] = None,
        conn: Optional[duckdb.DuckDBPyConnection] = None
    ) -> Dict[str, Any]:
        """
        Loads the dataset and scans it for outliers.
        """
        df = load_dataset(dataset_ref, conn)
        return self.find_anomalies(df, method, contamination, features)
        
    def find_anomalies(
        self, 
        df: pd.DataFrame, 
        method: str = "iforest", 
        contamination: float = 0.05, 
        features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Scans DataFrame for outliers.
        """
        if len(df) == 0:
            return {"anomalies": [], "total_anomalies_found": 0, "features_used": []}
            
        # Select features to scan
        if not features:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            features = [c for c in numeric_cols if not any(x in str(c).lower() for x in ['id', 'key', 'index'])]
            
        if not features:
            raise ValueError("No numeric features found or selected for anomaly detection.")
            
        # Clear missing data
        clean_df = df[features].dropna().copy()
        if len(clean_df) == 0:
            return {"anomalies": [], "total_anomalies_found": 0, "features_used": [str(f) for f in features]}
            
        # Standardize features
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(clean_df)
        
        # Calculate feature stats
        means = clean_df.mean().to_dict()
        stds = clean_df.std().to_dict()
        
        # Fit model
        method = method.lower().strip()
        if method == "iforest":
            model = IsolationForest(contamination=contamination, random_state=42)
            preds = model.fit_predict(scaled_data)
            scores = -model.decision_function(scaled_data)
        elif method == "lof":
            model = LocalOutlierFactor(n_neighbors=min(20, len(scaled_data)-1), contamination=contamination, novelty=True)
            model.fit(scaled_data)
            preds = model.predict(scaled_data)
            scores = -model.score_samples(scaled_data)
        else:
            raise ValueError(f"Unsupported anomaly detection method: {method}")
            
        anomalies_list = []
        for idx, (lbl, score) in enumerate(zip(preds, scores)):
            if lbl == -1:
                orig_idx = clean_df.index[idx]
                row_vals = clean_df.iloc[idx].to_dict()
                
                explanations = []
                for feat in features:
                    val = row_vals[feat]
                    m = means[feat]
                    s = stds[feat] if stds[feat] > 0 else 1.0
                    z = (val - m) / s
                    explanations.append({
                        "feature": str(feat),
                        "value": float(val),
                        "mean": float(m),
                        "z_score": float(z),
                        "deviation": f"{'+' if z > 0 else ''}{z:.2f} Std Dev"
                    })
                
                # Sort features by absolute Z-score (most deviating first)
                explanations = sorted(explanations, key=lambda x: abs(x["z_score"]), reverse=True)
                
                top_deviant = explanations[0]
                explanation_str = f"Anomaly driven by feature '{top_deviant['feature']}' deviating by {top_deviant['deviation']} from the mean."
                
                anomalies_list.append({
                    "row_index": int(orig_idx),
                    "anomaly_score": float(score),
                    "explanation": explanation_str,
                    "deviations": explanations
                })
                
        # Sort anomalies by score (most anomalous first)
        anomalies_list = sorted(anomalies_list, key=lambda x: x["anomaly_score"], reverse=True)
        
        return {
            "anomalies": anomalies_list,
            "total_anomalies_found": len(anomalies_list),
            "features_used": [str(f) for f in features]
        }
