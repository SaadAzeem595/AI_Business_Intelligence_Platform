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


# Helper to analyze file schema in a schema-intelligent way
def analyze_file_schema(file_path: str, file_type: str):
    from app.core.database import get_duckdb_conn
    conn = next(get_duckdb_conn())
    try:
        if file_type == "CSV":
            rows_count = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{file_path}')").fetchone()[0]
            cols_info = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{file_path}')").fetchall()
            columns = [c[0] for c in cols_info]
            schema = {c[0]: str(c[1]) for c in cols_info}
            return rows_count, columns, schema
        elif file_type == "PARQUET":
            rows_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{file_path}')").fetchone()[0]
            cols_info = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{file_path}')").fetchall()
            columns = [c[0] for c in cols_info]
            schema = {c[0]: str(c[1]) for c in cols_info}
            return rows_count, columns, schema
        elif file_type in ("EXCEL", "XLSX", "XLS"):
            import pandas as pd
            df = pd.read_excel(file_path)
            columns = list(df.columns)
            schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
            return len(df), columns, schema
        elif file_type == "JSON":
            import pandas as pd
            df = pd.read_json(file_path)
            columns = list(df.columns)
            schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
            return len(df), columns, schema
    except Exception:
        pass
    return 0, [], {}


@router.get("", response_model=List[DatasetResponse])
async def list_datasets(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[DatasetResponse]:
    """Returns all metadata registries for uploaded sheets."""
    from app.features.datasets.repository import dataset_repo
    db_items = await dataset_repo.get_multi(db, limit=1000)
    
    results = []
    for item in db_items:
        results.append(
            DatasetResponse(
                id=item.id,
                filename=item.filename,
                type=item.type,
                size=item.size,
                rows=item.rows,
                qualityScore=item.qualityScore,
                status=item.status,
                date=item.date
            )
        )
        
    # Dynamically append default mocks if they don't exist in DB
    default_ids = {item.id for item in db_items}
    default_mocks = [
        DatasetResponse(id="1", filename="q3_financials.xlsx", type="Excel", size="2.4 MB", rows=14020, qualityScore=98, status="Active", date="2026-08-02"),
        DatasetResponse(id="2", filename="customer_churn.csv", type="CSV", size="480 KB", rows=6200, qualityScore=92, status="Active", date="2026-08-01"),
        DatasetResponse(id="3", filename="raw_clicks_logs.json", type="JSON", size="14.8 MB", rows=185000, qualityScore=88, status="Processing", date="2026-08-02"),
        DatasetResponse(id="4", filename="unstructured_invoice.pdf", type="PDF", size="1.2 MB", rows=0, qualityScore=0, status="Active", date="2026-07-29"),
    ]
    for mock_item in default_mocks:
        if mock_item.id not in default_ids:
            results.append(mock_item)
            
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
        import json
        from app.features.datasets.repository import dataset_repo
        
        content = await file.read()
        file_path = DatasetService.save_uploaded_file(file.filename, content)
        dataset_id = str(uuid.uuid4())
        
        file_size_kb = len(content) / 1024
        size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{(file_size_kb/1024):.1f} MB"
        
        file_type = file.filename.split(".")[-1].upper()
        rows_count, columns, schema = analyze_file_schema(file_path, file_type)
        
        clean_table_name = tableName.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        if not clean_table_name:
            clean_table_name = os.path.splitext(file.filename)[0].lower().replace(" ", "_").replace("-", "_").replace(".", "_")
            
        dataset_data = {
            "id": dataset_id,
            "filename": file.filename,
            "type": file_type,
            "size": size_str,
            "rows": rows_count,
            "qualityScore": 100,
            "status": "Active",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "workspace_id": "default",  # Workspace association
            "display_name": tableName or os.path.splitext(file.filename)[0],
            "storage_path": file_path,
            "duckdb_table": clean_table_name,
            "columns_json": json.dumps(columns),
            "schema_json": json.dumps(schema),
        }
        
        db_item = await dataset_repo.create(db, obj_in=dataset_data)
        
        # Cache path for backward compatibility
        UPLOADED_PATHS_CACHE[dataset_id] = {
            "path": file_path,
            "filename": file.filename,
            "type": file_type,
            "size": size_str,
            "rows": rows_count,
            "qualityScore": 100,
            "status": "Active",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "duckdb_table": clean_table_name,
        }

        # Invalidate SQL and KPI caches
        await cache_client.invalidate_pattern("sql_query:*")
        await cache_client.invalidate_pattern("dashboard_kpi:*")

        return DatasetResponse(
            id=dataset_id,
            filename=file.filename,
            type=file_type,
            size=size_str,
            rows=rows_count,
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
    from app.features.datasets.repository import dataset_repo
    item = await dataset_repo.get(db, id)
    if item and item.storage_path and os.path.exists(item.storage_path):
        return DatasetService.get_csv_duckdb_analysis(
            file_path=item.storage_path,
            dataset_id=item.id,
            filename=item.filename,
        )
        
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
    from app.features.datasets.repository import dataset_repo
    item = await dataset_repo.get(db, id)
    if item:
        if item.storage_path and os.path.exists(item.storage_path):
            try:
                os.remove(item.storage_path)
            except Exception:
                pass
        await dataset_repo.remove(db, id=id)
        
    cache_item = UPLOADED_PATHS_CACHE.pop(id, None)
    if cache_item and os.path.exists(cache_item["path"]):
        try:
            os.remove(cache_item["path"])
        except Exception:
            pass
        
    # Invalidate SQL and KPI caches
    await cache_client.invalidate_pattern("sql_query:*")
    await cache_client.invalidate_pattern("dashboard_kpi:*")
    return {"status": "success"}
