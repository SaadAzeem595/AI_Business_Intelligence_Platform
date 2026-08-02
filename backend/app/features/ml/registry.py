import os
import mlflow
from mlflow.tracking import MlflowClient
import joblib
from typing import Dict, Any, List, Optional, Tuple
from app.features.ml.preprocessing import PreprocessingService
from app.features.ml.tracking import TrackingService

class ModelRegistryService:
    """
    Manages model registration, versioning, promotion stages, loading models,
    and rollback using the MLflow Model Registry backend.
    """
    
    def __init__(self):
        TrackingService.init_mlflow()
        self.client = MlflowClient()
        
    def register_model(
        self, 
        model_name: str, 
        run_id: str, 
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Registers a model version from a completed training run."""
        model_name = model_name.strip()
        
        # Ensure registered model name exists
        try:
            self.client.create_registered_model(model_name)
        except Exception:
            # Model registration already exists
            pass
            
        # Register the model version from the run's logged model path
        model_uri = f"runs:/{run_id}/model"
        version_info = self.client.create_model_version(
            name=model_name,
            source=model_uri,
            run_id=run_id,
            description=description
        )
        
        return {
            "name": model_name,
            "version": int(version_info.version),
            "stage": str(version_info.current_stage),
            "run_id": run_id,
            "status": str(version_info.status)
        }
        
    def promote_model(self, model_name: str, version: int, stage: str) -> Dict[str, Any]:
        """Promotes a model version to a stage (e.g. Staging, Production, Archived)."""
        stage = stage.strip().capitalize()
        if stage not in ["Staging", "Production", "Archived", "None"]:
            raise ValueError(f"Invalid stage '{stage}'. Must be Staging, Production, Archived, or None.")
            
        version_info = self.client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage=stage,
            archive_existing_versions=(stage == "Production") # demotes previous production models
        )
        
        return {
            "name": model_name,
            "version": int(version_info.version),
            "stage": str(version_info.current_stage)
        }
        
    def load_model_and_preprocessor(
        self, 
        model_name: str, 
        version: Optional[int] = None, 
        stage: Optional[str] = None
    ) -> Tuple[Any, PreprocessingService]:
        """Loads both the model and preprocessor artifacts by version or stage."""
        model_name = model_name.strip()
        
        # If both are omitted, default to the Production stage
        if version is None and stage is None:
            stage = "Production"
            
        # Find model version info
        if version is not None:
            v_info = self.client.get_model_version(model_name, str(version))
        else:
            stage = stage.strip().capitalize()
            # Fetch all versions and find matching stage
            versions = self.client.get_latest_versions(model_name, [stage])
            if not versions:
                # If no latest version in this stage, fall back to the absolute latest version
                all_versions = self.client.search_model_versions(f"name='{model_name}'")
                if not all_versions:
                    raise FileNotFoundError(f"No registered model found with name: '{model_name}'")
                v_info = all_versions[0] # Search returns newest first
            else:
                v_info = versions[0]
                
        run_id = v_info.run_id
        
        # Download artifacts locally
        model_dir = self.client.download_artifacts(run_id, "model")
        prep_dir = self.client.download_artifacts(run_id, "preprocessor")
        
        # Load serialized joblib files
        model = joblib.load(os.path.join(model_dir, "model.joblib"))
        preprocessor = PreprocessingService.load(os.path.join(prep_dir, "preprocessor.joblib"))
        
        return model, preprocessor
        
    def list_models(self) -> List[Dict[str, Any]]:
        """Lists all registered models and their versions."""
        registered_models = self.client.search_registered_models()
        results = []
        
        for rm in registered_models:
            versions = []
            for mv in rm.latest_versions:
                versions.append({
                    "version": int(mv.version),
                    "stage": str(mv.current_stage),
                    "run_id": str(mv.run_id),
                    "last_updated": mv.last_updated_timestamp
                })
            results.append({
                "name": str(rm.name),
                "description": str(rm.description),
                "versions": versions
            })
        return results
        
    def rollback_stage(self, model_name: str, version: int) -> Dict[str, Any]:
        """Rollbacks/promotes a specific version back to active Production."""
        return self.promote_model(model_name, version, "Production")
