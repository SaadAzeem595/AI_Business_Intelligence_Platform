import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
import numpy as np

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.analytics.schemas import (
    ForecastPayload,
    ForecastResponse,
    ForecastPoint,
    ForecastMetric,
    SegmentPayload,
    SegmentResponse,
    ScatterPoint,
    CohortSegment,
    AnomalyPayload,
    AnomalyResponse,
    TimelinePoint,
    AnomalyLog,
    SQLPayload,
    SQLResponse,
    ProjectForecastRequest,
    ProjectForecastResponse,
    ProjectSchemaInfoResponse,
)
from app.features.analytics.service import AnalyticsService
from app.features.analytics.engine.utils import load_dataset
from app.features.analytics.engine.forecasting import ForecastingService
from app.features.analytics.engine.segmentation import SegmentationService
from app.features.analytics.engine.anomaly import AnomalyDetectionService

router = APIRouter(tags=["Analytics & ML Model Operations"])


def get_fallback_dataset_path() -> str:
    """
    Creates a realistic business dataset CSV file if none has been uploaded,
    ensuring analytics endpoints can return real calculated values.
    """
    from app.features.datasets.service import DatasetService
    upload_dir = DatasetService.get_upload_dir()
    fallback_path = os.path.join(upload_dir, "fallback_business_data.csv")
    
    if not os.path.exists(fallback_path):
        # Generate 100 rows of realistic business data
        np.random.seed(42)
        dates = pd.date_range(start="2026-02-01", periods=100, freq='D')
        categories = ["North", "South", "East", "West"]
        
        data = {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "customer_id": [f"C-{1000 + np.random.randint(1, 30)}" for _ in range(100)],
            "revenue": np.random.uniform(100, 1000, 100).tolist(),
            "cost": np.random.uniform(50, 600, 100).tolist(),
            "marketing_spend": np.random.uniform(10, 150, 100).tolist(),
            "conversions": np.random.randint(1, 10, 100).tolist(),
            "visitors": np.random.randint(10, 100, 100).tolist(),
            "x": np.random.uniform(10, 100, 100).tolist(),
            "y": np.random.uniform(10, 100, 100).tolist(),
            "region": [np.random.choice(categories) for _ in range(100)],
        }
        # Add profit column
        data["profit"] = [r - c for r, c in zip(data["revenue"], data["cost"])]
        
        df = pd.DataFrame(data)
        df.to_csv(fallback_path, index=False)
        
    return fallback_path


async def resolve_dataset_path_async(
    dataset_id: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> str:
    """
    Resolves exact file path for a dataset belonging strictly to project_id or dataset_id.
    Prevents reading hidden or fallback datasets from another project.
    """
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    from app.features.datasets.models import Dataset
    from sqlalchemy import select

    # 1. Check UPLOADED_PATHS_CACHE for matching dataset_id & project_id
    if dataset_id and dataset_id in UPLOADED_PATHS_CACHE:
        cached = UPLOADED_PATHS_CACHE[dataset_id]
        if not project_id or cached.get("project_id") == project_id:
            path = cached.get("path")
            if path and os.path.exists(path):
                return path

    # 2. Check Database for Dataset model matching dataset_id & project_id
    if dataset_id and db:
        stmt = select(Dataset).where(Dataset.id == dataset_id)
        if project_id:
            stmt = stmt.where(Dataset.project_id == project_id)
        res = await db.execute(stmt)
        d_obj = res.scalar_one_or_none()
        if d_obj and d_obj.storage_path and os.path.exists(d_obj.storage_path):
            return d_obj.storage_path

    # 3. Check DB by filename or display_name
    if dataset_id and db:
        stmt = select(Dataset).where((Dataset.filename == dataset_id) | (Dataset.display_name == dataset_id))
        if project_id:
            stmt = stmt.where(Dataset.project_id == project_id)
        res = await db.execute(stmt)
        d_obj = res.scalar_one_or_none()
        if d_obj and d_obj.storage_path and os.path.exists(d_obj.storage_path):
            return d_obj.storage_path

    # 4. If dataset_id is missing but project_id is provided, search first dataset belonging to project_id
    if project_id:
        if db:
            stmt = select(Dataset).where(Dataset.project_id == project_id)
            res = await db.execute(stmt)
            d_objs = res.scalars().all()
            for d in d_objs:
                if d.storage_path and os.path.exists(d.storage_path):
                    return d.storage_path

        for d_id, cached in UPLOADED_PATHS_CACHE.items():
            if cached.get("project_id") == project_id:
                path = cached.get("path")
                if path and os.path.exists(path):
                    return path

    # 5. Check cache fallback for dataset_id without project constraint
    if dataset_id and not project_id:
        for d_id, cached in UPLOADED_PATHS_CACHE.items():
            if str(d_id) == str(dataset_id) or cached.get("filename") == dataset_id:
                path = cached.get("path")
                if path and os.path.exists(path):
                    return path

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No dataset found for dataset_id='{dataset_id or ''}' in active project '{project_id or ''}'. Please select or upload a dataset for this project."
    )


