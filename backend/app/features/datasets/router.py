from typing import List
import uuid
import os
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.datasets.schemas import DatasetResponse, DatasetDetailsResponse, CleanPayload
from app.features.datasets.service import DatasetService
from app.core.cache import cache_client

router = APIRouter(prefix="/datasets", tags=["Datasets"])

# In-Memory cache for uploaded file paths since we don't commit to DB tables during scaffold mode
UPLOADED_PATHS_CACHE = {}


@router.get("", response_model=List[DatasetResponse])
async def list_datasets(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[DatasetResponse]:
    """Returns all metadata registries for uploaded sheets."""
    # Scaffold default mock return list
    results = [
        DatasetResponse(id="1", filename="q3_financials.xlsx", type="Excel", size="2.4 MB", rows=14020, qualityScore=98, status="Active", date="2026-08-02"),
        DatasetResponse(id="2", filename="customer_churn.csv", type="CSV", size="480 KB", rows=6200, qualityScore=92, status="Active", date="2026-08-01"),
        DatasetResponse(id="3", filename="raw_clicks_logs.json", type="JSON", size="14.8 MB", rows=185000, qualityScore=88, status="Processing", date="2026-08-02"),
        DatasetResponse(id="4", filename="unstructured_invoice.pdf", type="PDF", size="1.2 MB", rows=0, qualityScore=0, status="Active", date="2026-07-29"),
    ]
    
    # Dynamically append uploaded datasets
    for dataset_id, item in UPLOADED_PATHS_CACHE.items():
        results.append(
            DatasetResponse(
                id=dataset_id,
                filename=item["filename"],
                type=item.get("type", item["filename"].split(".")[-1].upper()),
                size=item.get("size", "0 KB"),
                rows=item.get("rows", 0),
                qualityScore=item.get("qualityScore", 100),
                status=item.get("status", "Active"),
                date=item.get("date", datetime.now().strftime("%Y-%m-%d")),
            )
        )
    return results


@router.post("/upload", response_model=DatasetResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    tableName: str = Form(...),
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DatasetResponse:
    """Handles binary multipart uploads and triggers DuckDB parser mappings."""
    try:
        content = await file.read()
        file_path = DatasetService.save_uploaded_file(file.filename, content)
        dataset_id = str(uuid.uuid4())
        
        file_size_kb = len(content) / 1024
        size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{(file_size_kb/1024):.1f} MB"
        
        # Cache path for subsequent describes
        UPLOADED_PATHS_CACHE[dataset_id] = {
            "path": file_path,
            "filename": file.filename,
            "type": file.filename.split(".")[-1].upper(),
            "size": size_str,
            "rows": 0,
            "qualityScore": 100,
            "status": "Active",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

        # Invalidate SQL and KPI caches
        await cache_client.invalidate_pattern("sql_query:*")
        await cache_client.invalidate_pattern("dashboard_kpi:*")

        return DatasetResponse(
            id=dataset_id,
            filename=file.filename,
            type=file.filename.split(".")[-1].upper(),
            size=size_str,
            rows=0,
            qualityScore=100,
            status="Active",
            date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/{id}", response_model=DatasetDetailsResponse)
async def get_dataset_details(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DatasetDetailsResponse:
    """Exposes columns schemas and previews, reading from DuckDB if the file exists on host."""
    cache_item = UPLOADED_PATHS_CACHE.get(id)
    if cache_item:
        return DatasetService.get_csv_duckdb_analysis(
            file_path=cache_item["path"],
            dataset_id=id,
            filename=cache_item["filename"],
        )
    
    # Fallback to general details
    return DatasetService.get_csv_duckdb_analysis("", id, "customer_churn.csv" if id == "2" else "q3_financials.xlsx")


@router.post("/{id}/clean", response_model=DatasetDetailsResponse)
async def clean_dataset(
    id: str,
    payload: CleanPayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DatasetDetailsResponse:
    """Executes cleaning operations (e.g. dropping duplicates or zero fields)."""
    details = await get_dataset_details(id, current_user, db)
    # Modify health metrics as mocked cleaning results
    details.health = 100
    details.missing = 0
    details.duplicates = 0
    
    # Invalidate SQL and KPI caches
    await cache_client.invalidate_pattern("sql_query:*")
    await cache_client.invalidate_pattern("dashboard_kpi:*")
    return details


@router.delete("/{id}")
async def delete_dataset(
    id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Removes a metadata reference and deletes the underlying source file."""
    cache_item = UPLOADED_PATHS_CACHE.pop(id, None)
    if cache_item and os.path.exists(cache_item["path"]):
        os.remove(cache_item["path"])
        
    # Invalidate SQL and KPI caches
    await cache_client.invalidate_pattern("sql_query:*")
    await cache_client.invalidate_pattern("dashboard_kpi:*")
    return {"status": "success"}
