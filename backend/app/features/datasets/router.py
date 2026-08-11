from typing import List, Dict, Any
import uuid
import os
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.datasets.models import Dataset
from app.features.datasets.schemas import DatasetResponse, DatasetDetailsResponse, DatasetSchemaColumn, CleanPayload
from app.features.datasets.service import DatasetService
from app.core.cache import cache_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["Datasets"])

# In-Memory cache for uploaded file paths since we don't commit to DB tables during scaffold mode
UPLOADED_PATHS_CACHE = {}


# Helper to analyze file schema in a schema-intelligent way
def analyze_file_schema(file_path: str, file_type: str):
    from app.core.database import get_duckdb_conn
    import os
    gen = get_duckdb_conn()
    conn = next(gen)
    try:
        file_ext = os.path.splitext(file_path.lower())[1]
        
        # Determine read expression
        read_expr = None
        if file_type == "CSV" or file_ext == ".csv":
            read_expr = f"read_csv_auto('{file_path}')"
        elif file_type == "PARQUET" or file_ext == ".parquet":
            read_expr = f"read_parquet('{file_path}')"
            
        if read_expr:
            # Row count
            rows_count = conn.execute(f"SELECT COUNT(*) FROM {read_expr}").fetchone()[0]
            # Column definitions
            cols_info = conn.execute(f"DESCRIBE SELECT * FROM {read_expr}").fetchall()
            columns = [c[0] for c in cols_info]
            
            schema = {}
            for col in cols_info:
                col_name = col[0]
                col_type = str(col[1])
                
                # Missing values count
                null_count = conn.execute(f"SELECT COUNT(*) - COUNT(\"{col_name}\") FROM {read_expr}").fetchone()[0]
                completeness = 100.0 if rows_count == 0 else float((rows_count - null_count) / rows_count * 100.0)
                
                # Distinct count
                distinct_count = conn.execute(f"SELECT COUNT(DISTINCT \"{col_name}\") FROM {read_expr}").fetchone()[0]
                
                # Max and Min (if numeric/date)
                min_val = None
                max_val = None
                is_numeric = any(t in col_type.upper() for t in ["INT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC"])
                is_date = any(t in col_type.upper() for t in ["DATE", "TIME", "TIMESTAMP"])
                
                if (is_numeric or is_date) and rows_count > 0:
                    try:
                        min_res = conn.execute(f"SELECT MIN(\"{col_name}\"), MAX(\"{col_name}\") FROM {read_expr}").fetchone()
                        if min_res:
                            min_val = str(min_res[0]) if min_res[0] is not None else None
                            max_val = str(min_res[1]) if min_res[1] is not None else None
                    except Exception:
                        pass
                
                # Sample values
                sample_values = []
                if rows_count > 0:
                    try:
                        sample_res = conn.execute(f"SELECT DISTINCT \"{col_name}\" FROM {read_expr} WHERE \"{col_name}\" IS NOT NULL LIMIT 5").fetchall()
                        sample_values = [r[0] for r in sample_res]
                    except Exception:
                        pass
                
                # Categorical determination
                is_categorical = False
                if not is_numeric and not is_date and distinct_count < 100:
                    is_categorical = True
                    
                schema[col_name] = {
                    "type": col_type,
                    "nullable": col[2] == "YES",
                    "completeness": completeness,
                    "missing_count": null_count,
                    "unique_count": distinct_count,
                    "min": min_val,
                    "max": max_val,
                    "sample_values": sample_values,
                    "is_categorical": is_categorical,
                    "is_date": is_date,
                    "is_numeric": is_numeric
                }
                
            return rows_count, columns, schema
            
        elif file_type in ("EXCEL", "XLSX", "XLS") or file_ext in (".xlsx", ".xls"):
            import pandas as pd
            df = pd.read_excel(file_path)
            rows_count = len(df)
            columns = list(df.columns)
            schema = {}
            for col in df.columns:
                col_type = str(df[col].dtype)
                null_count = int(df[col].isna().sum())
                completeness = 100.0 if rows_count == 0 else float((rows_count - null_count) / rows_count * 100.0)
                distinct_count = int(df[col].nunique())
                
                min_val = None
                max_val = None
                if pd.api.types.is_numeric_dtype(df[col]) and rows_count > 0:
                    min_val = str(df[col].min()) if not pd.isna(df[col].min()) else None
                    max_val = str(df[col].max()) if not pd.isna(df[col].max()) else None
                
                sample_values = df[col].dropna().unique()[:5].tolist()
                sample_values = [str(v) for v in sample_values]
                
                schema[str(col)] = {
                    "type": col_type,
                    "nullable": True,
                    "completeness": completeness,
                    "missing_count": null_count,
                    "unique_count": distinct_count,
                    "min": min_val,
                    "max": max_val,
                    "sample_values": sample_values,
                    "is_categorical": not pd.api.types.is_numeric_dtype(df[col]) and distinct_count < 100,
                    "is_date": "date" in col_type.lower() or "datetime" in col_type.lower(),
                    "is_numeric": pd.api.types.is_numeric_dtype(df[col])
                }
            return rows_count, columns, schema
            
        elif file_type == "JSON" or file_ext == ".json":
            import pandas as pd
            df = pd.read_json(file_path)
            rows_count = len(df)
            columns = list(df.columns)
            schema = {}
            for col in df.columns:
                col_type = str(df[col].dtype)
                null_count = int(df[col].isna().sum())
                completeness = 100.0 if rows_count == 0 else float((rows_count - null_count) / rows_count * 100.0)
                distinct_count = int(df[col].nunique())
                
                min_val = None
                max_val = None
                if pd.api.types.is_numeric_dtype(df[col]) and rows_count > 0:
                    min_val = str(df[col].min()) if not pd.isna(df[col].min()) else None
                    max_val = str(df[col].max()) if not pd.isna(df[col].max()) else None
                
                sample_values = df[col].dropna().unique()[:5].tolist()
                sample_values = [str(v) for v in sample_values]
                
                schema[str(col)] = {
                    "type": col_type,
                    "nullable": True,
                    "completeness": completeness,
                    "missing_count": null_count,
                    "unique_count": distinct_count,
                    "min": min_val,
                    "max": max_val,
                    "sample_values": sample_values,
                    "is_categorical": not pd.api.types.is_numeric_dtype(df[col]) and distinct_count < 100,
                    "is_date": "date" in col_type.lower() or "datetime" in col_type.lower(),
                    "is_numeric": pd.api.types.is_numeric_dtype(df[col])
                }
            return rows_count, columns, schema
            
    except Exception as e:
        logger.error(f"Error in analyze_file_schema: {e}")
    finally:
        try:
            gen.close()
        except Exception:
            pass
    return 0, [], {}