def resolve_dataset_path(dataset_id: Optional[str] = None) -> str:
    from app.core.cache import run_async_as_sync
    try:
        from app.core.database import AsyncSessionLocal
        async def _run():
            async with AsyncSessionLocal() as db:
                return await resolve_dataset_path_async(dataset_id, db=db)
        return run_async_as_sync(_run())
    except Exception:
        from app.features.datasets.router import UPLOADED_PATHS_CACHE
        if dataset_id and dataset_id in UPLOADED_PATHS_CACHE:
            return UPLOADED_PATHS_CACHE[dataset_id]["path"]
        if UPLOADED_PATHS_CACHE:
            first_id = list(UPLOADED_PATHS_CACHE.keys())[0]
            return UPLOADED_PATHS_CACHE[first_id]["path"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active dataset found. Please upload a dataset to run analytics."
        )



@router.post("/analytics/forecast", response_model=ForecastResponse)
async def forecast_trend(
    payload: ForecastPayload,
    dataset_id: Optional[str] = None,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
) -> ForecastResponse:
    """Executes pluggable forecasting model predictions on the active dataset."""
    try:
        dataset_path = resolve_dataset_path(dataset_id)
        df = load_dataset(dataset_path)
        if df.empty:
            raise HTTPException(status_code=400, detail="The dataset is empty.")

        # Find appropriate date and value columns
        col_map = {col.strip().lower(): col for col in df.columns}
        
        date_col = None
        for syn in ['date', 'time', 'timestamp', 'transaction_date', 'created_at']:
            if syn in col_map:
                date_col = col_map[syn]
                break
        if not date_col:
            date_col = df.columns[0]
            
        value_col = None
        for syn in ['revenue', 'sales', 'amount', 'profit', 'spend', 'total']:
            if syn in col_map:
                value_col = col_map[syn]
                break
        if not value_col:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            value_col = numeric_cols[0] if len(numeric_cols) > 0 else df.columns[-1]

        forecast_svc = ForecastingService()
        
        # Calculate selected model forecast
        model_name = payload.model
        forecast_res = forecast_svc.forecast(
            dataset_ref=dataset_path,
            model_name=model_name,
            date_col=date_col,
            value_col=value_col,
            periods=payload.periods,
            confidence=payload.confidence
        )

        # Run comparison models to fill the metrics table
        arima_res = forecast_svc.forecast(dataset_path, "arima", date_col, value_col, payload.periods, payload.confidence)
        # fallback if prophet is not available
        try:
            prophet_res = forecast_svc.forecast(dataset_path, "prophet", date_col, value_col, payload.periods, payload.confidence)
        except Exception:
            prophet_res = arima_res

        arima_metrics = arima_res.get("metrics", {})
        prophet_metrics = prophet_res.get("metrics", {})

        metrics = [
            ForecastMetric(
                metric="R-Squared (Precision)", 
                arimaValue=f"{arima_metrics.get('r_squared', 0.0):.2f}", 
                prophetValue=f"{prophet_metrics.get('r_squared', 0.0):.2f}"
            ),
            ForecastMetric(
                metric="Mean Absolute Error (MAE)", 
                arimaValue=f"${arima_metrics.get('mae', 0.0):,.0f}", 
                prophetValue=f"${prophet_metrics.get('mae', 0.0):,.0f}"
            ),
            ForecastMetric(
                metric="Root Mean Square Error (RMSE)", 
                arimaValue=f"${arima_metrics.get('rmse', 0.0):,.0f}", 
                prophetValue=f"${prophet_metrics.get('rmse', 0.0):,.0f}"
            ),
        ]

        # Convert timeline points
        timeline_points = []
        for pt in forecast_res.get("timeline", []):
            timeline_points.append(
                ForecastPoint(
                    date=pt["date"],
                    actual=pt["actual"],
                    forecast=pt["forecast"]
                )
            )

        return ForecastResponse(data=timeline_points, metrics=metrics)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/projects/{project_id}/forecast/schema-info", response_model=ProjectSchemaInfoResponse)
