from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class PredictPayload(BaseModel):
    model_name: str = Field(..., description="Registered ML model identifier", examples=["churn_forecast_rf"])
    inputs: List[Dict[str, Any]] = Field(..., description="Batch records payload for model classification", examples=[[{"age": 34, "tenure": 5, "monthly_charges": 70.0}]])
    version: Optional[int] = Field(None, description="Optional specific model version integer", examples=[1, 2])
    stage: Optional[str] = Field(None, description="Optional target environment registry stage", examples=["Production", "Staging"])

class TrainPayload(BaseModel):
    model_type: str = Field(..., description="Model type class category", examples=["forecast", "churn"])
    dataset_id: str = Field(..., description="Target dataset reference ID to feed training", examples=["active_sales_2026"])
    config: Dict[str, Any] = Field(..., description="Hyperparameter dict overrides", examples=[{"n_estimators": 100, "max_depth": 6}])
    background: bool = Field(True, description="Enable Celery background execution pipeline")

class PromotePayload(BaseModel):
    model_name: str = Field(..., description="Model registration identifier", examples=["churn_forecast_rf"])
    version: int = Field(..., description="Target version number to promote", examples=[1, 2])
    stage: str = Field(..., description="Target environment stage name", examples=["Production", "Staging"])