@router.get("", response_model=List[DatasetResponse])
async def list_datasets(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[DatasetResponse]:
    """Returns all metadata registries for uploaded sheets."""
    stmt = select(Dataset).where(
        (Dataset.workspace_id == current_user.workspace_id) | (Dataset.workspace_id == "default")
    )
    result = await db.execute(stmt)
    db_items = list(result.scalars().all())
    
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
                date=item.date,
                workspace_id=item.workspace_id,
                display_name=item.display_name,
                storage_path=item.storage_path,
                duckdb_table=item.duckdb_table,
                columns_json=item.columns_json,
                schema_json=item.schema_json,
                created_at=item.created_at,
                updated_at=item.updated_at
            )
        )
        
    # Dynamically append default mocks if they don't exist in DB
    default_ids = {item.id for item in db_items}
    default_mocks = [
        DatasetResponse(id="1", filename="q3_financials.xlsx", type="Excel", size="2.4 MB", rows=14020, qualityScore=98, status="Active", date="2026-08-02", workspace_id="default", display_name="q3_financials", duckdb_table="q3_financials"),
        DatasetResponse(id="2", filename="customer_churn.csv", type="CSV", size="480 KB", rows=6200, qualityScore=92, status="Active", date="2026-08-01", workspace_id="default", display_name="customer_churn", duckdb_table="customer_churn"),
        DatasetResponse(id="3", filename="raw_clicks_logs.json", type="JSON", size="14.8 MB", rows=185000, qualityScore=88, status="Processing", date="2026-08-02", workspace_id="default", display_name="raw_clicks_logs", duckdb_table="raw_clicks_logs"),
        DatasetResponse(id="4", filename="unstructured_invoice.pdf", type="PDF", size="1.2 MB", rows=0, qualityScore=0, status="Active", date="2026-07-29", workspace_id="default", display_name="unstructured_invoice", duckdb_table="unstructured_invoice"),
    ]
    for mock_item in default_mocks:
        if mock_item.id not in default_ids:
            results.append(mock_item)
            
    return results


