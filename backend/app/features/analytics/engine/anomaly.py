import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, List, Optional
import duckdb
from app.features.analytics.engine.utils import load_dataset

class AnomalyDetectionService:
    """
    Service to perform anomaly detection using Isolation Forest and Local Outlier Factor
    and generate feature-level explanations for outliers.
    """
    
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
