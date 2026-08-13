from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "Active"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    created_at: datetime
    updated_at: datetime
    datasetsCount: Optional[int] = 0
    dataset_count: Optional[int] = 0
    status: str = "Active"

    model_config = ConfigDict(from_attributes=True)
