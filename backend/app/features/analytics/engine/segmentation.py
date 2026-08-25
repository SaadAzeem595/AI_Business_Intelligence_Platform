import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import duckdb

from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score

from app.features.analytics.engine.utils import load_dataset
from app.features.analytics.engine.discovery import is_valid_date_column

logger = logging.getLogger(__name__)

ENTITY_KEY_PATTERNS = [
    "customer_unique_id", "customer_id", "user_id", "client_id", "account_id",
    "member_id", "subscriber_id", "patient_id", "entity_id", "shopper_id"
]

MONETARY_PATTERNS = [
    "price", "payment_value", "amount", "revenue", "spend", "total", "cost", "value", "freight_value"
]

ORDER_KEY_PATTERNS = [
    "order_id", "transaction_id", "invoice_id", "sale_id", "purchase_id"
]


class SegmentationService:
    """
    Service to segment tabular datasets using clustering models (KMeans, DBSCAN, Agglomerative)
    with dynamic feature engineering (RFM or generic numerical), auto optimal-k evaluation,
    2D visualization coordinate mapping, and business profile generation.
    """

    def segment_dataset(
        self,
        dataset_ref: str,
        method: str = "kmeans",
        n_clusters: int = 3,
        eps: float = 0.5,
        min_samples: int = 5,
        features: Optional[List[str]] = None,
        mode: str = "auto",
        entity_key: Optional[str] = None,
        conn: Optional[duckdb.DuckDBPyConnection] = None
    ) -> Dict[str, Any]:
        """Loads dataset and executes dynamic clustering."""
        df = load_dataset(dataset_ref, conn)
        return self.cluster_data(
            df=df,
            method=method,
            n_clusters=n_clusters,
            eps=eps,
            min_samples=min_samples,
            features=features,
            mode=mode,
            entity_key=entity_key
        )

    def cluster_data(
        self,
        df: pd.DataFrame,
        method: str = "kmeans",
        n_clusters: int = 3,
        eps: float = 0.5,
        min_samples: int = 5,
        features: Optional[List[str]] = None,
        mode: str = "auto",
        entity_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs data-driven clustering on pandas DataFrame with RFM or generic numerical features,
        optimal-k evaluation, 2D scatter coordinates, and business cohort recommendations.
        """
        if len(df) == 0:
            raise ValueError("The provided dataset is empty.")

        # 1. Detect Entity Key & Transactional Attributes
        detected_entity_key = entity_key or self.detect_entity_key(df)
        detected_trans = self.detect_transactional_columns(df)

        resolved_mode = mode.lower().strip() if mode else "auto"
        if resolved_mode == "auto":
            if detected_entity_key and detected_trans["date_col"] and detected_trans["monetary_col"]:
                resolved_mode = "rfm"
            else:
                resolved_mode = "numerical"

        # 2. Build Feature Matrix
        if resolved_mode == "rfm" and detected_entity_key and detected_trans["date_col"] and detected_trans["monetary_col"]:
            feature_df, entity_names = self._build_rfm_matrix(
                df=df,
                entity_key=detected_entity_key,
                date_col=detected_trans["date_col"],
                monetary_col=detected_trans["monetary_col"],
                order_col=detected_trans["order_col"]
            )
            dataset_type = "Transactional RFM (Recency, Frequency, Monetary)"
            used_features = list(feature_df.columns)
        else:
            resolved_mode = "numerical"
            feature_df, entity_names, used_features = self._build_numerical_matrix(
                df=df,
                requested_features=features,
                entity_key=detected_entity_key
            )
            dataset_type = "Generic Numerical Feature Clustering"

        if len(feature_df) == 0:
            raise ValueError("DataFrame contains no valid rows or non-null features for clustering.")

        # 3. Clean & Standardize Features (Prevent Data Leakage)
        cleaned_df = feature_df.fillna(feature_df.median(numeric_only=True)).fillna(0)
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(cleaned_df)


        # 4. Optimal-K Evaluation
        optimal_k, evaluation_metrics = self.evaluate_optimal_k(scaled_data, max_k=min(8, len(cleaned_df)))

        # Resolve selected k
        method = method.lower().strip()
        selected_k = n_clusters if n_clusters and 2 <= n_clusters <= len(cleaned_df) else optimal_k
        if len(cleaned_df) < selected_k and method != "dbscan":
            raise ValueError(f"Insufficient rows ({len(cleaned_df)}) to fit {selected_k} clusters.")

        # 5. Model Fitting
        if method == "kmeans":
            model = KMeans(n_clusters=selected_k, random_state=42, n_init=10)
            labels = model.fit_predict(scaled_data)
        elif method == "dbscan":
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(scaled_data)
        elif method in ["hierarchical", "agglomerative"]:
            model = AgglomerativeClustering(n_clusters=selected_k)
            labels = model.fit_predict(scaled_data)
        else:
            raise ValueError(f"Unsupported clustering method: {method}")

        # Update evaluation dict with selected k metrics if computed
        if evaluation_metrics:
            evaluation_metrics["optimal_k"] = optimal_k
            evaluation_metrics["selected_k"] = selected_k
            if selected_k in evaluation_metrics.get("metrics_by_k", {}):
                sel_m = evaluation_metrics["metrics_by_k"][selected_k]
                evaluation_metrics["silhouette_score"] = sel_m["silhouette_score"]
                evaluation_metrics["davies_bouldin_index"] = sel_m["davies_bouldin_index"]
                evaluation_metrics["calinski_harabasz_index"] = sel_m["calinski_harabasz_index"]

        # 6. Generate 2D Scatter Coordinates
        scatter_points = self._generate_scatter_points(
            scaled_data=scaled_data,
            feature_df=feature_df,
            entity_names=entity_names,
            labels=labels
        )

        # 7. Generate Business Segment Profiles & Summaries
        summaries, cohorts_list, profiles_list = self._generate_segment_profiles(
            feature_df=cleaned_df,
            labels=labels,
            used_features=used_features,
            mode=resolved_mode
        )

        assignments = [
            {"index": i, "entity": str(ent), "cluster": int(lbl)}
            for i, (idx, ent, lbl) in enumerate(zip(cleaned_df.index, entity_names, labels))
        ]

        return {
            "assignments": assignments,
            "summaries": summaries,
            "scatter": scatter_points,
            "cohorts": cohorts_list,
            "profiles": profiles_list,
            "evaluation": evaluation_metrics,
            "features_used": used_features,
            "dataset_type": dataset_type,
            "entity_key": detected_entity_key,
            "message": f"Successfully clustered {len(cleaned_df)} entities into {len(summaries)} segments using {method.upper()}."
        }

    # =========================================================================
    # Entity & Trait Discovery Helpers
    # =========================================================================
    def detect_entity_key(self, df: pd.DataFrame) -> Optional[str]:
        """Scans column names for primary entity/customer identifiers."""
        col_map = {str(col).lower(): str(col) for col in df.columns}
        for pattern in ENTITY_KEY_PATTERNS:
            if pattern in col_map:
                return col_map[pattern]

        # Look for columns ending with _id or _key
        for col in df.columns:
            c_lower = str(col).lower()
            if (c_lower.endswith("_id") or c_lower.endswith("_key")) and not c_lower.startswith("order_"):
                return str(col)
        return None

    def detect_transactional_columns(self, df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """Detects timestamp, monetary value, and order ID columns for RFM calculation."""
        date_col = None
        for col in df.columns:
            if is_valid_date_column(df, str(col)):
                date_col = str(col)
                break

        monetary_col = None
        col_map = {str(c).lower(): str(c) for c in df.columns}
        for pat in MONETARY_PATTERNS:
            if pat in col_map:
                monetary_col = col_map[pat]
                break
        if not monetary_col:
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]) and any(p in str(col).lower() for p in ["price", "amount", "revenue", "total", "spend", "value"]):
                    monetary_col = str(col)
                    break

        order_col = None
        for pat in ORDER_KEY_PATTERNS:
            if pat in col_map:
                order_col = col_map[pat]
                break

        return {"date_col": date_col, "monetary_col": monetary_col, "order_col": order_col}

    # =========================================================================
    # Feature Engineering Pipelines
    # =========================================================================
    def _build_rfm_matrix(
        self,
        df: pd.DataFrame,
        entity_key: str,
        date_col: str,
        monetary_col: str,
        order_col: Optional[str] = None
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Aggregates transactional data into RFM (Recency, Frequency, Monetary) features per entity."""
        temp = df[[entity_key, date_col, monetary_col] + ([order_col] if order_col and order_col in df.columns else [])].dropna(subset=[entity_key]).copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        temp = temp.dropna(subset=[date_col])

        if len(temp) == 0:
            raise ValueError(f"No valid datetime records found in column '{date_col}'.")

        max_date = temp[date_col].max()

        freq_series = temp.groupby(entity_key)[order_col].nunique() if (order_col and order_col in temp.columns) else temp.groupby(entity_key)[date_col].count()
        rec_series = temp.groupby(entity_key)[date_col].apply(lambda s: (max_date - s.max()).days)
        mon_series = temp.groupby(entity_key)[monetary_col].sum()

        rfm_df = pd.DataFrame({
            "recency": rec_series,
            "frequency": freq_series,
            "monetary": mon_series
        })

        # Apply log1p transformation to reduce skewness for distance calculations
        rfm_transformed = pd.DataFrame({
            "recency": rfm_df["recency"].clip(lower=0),
            "frequency": np.log1p(rfm_df["frequency"].clip(lower=0)),
            "monetary": np.log1p(rfm_df["monetary"].clip(lower=0))
        }, index=rfm_df.index)

        entity_names = [str(x) for x in rfm_df.index]
        return rfm_transformed, entity_names

    def _build_numerical_matrix(
        self,
        df: pd.DataFrame,
        requested_features: Optional[List[str]] = None,
        entity_key: Optional[str] = None
    ) -> Tuple[pd.DataFrame, List[str], List[str]]:
        """Extracts and prepares generic numerical feature columns."""
        working_df = df.copy()

        if entity_key and entity_key in working_df.columns:
            entity_names = [str(x) for x in working_df[entity_key]]
        else:
            entity_names = [f"Row {i}" for i in range(len(working_df))]

        if requested_features:
            selected_features = [f.strip() for f in requested_features if f.strip() in working_df.columns]
        else:
            numeric_cols = working_df.select_dtypes(include=[np.number]).columns.tolist()
            # Exclude strict ID/key columns
            selected_features = [
                c for c in numeric_cols
                if not any(x in str(c).lower() for x in ["id", "key", "index", "zip", "code", "phone"])
                and working_df[c].nunique() > 1
            ]

        if not selected_features:
            # Fallback to any numeric columns
            selected_features = working_df.select_dtypes(include=[np.number]).columns.tolist()

        if not selected_features:
            raise ValueError("No clusterable numerical features found or selected in dataset.")

        feature_df = working_df[selected_features].copy()
        return feature_df, entity_names, [str(f) for f in selected_features]

    # =========================================================================
    # Model Evaluation & Optimal-K Selection
    # =========================================================================
    def evaluate_optimal_k(self, scaled_data: np.ndarray, max_k: int = 8) -> Tuple[int, Dict[str, Any]]:
        """Evaluates k from 2 to max_k using Silhouette Score, Davies-Bouldin, and Calinski-Harabasz metrics."""
        n_samples = len(scaled_data)
        if n_samples < 3:
            return 2, {"optimal_k": 2, "selected_k": 2, "silhouette_score": 0.0, "davies_bouldin_index": 0.0, "calinski_harabasz_index": 0.0, "metrics_by_k": {}}

        max_k_eval = min(max_k, n_samples - 1)
        if max_k_eval < 2:
            max_k_eval = 2

        # Subsample high-dimensional or large matrices for fast evaluation
        if n_samples > 2000:
            np.random.seed(42)
            eval_indices = np.random.choice(n_samples, 2000, replace=False)
            eval_data = scaled_data[eval_indices]
        else:
            eval_data = scaled_data

        metrics_by_k = {}
        best_k = 2
        best_sil = -1.0

        for k in range(2, max_k_eval + 1):
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=5)
                lbls = km.fit_predict(eval_data)

                if len(set(lbls)) < 2:
                    continue

                sil = float(silhouette_score(eval_data, lbls, sample_size=min(1000, len(eval_data)), random_state=42))
                db_idx = float(davies_bouldin_score(eval_data, lbls))
                ch_idx = float(calinski_harabasz_score(eval_data, lbls))

                metrics_by_k[k] = {
                    "silhouette_score": round(sil, 4),
                    "davies_bouldin_index": round(db_idx, 4),
                    "calinski_harabasz_index": round(ch_idx, 2)
                }

                if sil > best_sil:
                    best_sil = sil
                    best_k = k
            except Exception as e:
                logger.warning(f"Error evaluating cluster count k={k}: {e}")

        top_m = metrics_by_k.get(best_k, {"silhouette_score": 0.0, "davies_bouldin_index": 0.0, "calinski_harabasz_index": 0.0})

        evaluation_result = {
            "optimal_k": best_k,
            "selected_k": best_k,
            "silhouette_score": top_m["silhouette_score"],
            "davies_bouldin_index": top_m["davies_bouldin_index"],
            "calinski_harabasz_index": top_m["calinski_harabasz_index"],
            "metrics_by_k": metrics_by_k
        }
        return best_k, evaluation_result


    # =========================================================================
    # 2D Scatter Coordinate Generation
    # =========================================================================
    def _generate_scatter_points(
        self,
        scaled_data: np.ndarray,
        feature_df: pd.DataFrame,
        entity_names: List[str],
        labels: np.ndarray,
        max_points: int = 300
    ) -> List[Dict[str, Any]]:
        """Computes 2D scatter coordinates (direct 2D or PCA reduction) for data visualization."""
        n_features = feature_df.shape[1]

        if n_features == 2:
            x_vals = feature_df.iloc[:, 0].to_numpy()
            y_vals = feature_df.iloc[:, 1].to_numpy()
        else:
            pca = PCA(n_components=2, random_state=42)
            coords = pca.fit_transform(scaled_data)
            x_vals = coords[:, 0]
            y_vals = coords[:, 1]

        scatter = []
        step = max(1, len(feature_df) // max_points)
        indices = range(0, len(feature_df), step)

        for idx in indices:
            c_lbl = int(labels[idx])
            c_name = f"Cluster {c_lbl}" if c_lbl >= 0 else "Noise (Outliers)"

            scatter.append({
                "name": str(entity_names[idx]),
                "x": float(np.round(x_vals[idx], 3)),
                "y": float(np.round(y_vals[idx], 3)),
                "cluster": c_name,
                "details": {
                    feat: float(np.round(feature_df.iloc[idx][feat], 2)) if pd.notna(feature_df.iloc[idx][feat]) else 0.0
                    for feat in feature_df.columns[:4]
                }
            })

        return scatter

    # =========================================================================
    # Business Profile & Recommendations Generator
    # =========================================================================
    def _generate_segment_profiles(
        self,
        feature_df: pd.DataFrame,
        labels: np.ndarray,
        used_features: List[str],
        mode: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generates dynamic, evidence-based business profiles, risk ratings, and recommendations.
        Compares each cluster's feature means and medians against global dataset averages/medians.
        """
        summaries = {}
        cohorts = []
        profiles = []

        unique_labels = sorted(list(set(labels)))
        global_means = feature_df[used_features].mean().to_dict()
        global_medians = feature_df[used_features].median().to_dict()
        global_stds = feature_df[used_features].std().to_dict()
        total_count = len(feature_df)

        original_with_labels = feature_df.copy()
        original_with_labels["cluster"] = labels

        for cid in unique_labels:
            c_df = feature_df[original_with_labels["cluster"] == cid]
            size = len(c_df)
            pct = (size / total_count) * 100.0 if total_count > 0 else 0.0
            feature_means = c_df[used_features].mean().to_dict()
            feature_medians = c_df[used_features].median().to_dict()

            stat_high_feats = []
            stat_low_feats = []
            feature_stats = {}

            for f in used_features:
                c_m = float(feature_means.get(f, 0.0))
                g_m = float(global_means.get(f, 0.0))
                c_med = float(feature_medians.get(f, 0.0))
                g_med = float(global_medians.get(f, 0.0))
                g_std = float(global_stds.get(f, 0.0))

                pct_diff = ((c_m - g_m) / abs(g_m)) * 100.0 if abs(g_m) > 1e-6 else (100.0 if c_m > 0 else 0.0)
                z_score = (c_m - g_m) / g_std if g_std > 1e-6 else 0.0

                feature_stats[f] = {
                    "cluster_mean": c_m,
                    "cluster_median": c_med,
                    "global_mean": g_m,
                    "global_median": g_med,
                    "pct_diff": pct_diff,
                    "z_score": z_score
                }

                if pct_diff >= 15.0 or z_score >= 0.4:
                    stat_high_feats.append((f, c_m, g_m, pct_diff))
                elif pct_diff <= -15.0 or z_score <= -0.4:
                    stat_low_feats.append((f, c_m, g_m, pct_diff))

            if mode == "rfm":
                name, desc, rec, risk, avg_spend_str, freq_score_str = self._describe_rfm_cluster(
                    cid=cid,
                    size=size,
                    pct=pct,
                    means=feature_means,
                    global_means=global_means,
                    feature_stats=feature_stats
                )
            else:
                name, desc, rec, risk, avg_spend_str, freq_score_str = self._describe_generic_cluster(
                    cid=cid,
                    size=size,
                    pct=pct,
                    stat_high_feats=stat_high_feats,
                    stat_low_feats=stat_low_feats,
                    feature_stats=feature_stats,
                    used_features=used_features
                )

            summaries[str(cid)] = {
                "name": name,
                "size": size,
                "percentage": float(np.round(pct, 2)),
                "feature_means": {str(k): float(np.round(v, 2)) if pd.notna(v) else 0.0 for k, v in feature_means.items()},
                "characteristics": desc,
                "recommendation": rec,
                "risk_rating": risk
            }

            cohorts.append({
                "name": f"{name} ({desc})",
                "count": size,
                "avgSpent": avg_spend_str,
                "freqScore": freq_score_str,
                "riskRating": risk
            })

            profiles.append({
                "cluster_id": int(cid),
                "name": name,
                "size": size,
                "percentage": float(np.round(pct, 2)),
                "characteristics": desc,
                "recommendation": rec,
                "risk_rating": risk,
                "feature_means": {str(k): float(np.round(v, 2)) if pd.notna(v) else 0.0 for k, v in feature_means.items()}
            })

        return summaries, cohorts, profiles

    def _describe_rfm_cluster(
        self,
        cid: int,
        size: int,
        pct: float,
        means: Dict[str, float],
        global_means: Dict[str, float],
        feature_stats: Dict[str, Dict[str, float]]
    ) -> Tuple[str, str, str, str, str, str]:
        """Classifies RFM clusters into evidence-based business personas with data-driven recommendations."""
        if cid == -1:
            return "Outlier Segment", "Entities with unclassified outlier transaction behavior.", "Audit individual anomaly records.", "Neutral", "$0", "0/100"

        c_r = means.get("recency", 0.0)
        c_f = means.get("frequency", 0.0)
        c_m = means.get("monetary", 0.0)

        g_r = global_means.get("recency", 1.0)
        g_f = global_means.get("frequency", 1.0)
        g_m = global_means.get("monetary", 1.0)

        is_recent = c_r <= g_r
        is_frequent = c_f >= g_f
        is_high_mon = c_m >= g_m

        real_monetary = np.expm1(c_m) if c_m > 0 else 0.0
        avg_spend_str = f"${real_monetary:,.0f}" if real_monetary > 0 else "$0"
        freq_score_str = f"{min(100, int(pct))}/100"

        r_diff = feature_stats.get("recency", {}).get("pct_diff", 0.0)
        f_diff = feature_stats.get("frequency", {}).get("pct_diff", 0.0)
        m_diff = feature_stats.get("monetary", {}).get("pct_diff", 0.0)

        desc = f"Recency mean: {c_r:.1f} days ({r_diff:+.1f}% vs global avg {g_r:.1f}); Frequency mean score: {c_f:.2f} ({f_diff:+.1f}% vs avg); Monetary sum mean: {c_m:.2f} ({m_diff:+.1f}% vs avg)."

        if is_recent and is_frequent and is_high_mon:
            name = "High Engagement & Spend Cohort"
            rec = "Maintain active engagement with high-frequency, recent spenders through ongoing value programs and dedicated support."
            risk = "Low"
        elif not is_recent and is_frequent and is_high_mon:
            name = "Dormant High-Value Cohort"
            rec = f"Address elevated recency ({r_diff:+.1f}% above avg) for historically active spenders through targeted re-engagement offers."
            risk = "High"
        elif is_recent and not is_frequent and is_high_mon:
            name = "New High-Spend Cohort"
            rec = f"Leverage strong monetary baseline ({m_diff:+.1f}% vs avg) by introducing onboarding pathways to increase order frequency."
            risk = "Medium"
        elif is_recent and is_frequent and not is_high_mon:
            name = "Frequent Low-Basket Cohort"
            rec = f"Capitalize on high transaction frequency ({f_diff:+.1f}% vs avg) by offering volume bundles to increase basket value."
            risk = "Low"
        elif not is_recent and not is_frequent and not is_high_mon:
            name = "Inactive Cohort"
            rec = f"Monitor inactive segment exhibiting low frequency ({f_diff:+.1f}%) and high recency ({r_diff:+.1f}%). Limit high-cost ad acquisition spend."
            risk = "High"
        else:
            name = f"Standard Activity Cohort (Cluster {cid + 1})"
            rec = "Maintain standard automated engagement flows and monitor metrics for cohort migration."
            risk = "Medium"

        return name, desc, rec, risk, avg_spend_str, freq_score_str

    def _describe_generic_cluster(
        self,
        cid: int,
        size: int,
        pct: float,
        stat_high_feats: List[Tuple[str, float, float, float]],
        stat_low_feats: List[Tuple[str, float, float, float]],
        feature_stats: Dict[str, Dict[str, float]],
        used_features: List[str]
    ) -> Tuple[str, str, str, str, str, str]:
        """
        Generates evidence-based cohort names, characteristics, risk labels, and recommendations
        for numerical feature clusters. Avoids generic labels like 'Feature Content'.
        Names are derived strictly from features with the largest statistically meaningful deviations.
        """
        if cid == -1:
            return "Outlier & Noise Cohort", "Entities with extreme metric deviations differing from primary cluster patterns.", "Audit data quality and inspect individual row anomalies.", "N/A", "N/A", "0/100"

        # Friendly column label mapping
        COLUMN_BUSINESS_NAMES = {
            "price": "Unit Price",
            "unit_price": "Unit Price",
            "payment_value": "Payment Value",
            "revenue": "Revenue",
            "spend": "Total Spend",
            "annual_spend": "Annual Spend",
            "monetary": "Monetary Value",
            "amount": "Transaction Amount",
            "total": "Total Financial Value",
            "cost": "Operating Cost",
            "freight_value": "Freight Cost",
            "shipping_cost": "Shipping Cost",
            "postage": "Postage Cost",
            "product_weight_g": "Product Weight",
            "weight": "Item Weight",
            "mass": "Item Mass",
            "product_length_cm": "Product Length",
            "length": "Item Length",
            "product_height_cm": "Product Height",
            "height": "Item Height",
            "product_width_cm": "Product Width",
            "width": "Item Width",
            "frequency": "Frequency",
            "order_count": "Order Count",
            "conversions": "Conversions",
            "visitors": "Visitors",
            "sessions": "Sessions",
            "recency": "Days Active",
            "profit": "Net Profit",
            "sales_volume": "Sales Volume",
            "feature_x": "Feature X",
            "feature_y": "Feature Y",
            "churn_rate": "Churn Rate",
            "risk_score": "Risk Score",
            "default_rate": "Default Rate"
        }

        def clean_label(feat: str) -> str:
            f_lower = str(feat).lower().strip()
            if f_lower in COLUMN_BUSINESS_NAMES:
                return COLUMN_BUSINESS_NAMES[f_lower]
            return feat.replace("_", " ").title()

        # Check for explicit risk metrics in dataset
        RISK_KEYWORDS = ["churn", "risk", "default", "delinquent", "loss", "cancellation", "fraud", "late", "overdue", "error_rate", "bounce_rate", "unpaid", "chargeback"]
        risk_metric_feat = None
        for f in used_features:
            if any(k in f.lower() for k in RISK_KEYWORDS):
                risk_metric_feat = f
                break

        # 1. Determine Risk Rating (Strictly Evidence-Based)
        if risk_metric_feat:
            r_stat = feature_stats.get(risk_metric_feat, {})
            r_diff = r_stat.get("pct_diff", 0.0)
            if r_diff >= 15.0:
                risk = "High"
            elif r_diff <= -15.0:
                risk = "Low"
            else:
                risk = "Medium"
        else:
            risk = "N/A"

        # Categorize features by domain semantics
        WEIGHT_KEYWORDS = ["weight", "mass"]
        DIMENSION_KEYWORDS = ["length", "height", "width", "size", "volume", "cubage", "dimension"]
        PRICE_KEYWORDS = ["price", "spend", "revenue", "monetary", "amount", "cost", "total", "value"]
        FREIGHT_KEYWORDS = ["freight", "shipping", "postage", "logistics"]

        def find_domain_feats(feat_tuples, keywords):
            return [t for t in feat_tuples if any(k in t[0].lower() for k in keywords)]

        high_weight = find_domain_feats(stat_high_feats, WEIGHT_KEYWORDS)
        low_weight = find_domain_feats(stat_low_feats, WEIGHT_KEYWORDS)
        high_dim = find_domain_feats(stat_high_feats, DIMENSION_KEYWORDS)
        low_dim = find_domain_feats(stat_low_feats, DIMENSION_KEYWORDS)
        high_price = find_domain_feats(stat_high_feats, PRICE_KEYWORDS)
        low_price = find_domain_feats(stat_low_feats, PRICE_KEYWORDS)
        high_freight = find_domain_feats(stat_high_feats, FREIGHT_KEYWORDS)
        low_freight = find_domain_feats(stat_low_feats, FREIGHT_KEYWORDS)

        # 2. Formulate Cluster Name based on strongest domain traits or strongest statistical deviations
        name = None

        # Pattern A: Physical product attributes (Weight & Dimensions)
        if high_weight and high_dim:
            name = "Large & Heavy Products"
        elif low_weight and low_dim:
            name = "Compact & Lightweight Products"
        elif high_weight and low_dim:
            name = "Dense & Heavyweight Compact Products"
        elif low_weight and high_dim:
            name = "Bulky & Lightweight Products"
        elif high_weight:
            name = "Heavyweight Product Cohort"
        elif low_weight:
            name = "Lightweight Product Cohort"
        elif high_dim:
            name = "Large Dimension Products"
        elif low_dim:
            name = "Compact Dimension Products"
        # Pattern B: Pricing & Financial Value
        elif high_price and not low_price:
            p_name = clean_label(high_price[0][0])
            name = f"High {p_name} Cluster"
        elif low_price and not high_price:
            p_name = clean_label(low_price[0][0])
            name = f"Low {p_name} Cluster"
        # Pattern C: Freight / Shipping Costs
        elif high_freight:
            name = "High Freight & Shipping Cost Cohort"
        elif low_freight:
            name = "Low Freight & Shipping Cost Cohort"

        # Pattern D: Fallback to strongest individual feature deviations sorted by absolute deviation
        if not name:
            all_deviations = sorted(
                stat_high_feats + stat_low_feats,
                key=lambda x: abs(x[3]),
                reverse=True
            )
            if all_deviations:
                top = all_deviations[0]
                top_name = clean_label(top[0])
                if top[3] > 0:
                    name = f"Elevated {top_name} Cohort"
                else:
                    name = f"Reduced {top_name} Cohort"

                if len(all_deviations) > 1:
                    second = all_deviations[1]
                    second_name = clean_label(second[0])
                    if (top[3] > 0 and second[3] > 0):
                        name = f"High {top_name} & {second_name} Cluster"
                    elif (top[3] < 0 and second[3] < 0):
                        name = f"Low {top_name} & {second_name} Cluster"
                    elif (top[3] > 0 and second[3] < 0):
                        name = f"High {top_name} & Low {second_name} Cluster"
                    elif (top[3] < 0 and second[3] > 0):
                        name = f"Low {top_name} & High {second_name} Cluster"
            else:
                name = f"Standard Baseline Trait Cluster (Cluster {cid + 1})"

        # 3. Build Detailed Characteristics (Citing exact calculated feature means/medians vs global dataset averages/medians)
        char_parts = []
        for f in used_features:
            st = feature_stats.get(f, {})
            c_m = st.get("cluster_mean", 0.0)
            g_m = st.get("global_mean", 0.0)
            diff = st.get("pct_diff", 0.0)
            char_parts.append(f"{clean_label(f)} mean is {c_m:.2f} ({diff:+.1f}% vs global avg {g_m:.2f})")

        desc = "; ".join(char_parts) + "." if char_parts else "Cluster feature metrics align closely with dataset baseline averages."

        # 4. Generate Practical Business Recommendations derived strictly from strongest deviations
        all_dev_sorted = sorted(
            stat_high_feats + stat_low_feats,
            key=lambda x: abs(x[3]),
            reverse=True
        )

        rec_parts = []
        if high_weight and high_dim:
            w_diff = high_weight[0][3]
            d_diff = high_dim[0][3]
            rec_parts.append(f"Because product weight is +{w_diff:.1f}% above average and dimensions are +{d_diff:.1f}% larger, optimize warehouse rack allocation, evaluate heavy-freight carrier tiers, and audit bulk packaging costs.")
        elif low_weight and low_dim:
            w_diff = low_weight[0][3]
            d_diff = low_dim[0][3]
            rec_parts.append(f"Because product weight is {w_diff:.1f}% below average and dimensions are {d_diff:.1f}% smaller, leverage standard parcel envelopes and small-box fulfillment to minimize postage fees.")
        elif high_freight:
            f_diff = high_freight[0][3]
            rec_parts.append(f"Given shipping costs are +{f_diff:.1f}% above average, review carrier rate tables and evaluate regional fulfillment centers to lower logistics expenses.")
        elif low_freight:
            f_diff = low_freight[0][3]
            rec_parts.append(f"Capitalize on lower shipping costs ({f_diff:.1f}% below average) by offering multi-item bundling thresholds to optimize net fulfillment margins.")
        elif high_price:
            p_diff = high_price[0][3]
            rec_parts.append(f"For higher price-point items (+{p_diff:.1f}% vs global avg), offer signature delivery tracking and premium protective packaging.")
        elif low_price:
            p_diff = low_price[0][3]
            rec_parts.append(f"For lower price-point items ({p_diff:.1f}% below avg), focus on unit volume fulfillment efficiency to preserve operational margins.")
        elif all_dev_sorted:
            top = all_dev_sorted[0]
            top_name = clean_label(top[0])
            direction = "above" if top[3] > 0 else "below"
            rec_parts.append(f"Focus operational monitoring on {top_name} exhibiting the strongest deviation ({top[3]:+.1f}% {direction} dataset average). Adjust process baselines accordingly.")
        else:
            rec_parts.append("All evaluated features operate within ±15% of dataset global baseline averages. Maintain standard monitoring workflows.")

        rec = " ".join(rec_parts)

        first_feat_val = list(feature_stats.values())[0]["cluster_mean"] if feature_stats else 0.0
        avg_spend_str = f"${first_feat_val:,.2f}" if (high_price or low_price or first_feat_val > 100) else f"{first_feat_val:.2f}"
        freq_score_str = f"{min(100, int(pct))}/100"

        return name, desc, rec, risk, avg_spend_str, freq_score_str


