from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DatasetResponse(BaseModel):
    id: str
    filename: str
    type: str
    size: str
    rows: int
    qualityScore: int
    status: str
    date: str

    model_config = ConfigDict(from_attributes=True)


class DatasetSchemaColumn(BaseModel):
    name: str
    type: str
    completeness: float
    distinctValues: int


class DatasetDetailsResponse(BaseModel):
    id: str
    filename: str
    size: str
    rows: int
    cols: int
    health: int
    missing: int
    duplicates: int
    status: str
    dataset_schema: List[DatasetSchemaColumn] = Field(..., alias="schema")
    preview: List[Dict[str, Any]]

    model_config = ConfigDict(populate_by_name=True)


class CleanPayload(BaseModel):
    actions: List[str]
