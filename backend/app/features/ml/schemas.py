from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class PredictPayload(BaseModel):
    model_name: str
    inputs: List[Dict[str, Any]]
    version: Optional[int] = None
    stage: Optional[str] = None

class TrainPayload(BaseModel):
    model_type: str
    dataset_id: str
    config: Dict[str, Any]
    background: bool = True

class PromotePayload(BaseModel):
    model_name: str
    version: int
    stage: str
