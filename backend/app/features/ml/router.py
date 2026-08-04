from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional

from app.core.dependencies import get_current_user, MockUser
from app.features.ml.schemas import PredictPayload, TrainPayload, PromotePayload
from app.features.ml.inference import InferenceService
from app.features.ml.registry import ModelRegistryService
from app.features.ml.tasks import retrain_model_task

router = APIRouter(prefix="/ml", tags=["ML Platform Operations"])

@router.post("/predict")
async def run_prediction(
    payload: PredictPayload,
    current_user: MockUser = Depends(get_current_user)
):
    """Executes single or batch inference against a registered model by version or stage."""
    try:
        inf_svc = InferenceService()
        res = inf_svc.predict(
            model_name=payload.model_name,
            inputs=payload.inputs,
            version=payload.version,
            stage=payload.stage
        )
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inference failed: {str(e)}"
        )

@router.post("/train")
async def trigger_training(
    payload: TrainPayload,
    current_user: MockUser = Depends(get_current_user)
):
    """Triggers retraining of an ML model type, either synchronously or asynchronously via Celery."""
    try:
        if payload.background:
            task = retrain_model_task.delay(
                model_type=payload.model_type,
                dataset_id=payload.dataset_id,
                config=payload.config
            )
            return {
                "status": "queued",
                "task_id": task.id,
                "detail": "Model retraining has been queued in Celery worker background."
            }
        else:
            res = retrain_model_task(
                model_type=payload.model_type,
                dataset_id=payload.dataset_id,
                config=payload.config
            )
            if res.get("status") == "failed":
                raise ValueError(res.get("error"))
            return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Retraining failed: {str(e)}"
        )

@router.get("/models")
async def list_registered_models(
    current_user: MockUser = Depends(get_current_user)
):
    """Lists all registered models, versions, and current stages from the Model Registry."""
    try:
        registry = ModelRegistryService()
        return registry.list_models()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to list models: {str(e)}"
        )

@router.post("/models/promote")
async def promote_model_version(
    payload: PromotePayload,
    current_user: MockUser = Depends(get_current_user)
):
    """Promotes a registered model version to Staging or Production."""
    try:
        registry = ModelRegistryService()
        res = registry.promote_model(
            model_name=payload.model_name,
            version=payload.version,
            stage=payload.stage
        )
        try:
            from app.core.cache import cache_client
            await cache_client.invalidate_pattern(f"ml_predict:{payload.model_name}:*")
        except Exception:
            pass
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to promote model version: {str(e)}"
        )
