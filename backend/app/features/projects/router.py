import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.projects.models import Project
from app.features.projects.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from app.features.projects.repository import project_repo
from app.features.datasets.models import Dataset
from app.features.datasets.schemas import DatasetResponse
from app.features.datasets.repository import dataset_repo
from app.features.datasets.service import DatasetService
from app.features.datasets.router import analyze_file_schema, UPLOADED_PATHS_CACHE
from app.core.cache import cache_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


def sanitize_table_name(project_id: str, name: str) -> str:
    """Creates a deterministic, SQL-safe, project-isolated DuckDB table identifier."""
    clean_proj_id = project_id.replace("-", "_").lower()
    clean_name = name.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
    clean_name = "".join(c for c in clean_name if c.isalnum() or c == "_")
    return f"project_{clean_proj_id}_{clean_name}"


async def get_project_and_verify_access(
    project_id: str,
    current_user: MockUser,
    db: AsyncSession,
) -> Project:
    """Helper to fetch a project and verify that the current user has access to it."""
    project = await project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project does not exist."
        )
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project."
        )
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Creates a new project for the authenticated user."""
    import time
    start_time = time.perf_counter()
    project_id = f"proj-{uuid.uuid4().hex[:8]}"
    logger.info(f"PROJECT_CREATE_STARTED: project_id={project_id} user_id={current_user.id} name='{payload.name}'")
    
    try:
        logger.info(f"PROJECT_CREATE_AUTHENTICATED: user_id={current_user.id} role={current_user.role}")
        
        # 1. Ensure user record exists in database (prevents foreign key owner_id failure)
        from app.features.auth.models import User
        stmt = select(User).where(User.id == current_user.id)
        result = await db.execute(stmt)
        user_in_db = result.scalars().first()
        if not user_in_db:
            user_in_db = User(
                id=current_user.id,
                email=current_user.email,
                name=current_user.name,
                role=current_user.role,
                is_active=True,
                hashed_password="dev_auth_bypass_hash"
            )
            db.add(user_in_db)
            await db.flush()

        # 2. Insert project record into database
        project_data = {
            "id": project_id,
            "name": payload.name,
            "description": payload.description,
            "owner_id": current_user.id,
            "status": payload.status or "Active",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        logger.info(f"PROJECT_CREATE_DB_INSERT: project_id={project_id} owner_id={current_user.id}")
        db_item = await project_repo.create(db, obj_in=project_data)
        logger.info(f"PROJECT_CREATE_DB_COMMITTED: project_id={project_id}")
        
        # 3. Invalidate projects cache
        try:
            await cache_client.invalidate_pattern(f"projects:{current_user.id}:*")
            logger.info(f"PROJECT_CREATE_CACHE_INVALIDATED: user_id={current_user.id}")
        except Exception as cache_err:
            logger.warning(f"Cache invalidation non-fatal warning: {cache_err}")

        duration = time.perf_counter() - start_time
        logger.info(f"PROJECT_CREATE_SUCCESS: project_id={project_id} user_id={current_user.id} duration={duration:.4f}s")
        
        return ProjectResponse(
            id=db_item.id,
            name=db_item.name,
            description=db_item.description,
            owner_id=db_item.owner_id,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
            datasetsCount=0,
            dataset_count=0,
            status=db_item.status
        )
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"PROJECT_CREATE_FAILED: project_id={project_id} user_id={current_user.id} duration={duration:.4f}s error='{str(e)}'")
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[ProjectResponse]:
    """Lists all projects owned by the authenticated user."""
    import time
    start_time = time.perf_counter()
    logger.info(f"PROJECT_LIST_STARTED: user_id={current_user.id}")
    
    try:
        from sqlalchemy import func
        
        result = await db.execute(select(Project).where(Project.owner_id == current_user.id).order_by(Project.created_at.desc()))
        projects = result.scalars().all()
        
        res_list = []
        for p in projects:
            ds_stmt = select(func.count(Dataset.id)).where(Dataset.project_id == p.id)
            ds_res = await db.execute(ds_stmt)
            count = ds_res.scalar() or 0
            
            res_list.append(
                ProjectResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    owner_id=p.owner_id,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    datasetsCount=count,
                    dataset_count=count,
                    status=getattr(p, "status", "Active")
                )
            )
        duration = time.perf_counter() - start_time
        logger.info(f"PROJECT_LIST_SUCCESS: user_id={current_user.id} count={len(res_list)} duration={duration:.4f}s")
        return res_list
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"PROJECT_LIST_FAILED: user_id={current_user.id} duration={duration:.4f}s error='{str(e)}'")
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}"
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Retrieves project details after verifying access."""
    project = await get_project_and_verify_access(project_id, current_user, db)
    
    from sqlalchemy import func
    ds_stmt = select(func.count(Dataset.id)).where(Dataset.project_id == project_id)
    ds_res = await db.execute(ds_stmt)
    count = ds_res.scalar() or 0
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        datasetsCount=count,
        dataset_count=count,
        status=getattr(project, "status", "Active")
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Updates an existing project owned by the user."""
    project = await get_project_and_verify_access(project_id, current_user, db)
    updated = await project_repo.update(db, db_obj=project, obj_in=payload)
    
    from sqlalchemy import func
    ds_stmt = select(func.count(Dataset.id)).where(Dataset.project_id == project_id)
    ds_res = await db.execute(ds_stmt)
    count = ds_res.scalar() or 0
    
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        owner_id=updated.owner_id,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        datasetsCount=count,
        dataset_count=count,
        status=getattr(updated, "status", "Active")
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Deletes a project and all associated datasets."""
    project = await get_project_and_verify_access(project_id, current_user, db)
    
    # Fetch and delete associated datasets
    stmt = select(Dataset).where(Dataset.project_id == project_id)
    result = await db.execute(stmt)
    datasets = result.scalars().all()
    for ds in datasets:
        if ds.storage_path and os.path.exists(ds.storage_path):
            try:
                os.remove(ds.storage_path)
            except Exception:
                pass
        await db.delete(ds)
        
    await project_repo.remove(db, id=project_id)
    
    # Clean up UPLOADED_PATHS_CACHE for project datasets
    keys_to_delete = [d_id for d_id, item in UPLOADED_PATHS_CACHE.items() if item.get("project_id") == project_id]
    for key in keys_to_delete:
        UPLOADED_PATHS_CACHE.pop(key, None)

    try:
        await cache_client.invalidate_pattern(f"projects:{current_user.id}:*")
        await cache_client.invalidate_pattern("sql_query:*")
        await cache_client.invalidate_pattern("dashboard_kpi:*")
    except Exception:
        pass

    logger.info(f"project_deleted: project_id={project_id} user_id={current_user.id}")
    return {"status": "success"}


