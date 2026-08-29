import time
from typing import Dict, Any, List, Optional
import duckdb

from app.core.database import get_duckdb_conn
from app.features.analytics.schemas import SQLResponse

# Ensure SQLAlchemy models are loaded in order (User & Project before Dataset)
from app.features.auth.models import User
from app.features.projects.models import Project
from app.features.datasets.models import Dataset

# Import new analytical services
from app.features.analytics.engine.profiler import DataProfilerService
from app.features.analytics.engine.quality import DataQualityService
from app.features.analytics.engine.kpi import KpiEngineService
from app.features.analytics.engine.statistics import StatisticalAnalysisService
from app.features.analytics.engine.feature_engineering import FeatureEngineeringService
from app.features.analytics.engine.visualization import VisualizationService
from app.features.analytics.engine.forecasting import ForecastingService
from app.features.analytics.engine.segmentation import SegmentationService
from app.features.analytics.engine.anomaly import AnomalyDetectionService
from app.features.analytics.engine.explainability import ExplainabilityService


def register_all_datasets_in_duckdb(conn: duckdb.DuckDBPyConnection, project_id: Optional[str] = None):
    """
    Registers all uploaded datasets belonging strictly to project_id as views in DuckDB.
    """
    import os
    import logging
    from sqlalchemy import select
    from app.features.auth.models import User
    from app.features.projects.models import Project
    from app.features.datasets.models import Dataset
    from app.core.database import AsyncSessionLocal
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    
    logger = logging.getLogger(__name__)
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    async def fetch_all_datasets_async():
        async with AsyncSessionLocal() as db:
            if project_id:
                stmt = select(Dataset).where(Dataset.project_id == project_id)
            else:
                stmt = select(Dataset).where(Dataset.project_id == None)
            result = await db.execute(stmt)
            return list(result.scalars().all())

    db_items = []
    try:
        from app.core.cache import run_async_as_sync
        db_items = run_async_as_sync(fetch_all_datasets_async())
    except Exception as e:
        logger.error(f"Failed to fetch datasets from DB for DuckDB registration: {e}")
        db_items = []

    # Map for deduplication
    registered_paths = set()

    # Helper to register view in DuckDB
    def create_duckdb_view(file_path: str, view_name: str):
        if not view_name or not file_path or not os.path.exists(file_path):
            return
        clean_v = view_name.strip().lower().replace(" ", "_").replace("-", "_")
        clean_v = "".join(c for c in clean_v if c.isalnum() or c == "_")
        if not clean_v:
            return
        clean_path = file_path.replace("\\", "/")
        try:
            if clean_path.endswith('.csv'):
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{clean_v}\" AS SELECT * FROM read_csv_auto('{clean_path}')")
            elif clean_path.endswith(('.xlsx', '.xls')):
                import pandas as pd
                df = pd.read_excel(file_path)
                conn.register(clean_v, df)
            elif clean_path.endswith('.json'):
                import pandas as pd
                df = pd.read_json(file_path)
                conn.register(clean_v, df)
            elif clean_path.endswith('.parquet'):
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{clean_v}\" AS SELECT * FROM read_parquet('{clean_path}')")
        except Exception as e:
            logger.warning(f"Failed to register view '{clean_v}' in DuckDB: {str(e)}")

    # 1. Register uploaded files from DB
    for item in db_items:
        file_path = item.storage_path
        if not file_path or not os.path.exists(file_path):
            continue
        registered_paths.add(file_path)
        
        view_names = set()
        if item.duckdb_table:
            view_names.add(item.duckdb_table)
        if item.display_name:
            view_names.add(item.display_name)
        if item.filename:
            view_names.add(os.path.splitext(item.filename)[0])
            view_names.add(item.filename)
        if item.original_filename:
            view_names.add(os.path.splitext(item.original_filename)[0])

        for view_name in view_names:
            create_duckdb_view(file_path, view_name)

    # 2. Register from UPLOADED_PATHS_CACHE fallback
    for d_id, item in UPLOADED_PATHS_CACHE.items():
        file_path = item["path"]
        if file_path in registered_paths:
            continue
        if project_id and item.get("project_id") != project_id:
            continue
        if not project_id and item.get("project_id") is not None:
            continue
            
        view_names = set()
        if item.get("duckdb_table"):
            view_names.add(item["duckdb_table"])
        if item.get("filename"):
            view_names.add(os.path.splitext(item["filename"])[0])

        for view_name in view_names:
            create_duckdb_view(file_path, view_name)

    # Register sample files only if project_id is None AND no DB/cache datasets exist
    if not project_id and not db_items and not UPLOADED_PATHS_CACHE:
        sample_dir = os.path.join(root_dir, "sample_data")
        if os.path.exists(sample_dir):
            for f in os.listdir(sample_dir):
                if f.endswith(('.csv', '.xlsx', '.xls', '.json', '.parquet')):
                    file_path = os.path.join(sample_dir, f)
                    base_name = os.path.splitext(f)[0].lower()
                    create_duckdb_view(file_path, base_name)
                    create_duckdb_view(file_path, base_name.replace("_data", ""))


