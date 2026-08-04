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

        conn = next(get_duckdb_conn())
        start_time = time.perf_counter()

        try:
            # Dynamically register all uploaded CSV files as temporary views in DuckDB
            for dataset_id, item in UPLOADED_PATHS_CACHE.items():
                file_path = item["path"]
                view_name = item["filename"].split(".")[0]
                conn.execute(
                    f"CREATE OR REPLACE TEMP VIEW \"{view_name}\" AS SELECT * FROM read_csv_auto('{file_path}')"
                )
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
            conn.close()


