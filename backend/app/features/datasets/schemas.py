from typing import Any, Dict, List, Optional
from datetime import datetime
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
    
    workspace_id: Optional[str] = None
    display_name: Optional[str] = None
    storage_path: Optional[str] = None
    duckdb_table: Optional[str] = None
    columns_json: Optional[str] = None
    schema_json: Optional[str] = None
    project_id: Optional[str] = None
    owner_id: Optional[str] = None
    original_filename: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DatasetSchemaColumn(BaseModel):
    name: str
    type: str
    completeness: float
    distinctValues: int
    nullable: Optional[bool] = True
    missing_count: Optional[int] = 0
    unique_count: Optional[int] = 0
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    sample_values: Optional[List[Any]] = None


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
    
    workspace_id: Optional[str] = None
    display_name: Optional[str] = None
    storage_path: Optional[str] = None
    duckdb_table: Optional[str] = None
    project_id: Optional[str] = None
    owner_id: Optional[str] = None
    original_filename: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class CleanPayload(BaseModel):
    actions: List[str]
