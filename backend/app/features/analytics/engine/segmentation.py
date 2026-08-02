import pandas as pd
import numpy as np
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class SegmentationService:
    """
    Service to segment tabular datasets using clustering models (KMeans, DBSCAN,
    Hierarchical clustering) and generate cluster summaries.
    """
    
    def segment_dataset(
        self, 
        dataset_ref: str, 
        method: str = "kmeans", 
        n_clusters: int = 3, 
        eps: float = 0.5, 
        min_samples: int = 5, 
        features: Optional[List[str]] = None,
        conn: Optional[duckdb.DuckDBPyConnection] = None
    ) -> Dict[str, Any]:
        """
        Loads the dataset and clusters the data.
        """
        df = load_dataset(dataset_ref, conn)
        return self.cluster_data(df, method, n_clusters, eps, min_samples, features)
        
    def cluster_data(
        self, 
        df: pd.DataFrame, 
        method: str = "kmeans", 
        n_clusters: int = 3, 
        eps: float = 0.5, 
        min_samples: int = 5, 
        features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Runs clustering on pandas DataFrame.
        """
        if len(df) == 0:
            return {"assignments": [], "summaries": {}, "features_used": []}
            
        # Select features to cluster
        if not features:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            features = [c for c in numeric_cols if not any(x in str(c).lower() for x in ['id', 'key', 'index'])]
            
        if not features:
            raise ValueError("No numeric features found or selected for clustering.")
            
        # Copy and clean data for clustering
        cluster_df = df[features].dropna().copy()
        if len(cluster_df) == 0:
            raise ValueError("DataFrame contains only null features.")
            
        method = method.lower().strip()
        if len(cluster_df) < n_clusters and method != 'dbscan':
            raise ValueError(f"Insufficient rows ({len(cluster_df)}) to fit {n_clusters} clusters.")
            
        # Standardize features
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(cluster_df)
        
        # Fit model
        if method == "kmeans":
            model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = model.fit_predict(scaled_data)
        elif method == "dbscan":
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(scaled_data)
        elif method in ["hierarchical", "agglomerative"]:
            model = AgglomerativeClustering(n_clusters=n_clusters)
            labels = model.fit_predict(scaled_data)
        else:
            raise ValueError(f"Unsupported clustering method: {method}")
            
        # Add labels to original index
        cluster_df["cluster"] = labels
        
        # Compute cluster summaries
        summaries = {}
        unique_labels = sorted(list(set(labels)))
        
        original_with_labels = df.loc[cluster_df.index].copy()
        original_with_labels["cluster"] = labels
        
        for cluster_id in unique_labels:
            c_df = cluster_df[cluster_df["cluster"] == cluster_id]
            c_orig_df = original_with_labels[original_with_labels["cluster"] == cluster_id]
            
            size = len(c_df)
            pct = (size / len(cluster_df)) * 100.0
            
            # Compute averages
            feature_means = c_orig_df[features].mean().to_dict()
            global_means = df[features].mean().to_dict()
            
            # Describe characteristics
            high_features = []
            low_features = []
            for feat in features:
                c_mean = feature_means[feat]
                g_mean = global_means[feat]
                if g_mean != 0:
                    ratio = c_mean / g_mean
                    if ratio > 1.15:
                        high_features.append(feat)
                    elif ratio < 0.85:
                        low_features.append(feat)
                        
            desc = ""
            label_name = f"Cluster {cluster_id}"
            if cluster_id == -1:
                label_name = "Noise (Outliers)"
                desc = "Data points that do not belong to any defined cohort."
            else:
                desc_parts = []
                if high_features:
                    desc_parts.append(f"characterized by high values of {', '.join(high_features)}")
                if low_features:
                    desc_parts.append(f"characterized by low values of {', '.join(low_features)}")
                if desc_parts:
                    desc = f"Cohort {cluster_id}, " + " and ".join(desc_parts) + "."
                else:
                    desc = f"Cohort {cluster_id} with average metrics."
                    
            summaries[str(cluster_id)] = {
                "name": label_name,
                "size": size,
                "percentage": float(pct),
                "feature_means": {str(k): float(v) if pd.notna(v) else 0.0 for k, v in feature_means.items()},
                "characteristics": desc
            }
            
        assignments = [{"index": int(idx), "cluster": int(lbl)} for idx, lbl in zip(cluster_df.index, labels)]
        
        return {
            "assignments": assignments,
            "summaries": summaries,
            "features_used": [str(f) for f in features]
        }
