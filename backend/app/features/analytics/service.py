import time
from typing import Dict, Any, List, Optional
import duckdb

from app.core.database import get_duckdb_conn
from app.features.analytics.schemas import SQLResponse

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


def register_all_datasets_in_duckdb(conn: duckdb.DuckDBPyConnection):
    """
    Registers all uploaded and sample datasets as views in DuckDB.
    """
    import os
    import logging
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    
    logger = logging.getLogger(__name__)
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    # Register uploaded files
    for d_id, item in UPLOADED_PATHS_CACHE.items():
        file_path = item["path"]
        view_name = os.path.splitext(item["filename"])[0].lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        try:
            if file_path.endswith('.csv'):
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{view_name}\" AS SELECT * FROM read_csv_auto('{file_path}')")
            elif file_path.endswith(('.xlsx', '.xls')):
                import pandas as pd
                df = pd.read_excel(file_path)
                conn.register(view_name, df)
            elif file_path.endswith('.json'):
                import pandas as pd
                df = pd.read_json(file_path)
                conn.register(view_name, df)
            elif file_path.endswith('.parquet'):
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{view_name}\" AS SELECT * FROM read_parquet('{file_path}')")
        except Exception as e:
            logger.warning(f"Failed to register uploaded view {view_name} in DuckDB: {str(e)}")

    # Register sample files
    sample_dir = os.path.join(root_dir, "sample_data")
    if os.path.exists(sample_dir):
        for f in os.listdir(sample_dir):
            if f.endswith(('.csv', '.xlsx', '.xls', '.json', '.parquet')):
                file_path = os.path.join(sample_dir, f)
                base_name = os.path.splitext(f)[0].lower()
                try:
                    if f.endswith('.csv'):
                        conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{base_name}\" AS SELECT * FROM read_csv_auto('{file_path}')")
                        # Also register short name (e.g. customer_churn instead of customer_churn_data)
                        short_name = base_name.replace("_data", "")
                        conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{short_name}\" AS SELECT * FROM read_csv_auto('{file_path}')")
                    elif f.endswith(('.xlsx', '.xls')):
                        import pandas as pd
                        df = pd.read_excel(file_path)
                        conn.register(base_name, df)
                        short_name = base_name.replace("_data", "")
                        conn.register(short_name, df)
                    elif f.endswith('.json'):
                        import pandas as pd
                        df = pd.read_json(file_path)
                        conn.register(base_name, df)
                        short_name = base_name.replace("_data", "")
                        conn.register(short_name, df)
                    elif f.endswith('.parquet'):
                        conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{base_name}\" AS SELECT * FROM read_parquet('{file_path}')")
                        short_name = base_name.replace("_data", "")
                        conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{short_name}\" AS SELECT * FROM read_parquet('{file_path}')")
                except Exception as e:
                    logger.warning(f"Failed to register sample view {base_name} in DuckDB: {str(e)}")


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
    def execute_duckdb_query(query: str) -> SQLResponse:
        """Loads active cached datasets into temporary views inside DuckDB and executes SQL queries."""
        import hashlib
        from app.core.cache import cache_client, run_async_as_sync
        from app.core.telemetry import SQL_LATENCY
        from app.features.datasets.router import UPLOADED_PATHS_CACHE

        query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
        cache_key = f"sql_query:{query_hash}"

        # 1. Try Cache Lookup
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
            register_all_datasets_in_duckdb(conn)
        except Exception:
            pass

        try:
            res = conn.execute(query)
            columns = [desc[0] for desc in res.description] if res.description else []
            rows = []
            
            if res.description:
                for row in res.fetchall():
                    row_dict = {}
                    for idx, col_name in enumerate(columns):
                        row_dict[col_name] = row[idx]
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