class AnalyticsService:
    """Orchestrates machine learning calculations, forecasting projections, and executing DuckDB SQL queries."""

    def __init__(
        self,
        profiler: Optional[DataProfilerService] = None,
        quality: Optional[DataQualityService] = None,
        kpi: Optional[KpiEngineService] = None,
        statistics: Optional[StatisticalAnalysisService] = None,
        feature_engineering: Optional[FeatureEngineeringService] = None,
        visualization: Optional[VisualizationService] = None,
        forecasting: Optional[ForecastingService] = None,
        segmentation: Optional[SegmentationService] = None,
        anomaly: Optional[AnomalyDetectionService] = None,
        explainability: Optional[ExplainabilityService] = None,
    ):
        """Supports dependency injection for independent testability."""
        self.profiler = profiler or DataProfilerService()
        self.quality = quality or DataQualityService()
        self.kpi = kpi or KpiEngineService()
        self.statistics = statistics or StatisticalAnalysisService()
        self.feature_engineering = feature_engineering or FeatureEngineeringService()
        self.visualization = visualization or VisualizationService()
        self.forecasting = forecasting or ForecastingService()
        self.segmentation = segmentation or SegmentationService()
        self.anomaly = anomaly or AnomalyDetectionService()
        self.explainability = explainability or ExplainabilityService()

    @staticmethod
    def execute_duckdb_query(query: str, project_id: Optional[str] = None) -> SQLResponse:
        """Loads active cached datasets into temporary views inside DuckDB and executes SQL queries."""
        import hashlib
        import re
        from app.core.cache import cache_client, run_async_as_sync
        from app.core.telemetry import SQL_LATENCY
        from app.features.datasets.router import UPLOADED_PATHS_CACHE

        # 1. SQL Safety Validation Layer
        clean_q = query.strip().upper()
        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE", "COPY"]
        for kw in forbidden_keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', clean_q):
                # Allow creating temporary views or tables used by the loading mechanism
                if kw == "CREATE" and ("VIEW" in clean_q or "TEMP" in clean_q or "TABLE" in clean_q):
                    continue
                raise Exception("The generated query was rejected for safety.")

        query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
        cache_key = f"sql_query:{project_id or 'global'}:{query_hash}"

        # 2. Try Cache Lookup
        try:
            cached_data = run_async_as_sync(cache_client.get(cache_key))
            if cached_data:
                # Cache hit
                return SQLResponse(
                    columns=cached_data["columns"],
                    rows=cached_data["rows"],
                    elapsedMs=0,  # Cache is fast/instant
                )
        except Exception as e:
            pass

        gen = get_duckdb_conn()
        conn = next(gen)
        start_time = time.perf_counter()

        try:
            # Dynamically register all uploaded and sample files as temporary views in DuckDB
            register_all_datasets_in_duckdb(conn, project_id)
        except Exception:
            pass

        try:
            from app.core.json_utils import make_json_serializable
            res = conn.execute(query)
            columns = [desc[0] for desc in res.description] if res.description else []
            rows = []
            
            if res.description:
                for row in res.fetchall():
                    row_dict = {}
                    for idx, col_name in enumerate(columns):
                        row_dict[col_name] = make_json_serializable(row[idx])
                    rows.append(row_dict)

            process_time_ms = int((time.perf_counter() - start_time) * 1000)
            duration_sec = time.perf_counter() - start_time
            
            # Observe telemetry latency metric
            SQL_LATENCY.labels(query_hash=query_hash).observe(duration_sec)

            response_obj = SQLResponse(
                columns=columns,
                rows=rows,
                elapsedMs=process_time_ms,
            )

            # 2. Save cache
            try:
                cache_payload = {"columns": columns, "rows": rows}
                run_async_as_sync(cache_client.set(cache_key, cache_payload, ttl=300))
            except Exception:
                pass

            return response_obj
        except Exception as e:
            raise Exception(f"SQL execution error: {str(e)}")
        finally:
            try:
                gen.close()
            except Exception:
                pass


