import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from sklearn.metrics import mean_absolute_error, mean_squared_error, root_mean_squared_error, r2_score
from sklearn.metrics import silhouette_score
from typing import Dict, Any, List, Optional

class EvaluationService:
    """
    Computes standard evaluation metrics for Classification, Regression,
    Clustering, and Anomaly Detection models, outputting machine-readable JSON.
    """
    
    @staticmethod
    def evaluate_classification(
        y_true: np.ndarray, 
        y_pred: np.ndarray, 
        y_prob: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Evaluates classification models (e.g. churn)."""
        acc = float(accuracy_score(y_true, y_pred))
        
        unique_classes = np.unique(y_true)
        is_binary = len(unique_classes) <= 2
        avg = "binary" if is_binary else "macro"
        
        prec = float(precision_score(y_true, y_pred, average=avg, zero_division=0))
        rec = float(recall_score(y_true, y_pred, average=avg, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, average=avg, zero_division=0))
        
        auc = None
        if y_prob is not None:
            try:
                if is_binary and len(y_prob.shape) > 1 and y_prob.shape[1] > 1:
                    # Select positive class probabilities
                    auc = float(roc_auc_score(y_true, y_prob[:, 1]))
                else:
                    auc = float(roc_auc_score(y_true, y_prob))
            except Exception:
                pass
                
        cm = confusion_matrix(y_true, y_pred).tolist()
        
        return {
            "task_type": "classification",
            "metrics": {
                "accuracy": acc,
                "precision": prec,
                "recall": rec,
                "f1_score": f1,
                "roc_auc": auc
            },
            "confusion_matrix": cm
        }
        
    @staticmethod
    def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
        """Evaluates regression or forecasting models."""
        mae = float(mean_absolute_error(y_true, y_pred))
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(root_mean_squared_error(y_true, y_pred))
        r2 = float(r2_score(y_true, y_pred))
        
        # Calculate MAPE (Mean Absolute Percentage Error)
        mask = y_true != 0
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if np.sum(mask) > 0 else 0.0
        
        return {
            "task_type": "regression",
            "metrics": {
                "mae": mae,
                "mse": mse,
                "rmse": rmse,
                "r2_score": r2,
                "mape": mape
            }
        }
        
    @staticmethod
    def evaluate_clustering(X: np.ndarray, labels: np.ndarray) -> Dict[str, Any]:
        """Evaluates clustering models (e.g. segmentation)."""
        unique_labels = np.unique(labels)
        n_clusters = len(unique_labels)
        
        sil = None
        if 1 < n_clusters < len(X):
            try:
                # Sample dataset if large to save computation time
                if len(X) > 2000:
                    np.random.seed(42)
                    indices = np.random.choice(len(X), 2000, replace=False)
                    sil = float(silhouette_score(X[indices], labels[indices]))
                else:
                    sil = float(silhouette_score(X, labels))
            except Exception:
                pass
                
        sizes = {}
        for lbl in unique_labels:
            sizes[str(lbl)] = int(np.sum(labels == lbl))
            
        return {
            "task_type": "clustering",
            "metrics": {
                "num_clusters": n_clusters,
                "silhouette_score": sil
            },
            "cluster_sizes": sizes
        }
        
    @staticmethod
    def evaluate_anomaly(labels: np.ndarray) -> Dict[str, Any]:
        """Evaluates anomaly detection models (1 = normal, -1 = outlier)."""
        total_samples = len(labels)
        anomaly_count = int(np.sum(labels == -1))
        anomaly_ratio = float(anomaly_count / total_samples) if total_samples > 0 else 0.0
        
        return {
            "task_type": "anomaly_detection",
            "metrics": {
                "total_samples": total_samples,
                "anomaly_count": anomaly_count,
                "anomaly_ratio": anomaly_ratio
            }
        }