@router.get("/{project_id}/datasets", response_model=List[DatasetResponse])
async def list_project_datasets(
    project_id: str,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[DatasetResponse]:
    """Returns metadata registries for datasets belonging to the specific project."""
    await get_project_and_verify_access(project_id, current_user, db)
    
    stmt = select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at.desc())
    result = await db.execute(stmt)
    db_items = result.scalars().all()
    
    return [
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
            project_id=item.project_id,
            owner_id=item.owner_id,
            original_filename=item.original_filename,
            error_message=item.error_message,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in db_items
    ]


@router.post("/{project_id}/datasets", response_model=DatasetResponse)
async def upload_project_dataset(
    project_id: str,
    file: UploadFile = File(...),
    tableName: Optional[str] = Form(None),
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> DatasetResponse:
    """Handles project-scoped binary multipart uploads, runs analysis, and registers with DuckDB."""
    # 1. Validate project existence and access
    await get_project_and_verify_access(project_id, current_user, db)
    
    # 2. Validate file type
    filename = file.filename or "uploaded_file"
    file_ext = filename.split(".")[-1].lower()
    allowed_extensions = ["csv", "xlsx", "xls", "json", "pdf", "parquet"]
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported formats: {', '.join(allowed_extensions)}"
        )
    
    dataset_id = str(uuid.uuid4())
    import time
    start_time = time.perf_counter()
    logger.info(f"DATASET_UPLOAD_STARTED: dataset_id={dataset_id} project_id={project_id} user_id={current_user.id} filename='{filename}'")
    
    try:
        # Save file to disk
        content = await file.read()
        
        # Max file size: 50MB
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds the maximum limit of 50MB."
            )
            
        file_path = DatasetService.save_uploaded_file(filename, content)
        
        file_size_kb = len(content) / 1024
        size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{(file_size_kb/1024):.1f} MB"
        
        file_type = file_ext.upper()
        if file_type == "XLSX" or file_type == "XLS":
            file_type = "Excel"
            
        # Parse schema and rows via DuckDB
        logger.info(f"duckdb_ingestion_started: dataset_id={dataset_id} path={file_path}")
        rows_count, columns, schema = analyze_file_schema(file_path, file_type)
        logger.info(f"duckdb_ingestion_completed: dataset_id={dataset_id} rows={rows_count}")
        
        # Calculate health score
        # Deduct score for missing values (if any columns have completeness < 100%)
        total_completeness = sum(c.get("completeness", 100.0) for c in schema.values())
        health_score = int(total_completeness / len(schema)) if schema else 100
        
        display_name = tableName.strip() if tableName else os.path.splitext(filename)[0]
        clean_table_name = sanitize_table_name(project_id, display_name)
        from app.core.json_utils import safe_json_dumps
        
        dataset_data = {
            "id": dataset_id,
            "filename": filename,
            "type": file_type,
            "size": size_str,
            "rows": rows_count,
            "qualityScore": health_score,
            "status": "Active",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "workspace_id": current_user.workspace_id,
            "display_name": display_name,
            "storage_path": file_path,
            "duckdb_table": clean_table_name,
            "columns_json": safe_json_dumps(columns),
            "schema_json": safe_json_dumps(schema),
            "project_id": project_id,
            "owner_id": current_user.id,
            "original_filename": filename,
            "error_message": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        db_item = await dataset_repo.create(db, obj_in=dataset_data)
        
        # Cache paths for compatibility
        UPLOADED_PATHS_CACHE[dataset_id] = {
            "path": file_path,
            "filename": filename,
            "type": file_type,
            "size": size_str,
            "rows": rows_count,
            "qualityScore": health_score,
            "status": "Active",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "duckdb_table": clean_table_name,
            "project_id": project_id,
        }
        
        # Invalidate SQL and KPI caches
        await cache_client.invalidate_pattern("sql_query:*")
        await cache_client.invalidate_pattern("dashboard_kpi:*")
        
        duration = time.perf_counter() - start_time
        logger.info(f"DATASET_UPLOAD_SUCCESS: dataset_id={dataset_id} project_id={project_id} user_id={current_user.id} duration={duration:.4f}s")
        
        return DatasetResponse(
            id=dataset_id,
            filename=filename,
            type=file_type,
            size=size_str,
            rows=rows_count,
            qualityScore=health_score,
            status="Active",
            date=datetime.now().strftime("%Y-%m-%d"),
            workspace_id=current_user.workspace_id,
            display_name=display_name,
            storage_path=file_path,
            duckdb_table=clean_table_name,
            columns_json=safe_json_dumps(columns),
            schema_json=safe_json_dumps(schema),
            project_id=project_id,
            owner_id=current_user.id,
            original_filename=filename,
            error_message=None,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at
        )
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"DATASET_UPLOAD_FAILED: dataset_id={dataset_id} project_id={project_id} user_id={current_user.id} duration={duration:.4f}s error='{str(e)}'")
        # Save fail state to DB if possible to prevent orphan files/failed parsing mapping
        try:
            # Cleanup saved file if it exists
            pass
        except Exception:
            pass
            
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingestion failed: {str(e)}"
        )