@router.post("/upload", response_model=DatasetResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    tableName: str = Form(...),
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
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
            "workspace_id": current_user.workspace_id,  # Workspace association
            "display_name": tableName or os.path.splitext(file.filename)[0],
            "storage_path": file_path,
            "duckdb_table": clean_table_name,
            "columns_json": json.dumps(columns),
            "schema_json": json.dumps(schema),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
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
            workspace_id=current_user.workspace_id,
            display_name=tableName or os.path.splitext(file.filename)[0],
            storage_path=file_path,
            duckdb_table=clean_table_name,
            columns_json=json.dumps(columns),
            schema_json=json.dumps(schema),
            created_at=db_item.created_at,
            updated_at=db_item.updated_at
        )
    except Exception as e:
        logger.error(f"Upload error: {e}")
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
    import json
    
    item = await dataset_repo.get(db, id)
    if item:
        if item.workspace_id != current_user.workspace_id and item.workspace_id != "default":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this dataset."
            )
        # Load preview from DuckDB
        preview_rows = []
        cols_count = 0
        if item.storage_path and os.path.exists(item.storage_path):
            from app.core.database import get_duckdb_conn
            conn = next(get_duckdb_conn())
            try:
                # Mount temp view
                from app.features.analytics.service import register_all_datasets_in_duckdb
                register_all_datasets_in_duckdb(conn)
                
                preview_res = conn.execute(f"SELECT * FROM \"{item.duckdb_table}\" LIMIT 5")
                columns = [desc[0] for desc in preview_res.description]
                cols_count = len(columns)
                for row in preview_res.fetchall():
                    row_dict = {}
                    for idx, col_name in enumerate(columns):
                        row_dict[col_name] = row[idx]
                    preview_rows.append(row_dict)
            except Exception as e:
                logger.error(f"Failed to fetch DuckDB preview for details: {e}")
            finally:
                conn.close()
                
        # Parse schema from stored schema_json
        schema_list = []
        if item.schema_json:
            try:
                stored_schema = json.loads(item.schema_json)
                for col_name, info in stored_schema.items():
                    schema_list.append(
                        DatasetSchemaColumn(
                            name=col_name,
                            type=info.get("type", "VARCHAR"),
                            completeness=info.get("completeness", 100.0),
                            distinctValues=info.get("unique_count", 0),
                            nullable=info.get("nullable", True),
                            missing_count=info.get("missing_count", 0),
                            unique_count=info.get("unique_count", 0),
                            min_value=info.get("min"),
                            max_value=info.get("max"),
                            sample_values=info.get("sample_values", [])
                        )
                    )
            except Exception as e:
                logger.error(f"Error parsing schema_json for details: {e}")
                
        if not cols_count and schema_list:
            cols_count = len(schema_list)
            
        return DatasetDetailsResponse(
            id=item.id,
            filename=item.filename,
            size=item.size,
            rows=item.rows,
            cols=cols_count,
            health=item.qualityScore,
            missing=int(item.rows * (1 - item.qualityScore / 100.0)),
            duplicates=0,
            status=item.status,
            schema=schema_list,
            preview=preview_rows,
            workspace_id=item.workspace_id,
            display_name=item.display_name,
            storage_path=item.storage_path,
            duckdb_table=item.duckdb_table,
            created_at=item.created_at,
            updated_at=item.updated_at
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
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
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
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Removes a metadata reference and deletes the underlying source file."""
    from app.features.datasets.repository import dataset_repo
    item = await dataset_repo.get(db, id)
    if item:
        if item.workspace_id != current_user.workspace_id and item.workspace_id != "default":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this dataset."
            )
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
