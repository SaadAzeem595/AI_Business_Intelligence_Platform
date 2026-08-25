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
        if evaluation_metrics and selected_k in evaluation_metrics.get("metrics_by_k", {}):
            sel_m = evaluation_metrics["metrics_by_k"][selected_k]
            evaluation_metrics["selected_k"] = selected_k
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

        metrics_by_k = {}
        best_k = 2
        best_sil = -1.0

        for k in range(2, max_k_eval + 1):
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                lbls = km.fit_predict(scaled_data)

                if len(set(lbls)) < 2:
                    continue

                sil = float(silhouette_score(scaled_data, lbls))
                db_idx = float(davies_bouldin_score(scaled_data, lbls))
                ch_idx = float(calinski_harabasz_score(scaled_data, lbls))

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
        """Generates dynamic, data-driven business profiles, risk ratings, and recommendations."""
        summaries = {}
        cohorts = []
        profiles = []

        unique_labels = sorted(list(set(labels)))
        global_means = feature_df.mean().to_dict()
        total_count = len(feature_df)

        original_with_labels = feature_df.copy()
        original_with_labels["cluster"] = labels

        for cid in unique_labels:
            c_df = feature_df[original_with_labels["cluster"] == cid]
            size = len(c_df)
            pct = (size / total_count) * 100.0 if total_count > 0 else 0.0
            feature_means = c_df.mean().to_dict()

            high_feats = []
            low_feats = []
            for f in used_features:
                c_m = feature_means.get(f, 0.0)
                g_m = global_means.get(f, 0.0)
                if g_m != 0:
                    ratio = c_m / g_m
                    if ratio > 1.15:
                        high_feats.append(f)
                    elif ratio < 0.85:
                        low_feats.append(f)

            if mode == "rfm":
                name, desc, rec, risk, avg_spend_str, freq_score_str = self._describe_rfm_cluster(
                    cid=cid,
                    size=size,
                    pct=pct,
                    means=feature_means,
                    global_means=global_means
                )
            else:
                name, desc, rec, risk, avg_spend_str, freq_score_str = self._describe_generic_cluster(
                    cid=cid,
                    size=size,
                    pct=pct,
                    high_feats=high_feats,
                    low_feats=low_feats,
                    means=feature_means,
                    global_means=global_means
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
        global_means: Dict[str, float]
    ) -> Tuple[str, str, str, str, str, str]:
        """Classifies RFM clusters into business personas with tailored recommendations."""
        c_r = means.get("recency", 0.0)
        c_f = means.get("frequency", 0.0)
        c_m = means.get("monetary", 0.0)

        g_r = global_means.get("recency", 1.0)
        g_f = global_means.get("frequency", 1.0)
        g_m = global_means.get("monetary", 1.0)

        is_recent = c_r <= g_r
        is_frequent = c_f >= g_f
        is_high_mon = c_m >= g_m

        # Convert log transformed values back for display if needed
        real_monetary = np.expm1(c_m) if c_m > 0 else 0.0
        avg_spend_str = f"${real_monetary:,.0f}" if real_monetary > 0 else "$0"
        freq_score_str = f"{min(100, int(pct))}/100"

        if cid == -1:
            return "Outlier Segment", "Unclassified customer behaviors.", "Audit individual user actions.", "Medium", "$0", "0/100"

        if is_recent and is_frequent and is_high_mon:
            name = "Champions & VIP Customers"
            desc = "High spenders with frequent recent orders."
            rec = "Provide exclusive VIP perks, early product access, and dedicated customer service."
            risk = "Low"
        elif not is_recent and is_frequent and is_high_mon:
            name = "At-Risk VIPs (High Spend, Idle)"
            desc = "Historically high spenders who haven't ordered recently."
            rec = "Deploy personalized win-back offers and retention incentives immediately."
            risk = "High"
        elif is_recent and not is_frequent and is_high_mon:
            name = "New High-Value Prospects"
            desc = "Recent high monetary buyers with low order count."
            rec = "Offer onboarding incentives and cross-sell premium complementary products."
            risk = "Medium"
        elif is_recent and is_frequent and not is_high_mon:
            name = "Frequent Bargain Hunters"
            desc = "Highly active buyers with lower order basket values."
            rec = "Offer bundle discounts and order thresholds to increase average cart size."
            risk = "Low"
        elif not is_recent and not is_frequent and not is_high_mon:
            name = "Hibernating / Churned Buyers"
            desc = "Inactive customers with low historical spend."
            rec = "Include in automated email re-engagement or limit paid ad spend."
            risk = "High"
        else:
            name = f"Core Customer Segment {cid}"
            desc = f"Cluster {cid} exhibiting steady operational interactions."
            rec = "Maintain standard automated marketing workflows."
            risk = "Medium"

        return name, desc, rec, risk, avg_spend_str, freq_score_str

    def _describe_generic_cluster(
        self,
        cid: int,
        size: int,
        pct: float,
        high_feats: List[str],
        low_feats: List[str],
        means: Dict[str, float],
        global_means: Dict[str, float]
    ) -> Tuple[str, str, str, str, str, str]:
        """Generates dynamic business names and recommendations for generic numerical feature clusters."""
        if cid == -1:
            return "Noise / Outliers", "Data points differing significantly from main clusters.", "Inspect individual data entries.", "High", "N/A", "0/100"

        desc_parts = []
        if high_feats:
            desc_parts.append(f"High {', '.join(high_feats[:2])}")
        if low_feats:
            desc_parts.append(f"Low {', '.join(low_feats[:2])}")

        if desc_parts:
            name = " & ".join(desc_parts) + f" Cohort"
            desc = f"Segment characterized by " + " and ".join(desc_parts) + "."
        else:
            name = f"Average Performer Cohort {cid}"
            desc = f"Cohort {cid} with metrics near global dataset average."

        # Compute spend string from first monetary-like feature if available
        first_feat_val = list(means.values())[0] if means else 0.0
        avg_spend_str = f"${first_feat_val:,.0f}" if first_feat_val > 10 else f"{first_feat_val:.1f}"
        freq_score_str = f"{min(100, int(pct))}/100"

        if high_feats and not low_feats:
            rec = "Capitalize on high feature performance with scaling investments."
            risk = "Low"
        elif low_feats and not high_feats:
            rec = "Address underlying operational bottlenecks causing low metric values."
            risk = "High"
        else:
            rec = "Monitor cohort performance stability and optimize key metric ratios."
            risk = "Medium"

        return name, desc, rec, risk, avg_spend_str, freq_score_str