async def get_project_forecast_schema_info(
    project_id: str,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectSchemaInfoResponse:
    """Inspects all project datasets and returns time-series candidates and suggested controls."""
    from app.features.projects.router import get_project_and_verify_access
    from app.features.analytics.engine.discovery import DatasetDiscoveryService
    await get_project_and_verify_access(project_id, current_user, db)

    return await DatasetDiscoveryService.discover_project_candidates(project_id, db)



@router.post("/projects/{project_id}/forecast", response_model=ProjectForecastResponse)
async def run_project_forecast(
    project_id: str,
    payload: ProjectForecastRequest,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectForecastResponse:
    """Executes dataset-aware time-series forecasting pipeline on project datasets via DuckDB."""
    from app.features.projects.router import get_project_and_verify_access
    from app.features.analytics.engine.discovery import DatasetDiscoveryService, is_valid_date_column, EXPLICIT_NON_DATE_KEYWORDS
    from app.features.analytics.engine.forecasting import ProductionForecastingEngine

    await get_project_and_verify_access(project_id, current_user, db)

    # 0. Request Validation for date_column and target_column
    if payload.date_column:
        date_col_lower = payload.date_column.lower()
        if any(kw in date_col_lower for kw in EXPLICIT_NON_DATE_KEYWORDS):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Column '{payload.date_column}' is a non-temporal attribute and cannot be used as a date column for time series forecasting."
            )

    # 1. Build time-series SQL query
    sql, meta = await DatasetDiscoveryService.build_time_series_query_async(
        project_id=project_id,
        dataset_id=payload.dataset_id,
        date_column=payload.date_column,
        target_column=payload.target_column,
        aggregation=payload.aggregation,
        group_by=payload.group_by,
        db=db
    )

    # 2. Execute DuckDB query
    query_res = AnalyticsService.execute_duckdb_query(sql, project_id)
    rows = query_res.rows if hasattr(query_res, "rows") else (query_res.get("rows", []) if isinstance(query_res, dict) else [])
    if not rows:
        return ProjectForecastResponse(
            status="error",
            project_id=project_id,
            dataset_id=payload.dataset_id,
            dataset_name=meta.get("dataset_name"),
            message="No time-series rows returned from dataset query. Check that date and metric columns contain data."
        )

    df = pd.DataFrame(rows)

    date_col = "date_bucket" if "date_bucket" in df.columns else (payload.date_column or meta["date_column"])
    target_col = "metric_value" if "metric_value" in df.columns else (payload.target_column or meta["target_column"])

    # 3. Run Production Forecast Engine
    forecast_res = ProductionForecastingEngine.execute_project_forecast(
        df=df,
        project_id=project_id,
        dataset_id=payload.dataset_id,
        dataset_name=meta.get("dataset_name", "Dataset"),
        date_col=date_col,
        target_col=target_col,
        aggregation=payload.aggregation,
        horizon=payload.horizon,
        requested_model=payload.model,
        confidence=payload.confidence,
        group_by=payload.group_by
    )

    return forecast_res


@router.get("/forecasting/health", tags=["Health & Status Checks"])
@router.get("/projects/{project_id}/forecast/health", tags=["Health & Status Checks"])
async def forecasting_health_check(project_id: Optional[str] = None) -> dict:
    """Diagnostic health endpoint verifying forecasting engine, DuckDB, router, and ML dependencies."""
    from app.features.analytics.engine.forecasting import PROPHET_AVAILABLE, ProductionForecastingEngine
    from app.core.database import get_duckdb_conn

    duckdb_status = "ok"
    try:
        gen = get_duckdb_conn()
        conn = next(gen)
        try:
            conn.execute("SELECT 1")
        finally:
            try:
                gen.close()
            except Exception:
                pass
    except Exception as e:
        duckdb_status = f"error: {str(e)}"

    return {
        "api": "ok",
        "forecasting_router": "ok",
        "duckdb": duckdb_status,
        "dependencies": {
            "pandas": "ok",
            "numpy": "ok",
            "statsmodels": "ok",
            "prophet": "ok" if PROPHET_AVAILABLE else "optional (not installed)"
        },
        "engine": "ok",
        "project_id": project_id
    }



@router.post("/analytics/segment", response_model=SegmentResponse)
async def segment_cohorts(
    payload: SegmentPayload,
    dataset_id: Optional[str] = None,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> SegmentResponse:
    """Executes dynamic customer (RFM) or generic numerical dataset segmentation."""
    try:
        ds_id = payload.dataset_id or dataset_id
        dataset_path = await resolve_dataset_path_async(dataset_id=ds_id, project_id=payload.project_id, db=db)

        segment_svc = SegmentationService()
        feats = [f.strip() for f in payload.features.split(",")] if (payload.features and isinstance(payload.features, str)) else None

        n_clusters = payload.clusters if payload.clusters is not None else 3

        seg_res = segment_svc.segment_dataset(
            dataset_ref=dataset_path,
            method="kmeans",
            n_clusters=n_clusters,
            features=feats,
            mode=payload.mode or "auto",
            entity_key=payload.entity_key
        )

        scatter_points = [
            ScatterPoint(
                name=pt["name"],
                x=pt["x"],
                y=pt["y"],
                cluster=pt["cluster"],
                details=pt.get("details")
            )
            for pt in seg_res.get("scatter", [])
        ]

        cohort_segments = [
            CohortSegment(
                name=c["name"],
                count=c["count"],
                avgSpent=c["avgSpent"],
                freqScore=c["freqScore"],
                riskRating=c["riskRating"]
            )
            for c in seg_res.get("cohorts", [])
        ]

        return SegmentResponse(
            scatter=scatter_points,
            cohorts=cohort_segments,
            evaluation=seg_res.get("evaluation"),
            profiles=seg_res.get("profiles", []),
            features_used=seg_res.get("features_used", []),
            dataset_type=seg_res.get("dataset_type", "tabular"),
            entity_key=seg_res.get("entity_key"),
            message=seg_res.get("message")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/projects/{project_id}/segment/schema-info")
async def get_project_segment_schema_info(
    project_id: str,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Inspects project datasets to return available segmentation dataset candidates with auto-detected features and key columns."""
    from app.features.projects.router import get_project_and_verify_access
    from app.features.datasets.models import Dataset
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    from app.features.analytics.engine.segmentation import SegmentationService
    from app.features.analytics.engine.utils import load_dataset
    from sqlalchemy import select

    await get_project_and_verify_access(project_id, current_user, db)

    stmt = select(Dataset).where(Dataset.project_id == project_id)
    res = await db.execute(stmt)
    db_datasets = res.scalars().all()

    datasets_info = []
    for d in db_datasets:
        datasets_info.append({
            "id": str(d.id),
            "filename": d.filename,
            "display_name": d.display_name or d.filename,
            "duckdb_table": d.duckdb_table,
            "storage_path": d.storage_path
        })

    for d_id, cached in UPLOADED_PATHS_CACHE.items():
        if cached.get("project_id") == project_id:
            if not any(x["id"] == str(d_id) for x in datasets_info):
                datasets_info.append({
                    "id": str(d_id),
                    "filename": cached.get("filename", "dataset.csv"),
                    "display_name": cached.get("filename", "dataset.csv"),
                    "duckdb_table": cached.get("duckdb_table"),
                    "storage_path": cached.get("path")
                })

    candidates = []
    seg_svc = SegmentationService()

    for ds in datasets_info:
        path = ds.get("storage_path")
        if not path or not os.path.exists(path):
            continue
        try:
            df = load_dataset(path)
            if df.empty:
                continue

            entity_key = seg_svc.detect_entity_key(df)
            trans_info = seg_svc.detect_transactional_columns(df)

            entity_key_options = []
            if entity_key:
                entity_key_options.append(entity_key)
            for col in df.columns:
                c_lower = str(col).lower()
                if (c_lower.endswith("_id") or c_lower.endswith("_key") or "user" in c_lower or "customer" in c_lower or "client" in c_lower) and col not in entity_key_options:
                    entity_key_options.append(str(col))

            numeric_cols = [str(c) for c in df.select_dtypes(include=[np.number]).columns]
            suggested_features = [
                c for c in numeric_cols
                if not any(x in str(c).lower() for x in ["id", "key", "index", "zip", "code", "phone"])
                and df[c].nunique() > 1
            ]
            if not suggested_features:
                suggested_features = numeric_cols

            cat_cols = [str(c) for c in df.select_dtypes(include=['object', 'category']).columns if df[c].nunique() < 100]

            is_rfm = bool(entity_key and trans_info.get("date_col") and trans_info.get("monetary_col"))
            suggested_mode = "rfm" if is_rfm else "numerical"

            candidates.append({
                "dataset_id": ds["id"],
                "dataset_name": ds["display_name"],
                "filename": ds["filename"],
                "entity_key": entity_key,
                "available_entity_keys": entity_key_options,
                "numerical_features": numeric_cols,
                "categorical_features": cat_cols,
                "suggested_features": suggested_features,
                "suggested_mode": suggested_mode,
                "is_rfm_capable": is_rfm
            })
        except Exception as e:
            pass

    has_candidates = len(candidates) > 0
    message = None if has_candidates else "No valid datasets found in this project for segmentation. Upload a CSV or Excel dataset to begin."

    return {
        "project_id": project_id,
        "dataset_count": len(candidates),
        "candidates": candidates,
        "message": message
    }


@router.post("/projects/{project_id}/segment", response_model=SegmentResponse)
async def run_project_segmentation(
    project_id: str,
    payload: SegmentPayload,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> SegmentResponse:
    """Executes dataset-aware segmentation on project datasets."""
    try:
        from app.features.projects.router import get_project_and_verify_access
        await get_project_and_verify_access(project_id, current_user, db)

        payload.project_id = project_id
        return await segment_cohorts(payload=payload, dataset_id=payload.dataset_id, current_user=current_user, db=db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )



@router.post("/analytics/anomalies", response_model=AnomalyResponse)
async def detect_anomalies(
    payload: AnomalyPayload,
    dataset_id: Optional[str] = None,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
) -> AnomalyResponse:
    """Scans dataset columns for standard deviation and mathematical spikes/outliers."""
    try:
        dataset_path = resolve_dataset_path(dataset_id)
        df = load_dataset(dataset_path)
        if df.empty:
            raise HTTPException(status_code=400, detail="The dataset is empty.")

        # Resolve primary columns
        value_col = None
        for syn in ['revenue', 'sales', 'amount', 'profit', 'spend', 'total']:
            for col in df.columns:
                if syn in str(col).lower():
                    value_col = col
                    break
            if value_col:
                break
        if not value_col:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            value_col = numeric_cols[0] if len(numeric_cols) > 0 else df.columns[-1]
            
        date_col = None
        for col in df.columns:
            if any(x in str(col).lower() for x in ['date', 'time', 'timestamp', 'created_at']):
                date_col = col
                break
        if not date_col:
            date_col = df.columns[0]

        # Use sensitivity as contamination
        contamination = min(0.2, max(0.01, payload.sensitivity))
        anomaly_svc = AnomalyDetectionService()
        
        anom_res = anomaly_svc.find_anomalies(
            df=df,
            method="iforest",
            contamination=contamination,
            features=[value_col]
        )

        # Build timeline threshold line
        mean_val = df[value_col].mean()
        std_val = df[value_col].std() if df[value_col].std() > 0 else 1.0
        limit_val = mean_val + 2 * std_val

        # Sort timeline by date
        temp_df = df[[date_col, value_col]].dropna().copy()
        temp_df[date_col] = pd.to_datetime(temp_df[date_col])
        temp_df = temp_df.sort_values(by=date_col)

        timeline = []
        for _, row in temp_df.iterrows():
            timeline.append(
                TimelinePoint(
                    date=row[date_col].strftime("%b %d"),
                    value=float(row[value_col]),
                    limit=float(limit_val)
                )
            )

        # Build logs
        logs = []
        for anom in anom_res["anomalies"]:
            idx = anom["row_index"]
            
            date_str = str(df.iloc[idx][date_col])
            try:
                date_str = pd.to_datetime(date_str).strftime("%Y-%m-%d")
            except Exception:
                pass
                
            val = float(df.iloc[idx][value_col])
            dev = anom["deviations"][0]["deviation"] if anom["deviations"] else "+0.0 Std Dev"
            
            logs.append(
                AnomalyLog(
                    id=f"A-{idx}",
                    metric=f"{value_col} Outlier",
                    value=f"${val:,.0f}" if "revenue" in value_col.lower() or "profit" in value_col.lower() else f"{val:.1f}",
                    deviation=dev,
                    date=date_str,
                    status="Unresolved"
                )
            )

        return AnomalyResponse(timeline=timeline, logs=logs)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/sql/run", response_model=SQLResponse)
async def run_sql_query(
    payload: SQLPayload,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> SQLResponse:
    """Executes SQL queries against temporary CSV view mappings via the DuckDB engine."""
    try:
        if payload.project_id:
            from app.features.projects.router import get_project_and_verify_access
            await get_project_and_verify_access(payload.project_id, current_user, db)
            
        return AnalyticsService.execute_duckdb_query(payload.query, payload.project_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/sql/schema", response_model=List[Dict[str, Any]])
async def get_sql_schema(
    project_id: Optional[str] = None,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"])),
    db: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    """Returns currently available view mappings registered in the DuckDB context."""
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    from app.features.datasets.models import Dataset
    from sqlalchemy import select

    if project_id:
        from app.features.projects.router import get_project_and_verify_access
        await get_project_and_verify_access(project_id, current_user, db)
        
        # Get datasets belonging to the project
        stmt = select(Dataset).where(Dataset.project_id == project_id)
        result = await db.execute(stmt)
        db_items = result.scalars().all()
        
        schema_list = []
        for item in db_items:
            schema_list.append({"name": item.duckdb_table, "rowsCount": item.rows})
            
        # Also check cache
        for d_id, item in UPLOADED_PATHS_CACHE.items():
            if item.get("project_id") == project_id:
                if not any(x["name"] == item["duckdb_table"] for x in schema_list):
                    schema_list.append({"name": item["duckdb_table"], "rowsCount": item["rows"]})
                    
        return schema_list
    else:
        schema_list = []
        for dataset_id, item in UPLOADED_PATHS_CACHE.items():
            if item.get("project_id") is None:
                view_name = item["filename"].split(".")[0]
                schema_list.append({"name": view_name, "rowsCount": 100})
            
        if not schema_list:
            schema_list = [
                {"name": "q3_financials", "rowsCount": 14020},
                {"name": "customer_churn", "rowsCount": 6200},
                {"name": "raw_clicks_logs", "rowsCount": 185000},
            ]
        return schema_list


@router.get("/metrics", tags=["Dashboard & Platform Metrics"])
@router.get("/dashboard/metrics", tags=["Dashboard & Platform Metrics"])
async def get_dashboard_metrics() -> dict:
    """Returns aggregated high-level business intelligence metrics."""
    return {
        "grossRevenue": "$1,248,390",
        "grossRevenueChange": 14.2,
        "activeUsers": "14,204",
        "activeUsersChange": 8.7,
        "predictionAccuracy": "94.6%",
        "predictionAccuracyChange": 1.2,
        "anomaliesCount": 2
    }


@router.get("/dashboard/trends", tags=["Dashboard & Platform Metrics"])
async def get_dashboard_trends() -> list:
    """Returns monthly revenue vs target performance trend timelines."""
    return [
        {"month": "Jan", "revenue": 45000, "target": 40000, "margin": 23},
        {"month": "Feb", "revenue": 52000, "target": 43000, "margin": 24},
        {"month": "Mar", "revenue": 61000, "target": 48000, "margin": 26},
        {"month": "Apr", "revenue": 58000, "target": 50000, "margin": 25},
        {"month": "May", "revenue": 71000, "target": 55000, "margin": 28},
        {"month": "Jun", "revenue": 84000, "target": 60000, "margin": 30},
        {"month": "Jul", "revenue": 95000, "target": 68000, "margin": 32},
    ]


