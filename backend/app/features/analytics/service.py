import time
from typing import Dict, Any, List
import duckdb

from app.core.database import get_duckdb_conn
from app.features.analytics.schemas import SQLResponse


class AnalyticsService:
    """Orchestrates machine learning calculations, forecasting projections, and executing DuckDB SQL queries."""

    @staticmethod
    def execute_duckdb_query(query: str) -> SQLResponse:
        """Loads active cached datasets into temporary views inside DuckDB and executes SQL queries."""
        # Import inside method to prevent circular reference limits
        from app.features.datasets.router import UPLOADED_PATHS_CACHE

        conn = next(get_duckdb_conn())
        start_time = time.perf_counter()

        try:
            # Dynamically register all uploaded CSV files as temporary views in DuckDB
            for dataset_id, item in UPLOADED_PATHS_CACHE.items():
                file_path = item["path"]
                # Use clean view names (e.g. without extension)
                view_name = item["filename"].split(".")[0]
                # Register views in DuckDB session context
                conn.execute(
                    f"CREATE OR REPLACE TEMP VIEW \"{view_name}\" AS SELECT * FROM read_csv_auto('{file_path}')"
                )
        except Exception:
            # Graceful pass if views registration fails (e.g., non-CSV files or lock errors)
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

            return SQLResponse(
                columns=columns,
                rows=rows,
                elapsedMs=process_time_ms,
            )
        except Exception as e:
            # Let the query runner crash with clear message for user debugging
            raise Exception(f"SQL execution error: {str(e)}")
        finally:
            conn.close()
