import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest

from app.features.ml.registry import ModelRegistryService
from app.features.ml.preprocessing import PreprocessingService

class InferenceService:
    """
    Serves predictions (batch and single) for registered models.
    Provides probability scores, confidence ranges, and explanation metadata.
    """
    def __init__(self, registry: Optional[ModelRegistryService] = None):
        self.registry = registry or ModelRegistryService()
        
    def predict(
        self,
        model_name: str,
        inputs: List[Dict[str, Any]],
        version: Optional[int] = None,
        stage: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs batch predictions for given inputs and returns prediction metadata."""
        model, preprocessor = self.registry.load_model_and_preprocessor(model_name, version, stage)
        
        # Convert inputs to DataFrame
        df = pd.DataFrame(inputs)
        
        # Preprocess features
        processed_df = preprocessor.transform(df)
        
        # Drop the target column during inference if it exists
        if preprocessor.target_col and preprocessor.target_col in processed_df.columns:
            processed_df = processed_df.drop(columns=[preprocessor.target_col])
            
        X = processed_df.values
        
        results = []
        
        # Check if the model is a classifier
        is_classifier = False
        from sklearn.base import is_classifier as sklearn_is_classifier
        if sklearn_is_classifier(model) or hasattr(model, "classes_"):
            is_classifier = True
        elif type(model).__name__ in ["XGBClassifier", "LGBMClassifier", "RandomForestClassifier"]:
            is_classifier = True
            
        # 1. Classification (e.g. Churn)
        if is_classifier:
            preds = model.predict(X)
            probs = model.predict_proba(X) if hasattr(model, "predict_proba") else None
            
            has_encoder = hasattr(preprocessor, "target_encoder") and preprocessor.target_encoder is not None
            if has_encoder:
                le = preprocessor.target_encoder
                class_names = le.classes_
            else:
                class_names = getattr(model, "classes_", np.unique(preds))
            
            for idx, (pred, prob) in enumerate(zip(preds, probs if probs is not None else [None] * len(preds))):
                if prob is not None:
                    prob_dict = {str(class_names[i]): float(prob[i]) for i in range(len(class_names))}
                    pred_label = str(le.inverse_transform([pred])[0]) if has_encoder else str(pred)
                    
                    try:
                        if has_encoder:
                            confidence = float(prob[pred])
                        else:
                            class_idx = np.where(class_names == pred)[0][0]
                            confidence = float(prob[class_idx])
                    except Exception:
                        confidence = 1.0
                        
                    explanation = f"Model predicts class '{pred_label}' with confidence {confidence*100:.1f}%."
                else:
                    prob_dict = {}
                    pred_label = str(le.inverse_transform([pred])[0]) if has_encoder else str(pred)
                    explanation = f"Model predicts class '{pred_label}'."
                
                res_item = {
                    "prediction": pred_label,
                    "explanation": explanation
                }
                if prob_dict:
                    res_item["probabilities"] = prob_dict
                results.append(res_item)
                
        # 2. Anomaly Detection (Isolation Forest)
        elif isinstance(model, IsolationForest) or model_name.lower() in ["anomaly", "anomaly_detection"]:
            preds = model.predict(X) # -1 or 1
            scores = -model.decision_function(X) if hasattr(model, "decision_function") else np.zeros(len(X))
            
            means = preprocessor.impute_values
            
            for idx, (pred, score) in enumerate(zip(preds, scores)):
                is_anomaly = bool(pred == -1)
                
                # Compute deviations
                deviations = []
                row_vals = processed_df.iloc[idx].to_dict()
                for feat, val in row_vals.items():
                    m = means.get(feat, 0.0)
                    if isinstance(m, (int, float)):
                        diff = float(val - m)
                        deviations.append({
                            "feature": str(feat),
                            "value": float(val),
                            "mean": float(m),
                            "deviation": diff
                        })
                deviations = sorted(deviations, key=lambda x: abs(x["deviation"]), reverse=True)
                
                explanation_str = "Data point exhibits typical behavior."
                if is_anomaly:
                    top_dev = deviations[0] if deviations else None
                    if top_dev:
                        explanation_str = f"Anomaly detected. Feature '{top_dev['feature']}' deviated by {top_dev['deviation']:.2f} from baseline."
                        
                results.append({
                    "prediction": "Anomaly" if is_anomaly else "Normal",
                    "anomaly_score": float(score),
                    "is_anomaly": is_anomaly,
                    "explanation": explanation_str,
                    "deviations": deviations[:3]
                })
                
        # 3. Clustering / Segmentation (KMeans)
        elif isinstance(model, KMeans):
            preds = model.predict(X)
            distances = model.transform(X)
            
            for idx, pred in enumerate(preds):
                dist = float(distances[idx, pred])
                results.append({
                    "prediction": f"Cluster {pred}",
                    "cluster_id": int(pred),
                    "distance_to_centroid": dist,
                    "explanation": f"Assigned to Cluster {pred}. Centroid distance is {dist:.2f}."
                })
                
        # 4. Regression / Forecasting (Prophet & standard regressors)
        else:
            if type(model).__name__ == "ProphetWrapper":
                date_col = preprocessor.date_cols[0] if preprocessor.date_cols else "date"
                df_prophet = pd.DataFrame({
                    "ds": pd.to_datetime(df[date_col])
                })
                forecast = model.model.predict(df_prophet)
                preds = forecast["yhat"].values
                yhat_lower = forecast["yhat_lower"].values
                yhat_upper = forecast["yhat_upper"].values
                for idx, pred in enumerate(preds):
                    val = float(pred)
                    lower = float(yhat_lower[idx])
                    upper = float(yhat_upper[idx])
                    results.append({
                        "prediction": val,
                        "confidence_lower": max(0.0, lower),
                        "confidence_upper": upper,
                        "explanation": f"Forecasted value is {val:,.2f} (Bounds: {max(0.0, lower):,.2f} - {upper:,.2f})."
                    })
            else:
                preds = model.predict(X)
                z = 1.96
                margin = float(np.std(preds) * 0.1) if len(preds) > 1 else float(preds[0] * 0.1)
                if margin == 0:
                    margin = 10.0
                    
                for idx, pred in enumerate(preds):
                    val = float(pred)
                    results.append({
                        "prediction": val,
                        "confidence_lower": max(0.0, val - z * margin),
                        "confidence_upper": val + z * margin,
                        "explanation": f"Forecasted value is {val:,.2f} (Bounds: {max(0.0, val - z * margin):,.2f} - {val + z * margin:,.2f})."
                    })

                
        return {
            "model_name": model_name,
            "predictions": results
        }
