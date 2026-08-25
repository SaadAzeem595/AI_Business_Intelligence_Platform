import os
import re
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.datasets.models import Dataset
from app.features.datasets.router import UPLOADED_PATHS_CACHE
from app.features.analytics.engine.utils import load_dataset
from app.features.analytics.schemas import TimeSeriesCandidate, ProjectSchemaInfoResponse

logger = logging.getLogger(__name__)

EXPLICIT_NON_DATE_KEYWORDS = [
    "width", "height", "length", "lenght", "weight", "qty", "quantity",
    "price", "cost", "value", "amount", "score", "count", "id", "zip",
    "code", "index", "phone", "lat", "lng", "geo", "cpf", "cnpj", "freight",
    "cm", "mm", "kg", "g", "meter", "size", "dimension", "description", "category"
]

METRIC_KEYWORDS = ["revenue", "sales", "price", "amount", "cost", "total", "spend", "freight_value", "quantity", "order_count", "units", "profit"]
ID_EXCLUDE_KEYWORDS = ["id", "zip", "code", "index", "phone", "lat", "lng", "geo", "cpf", "cnpj"]
STRICT_DATE_REGEX = re.compile(r'\b(date|time|timestamp|datetime|created_at|updated_at|order_date|purchase_timestamp|approved_at|delivered_date)\b', re.IGNORECASE)


def is_valid_date_column(df: pd.DataFrame, col_name: str) -> bool:
    """
    Strictly validates if a column is temporal.
    - Rejects numeric columns (float, int, DOUBLE, DECIMAL) unless column name explicitly indicates date/time and values fall into Excel serial or Unix timestamp range.
    - Rejects columns matching explicit non-date attribute keywords (width, height, price, cm, etc.).
    - Rejects string columns whose non-null samples are numeric values (e.g. "25", "25.0").
    - Validates datetime parse rate >= 80% on non-null samples with >= 3 distinct dates in reasonable year bounds (1900 - 2100).
    """
    col_str = str(col_name)
    col_lower = col_str.lower()
    series = df[col_str]

    # Rule 1: Reject explicit non-date attribute keywords (e.g. product_width_cm, price, quantity, size)
    if any(kw in col_lower for kw in EXPLICIT_NON_DATE_KEYWORDS):
        return False

    # Rule 2: Datetime dtype is inherently date
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    # Rule 3: Numeric columns check
    if pd.api.types.is_numeric_dtype(series):
        # Allow numeric only if column name strongly suggests date/timestamp AND values fall in Excel date serial (30000..60000) or Unix timestamp (1e9..2e9)
        if STRICT_DATE_REGEX.search(col_lower):
            non_null = series.dropna()
            if len(non_null) > 0:
                vals = non_null.head(30)
                if ((vals >= 30000) & (vals <= 60000)).all() or ((vals >= 1e9) & (vals <= 2e9)).all():
                    return True
        return False

    # Rule 4: String / object validation
    if series.dtype == 'object' or isinstance(series.dtype, pd.StringDtype):
        non_null_samples = series.dropna()
        if len(non_null_samples) == 0:
            return False

        sample = non_null_samples.head(30)

        # Check if sample strings are purely numeric (e.g. "25", "25.0", "100")
        is_all_numeric_strings = True
        for val in sample:
            s_val = str(val).strip()
            if not re.match(r'^-?\d+(\.\d+)?$', s_val):
                is_all_numeric_strings = False
                break
        if is_all_numeric_strings:
            return False

        # Attempt datetime parsing with multiple strategies (standard, format='mixed', dayfirst)
        parsed = None
        try:
            parsed = pd.to_datetime(sample, errors='coerce', format='mixed')
        except Exception:
            try:
                parsed = pd.to_datetime(sample, errors='coerce')
            except Exception:
                try:
                    parsed = pd.to_datetime(sample, errors='coerce', dayfirst=True)
                except Exception:
                    pass

        if parsed is not None:
            valid_parsed = parsed.dropna()
            if len(valid_parsed) / len(sample) >= 0.8:
                if valid_parsed.nunique() >= 3:
                    years = valid_parsed.dt.year
                    if not ((years < 1900).any() or (years > 2100).any()):
                        if STRICT_DATE_REGEX.search(col_lower) or len(valid_parsed) == len(sample):
                            return True

    return False


class DatasetDiscoveryService:
    @staticmethod
    async def discover_project_candidates(
        project_id: str,
        db: AsyncSession
    ) -> ProjectSchemaInfoResponse:
        """
        Inspects all datasets associated with a project and returns time-series candidates.
        Automatically detects date/time, numeric metric, and categorical breakdown columns.
        Supports relational discovery for multi-table datasets like Olist.
        """
        # Fetch project datasets from Postgres DB
        stmt = select(Dataset).where(Dataset.project_id == project_id)
        res = await db.execute(stmt)
        db_datasets = res.scalars().all()

        datasets_info: List[Dict[str, Any]] = []
        for d in db_datasets:
            datasets_info.append({
                "id": str(d.id),
                "filename": d.filename,
                "duckdb_table": d.duckdb_table,
                "storage_path": d.storage_path
            })

        # Also merge cached items for project
        for d_id, cached in UPLOADED_PATHS_CACHE.items():
            if cached.get("project_id") == project_id:
                if not any(x["id"] == str(d_id) for x in datasets_info):
                    datasets_info.append({
                        "id": str(d_id),
                        "filename": cached.get("filename", "dataset.csv"),
                        "duckdb_table": cached.get("duckdb_table"),
                        "storage_path": cached.get("path")
                    })

        if not datasets_info:
            return ProjectSchemaInfoResponse(
                has_time_series=False,
                candidates=[],
                message="No datasets found in this project. Upload a CSV or Excel file with date and numeric columns to begin forecasting."
            )

        candidates: List[TimeSeriesCandidate] = []
        table_name_map = {d["duckdb_table"].lower() if d.get("duckdb_table") else d["filename"].lower(): d for d in datasets_info}

        # Check for Olist Relational Pattern (orders + order_items)
        has_olist_orders = any("orders" in name and "items" not in name for name in table_name_map)
        has_olist_items = any("items" in name or "order_items" in name for name in table_name_map)

        if has_olist_orders and has_olist_items:
            candidates.append(
                TimeSeriesCandidate(
                    dataset_id="olist_relational_derived",
                    dataset_name="Olist E-Commerce (Orders + Order Items Joined)",
                    date_columns=["order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date"],
                    metric_columns=["price", "freight_value", "total_order_value (price + freight_value)"],
                    categorical_columns=["product_category_name", "order_status", "customer_state"],
                    is_derived_olist=True,
                    suggested_date="order_purchase_timestamp",
                    suggested_metric="total_order_value (price + freight_value)",
                    dataset_type="Transactional / Time Series",
                    is_time_series_capable=True
                )
            )

        # Inspect individual dataset files
        for ds in datasets_info:
            storage_path = ds.get("storage_path")
            if not storage_path or not os.path.exists(storage_path):
                continue

            try:
                df = load_dataset(storage_path)
                if df.empty:
                    continue

                date_cols = []
                metric_cols = []
                cat_cols = []

                for col in df.columns:
                    col_str = str(col)
                    col_lower = col_str.lower()

                    # 1. Check Date Column using strict validation
                    if is_valid_date_column(df, col_str):
                        date_cols.append(col_str)
                        continue

                    # 2. Check Numeric Metric
                    is_excluded_id = any(k in col_lower for k in ID_EXCLUDE_KEYWORDS)
                    if pd.api.types.is_numeric_dtype(df[col_str]) and not is_excluded_id:
                        metric_cols.append(col_str)
                    elif df[col_str].dtype == 'object':
                        # Check low cardinality category
                        unique_cnt = df[col_str].nunique()
                        if 1 < unique_cnt < 100:
                            cat_cols.append(col_str)

                is_ts_capable = len(date_cols) > 0 and len(metric_cols) > 0
                dataset_type = "Transactional / Time Series" if is_ts_capable else "Dimension / Master Data"

                suggested_date = date_cols[0] if date_cols else None
                suggested_metric = None
                for m in metric_cols:
                    if any(k in m.lower() for k in METRIC_KEYWORDS):
                        suggested_metric = m
                        break
                if not suggested_metric and metric_cols:
                    suggested_metric = metric_cols[0]

                candidates.append(
                    TimeSeriesCandidate(
                        dataset_id=ds["id"],
                        dataset_name=ds["filename"],
                        date_columns=date_cols,
                        metric_columns=metric_cols,
                        categorical_columns=cat_cols,
                        is_derived_olist=False,
                        suggested_date=suggested_date,
                        suggested_metric=suggested_metric,
                        dataset_type=dataset_type,
                        is_time_series_capable=is_ts_capable
                    )
                )
            except Exception as e:
                logger.error(f"Error inspecting dataset {ds['filename']}: {e}")

        has_valid_ts = any(c.is_time_series_capable for c in candidates)

        message = None
        if not has_valid_ts:
            message = (
                "Selected datasets (e.g. product attribute data) do not contain temporal timestamp columns. "
                "For sales forecasting, please select a transactional dataset or use the auto-joined Olist dataset."
            )

        return ProjectSchemaInfoResponse(
            has_time_series=has_valid_ts,
            candidates=candidates,
            message=message
        )

    @staticmethod
    async def build_time_series_query_async(
        project_id: str,
        dataset_id: Optional[str],
        date_column: Optional[str],
        target_column: Optional[str],
        aggregation: str = "monthly",
        group_by: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Constructs schema-aware DuckDB SQL query to aggregate project datasets into clean time-series.
        Supports single datasets as well as relational joins (e.g. Olist dataset).
        Resolves table name dynamically from DB metadata or uploaded cache.
        """
        agg_fmt = "month"
        if aggregation.lower() == "daily":
            agg_fmt = "day"
        elif aggregation.lower() == "weekly":
            agg_fmt = "week"

        # Check Olist derived join
        if dataset_id == "olist_relational_derived" or (date_column and "order_purchase_timestamp" in date_column):
            date_col = date_column or "order_purchase_timestamp"
            group_sql = f', items."{group_by}"' if group_by else ""
            select_group = f', items."{group_by}" AS group_key' if group_by else ""

            sql = f"""
            SELECT 
              date_trunc('{agg_fmt}', CAST(orders."{date_col}" AS TIMESTAMP)) AS date_bucket,
              SUM(items.price + COALESCE(items.freight_value, 0)) AS metric_value
              {select_group}
            FROM olist_orders_dataset orders
            JOIN olist_order_items_dataset items ON orders.order_id = items.order_id
            WHERE orders."{date_col}" IS NOT NULL
            GROUP BY 1 {group_sql}
            ORDER BY 1 ASC
            """
            return sql, {"dataset_name": "Olist E-Commerce (Derived Join)", "date_column": date_col, "target_column": "total_order_value"}

        # Single table query resolution
        from app.features.datasets.router import UPLOADED_PATHS_CACHE
        from app.features.auth.models import User
        from app.features.projects.models import Project
        from app.features.datasets.models import Dataset

        table_name = None
        ds_name = "Dataset"

        if db and dataset_id:
            stmt = select(Dataset).where(Dataset.id == dataset_id)
            res = await db.execute(stmt)
            d_obj = res.scalar_one_or_none()
            if d_obj:
                table_name = d_obj.duckdb_table or (d_obj.display_name and d_obj.display_name.split(".")[0]) or (d_obj.filename and d_obj.filename.split(".")[0])
                ds_name = d_obj.filename

        if db and not table_name:
            stmt = select(Dataset).where(Dataset.project_id == project_id)
            res = await db.execute(stmt)
            d_items = res.scalars().all()
            if d_items:
                target_d = next((d for d in d_items if str(d.id) == str(dataset_id)), d_items[0])
                table_name = target_d.duckdb_table or (target_d.display_name and target_d.display_name.split(".")[0]) or (target_d.filename and target_d.filename.split(".")[0])
                ds_name = target_d.filename

        if not table_name:
            for d_id, cached in UPLOADED_PATHS_CACHE.items():
                if str(d_id) == str(dataset_id) or (dataset_id is None and cached.get("project_id") == project_id):
                    table_name = cached.get("duckdb_table") or cached.get("filename", "").split(".")[0]
                    ds_name = cached.get("filename", "Dataset")
                    break

        if not table_name and dataset_id:
            table_name = dataset_id.replace("-", "_").lower()

        if not table_name:
            table_name = "dataset"

        date_col = date_column or "date"
        target_col = target_column or "revenue"
        group_sql = f', "{group_by}"' if group_by else ""
        select_group = f', "{group_by}" AS group_key' if group_by else ""

        clean_table = table_name.strip().lower().replace(" ", "_").replace("-", "_")
        clean_table = "".join(c for c in clean_table if c.isalnum() or c == "_")
        if not clean_table:
            clean_table = "dataset"

        date_expr = (
            f'COALESCE('
            f'TRY_CAST("{date_col}" AS TIMESTAMP), '
            f'TRY_CAST(strptime(CAST("{date_col}" AS VARCHAR), \'%Y-%m-%d\') AS TIMESTAMP), '
            f'TRY_CAST(strptime(CAST("{date_col}" AS VARCHAR), \'%m/%d/%Y\') AS TIMESTAMP), '
            f'TRY_CAST(strptime(CAST("{date_col}" AS VARCHAR), \'%d/%m/%Y\') AS TIMESTAMP), '
            f'TRY_CAST(strptime(CAST("{date_col}" AS VARCHAR), \'%Y/%m/%d\') AS TIMESTAMP), '
            f'TRY_CAST(to_timestamp((TRY_CAST("{date_col}" AS DOUBLE) - 25569) * 86400) AS TIMESTAMP), '
            f'TRY_CAST(to_timestamp(TRY_CAST("{date_col}" AS DOUBLE)) AS TIMESTAMP)'
            f')'
        )

        sql = f"""
        SELECT 
          date_trunc('{agg_fmt}', {date_expr}) AS date_bucket,
          SUM("{target_col}") AS metric_value
          {select_group}
        FROM "{clean_table}"
        WHERE "{date_col}" IS NOT NULL AND "{target_col}" IS NOT NULL AND {date_expr} IS NOT NULL
        GROUP BY 1 {group_sql}
        ORDER BY 1 ASC
        """

        return sql, {"dataset_name": ds_name, "date_column": date_col, "target_column": target_col}

    @staticmethod
    def build_time_series_query(
        project_id: str,
        dataset_id: Optional[str],
        date_column: Optional[str],
        target_column: Optional[str],
        aggregation: str = "monthly",
        group_by: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        from app.core.cache import run_async_as_sync
        try:
            return run_async_as_sync(
                DatasetDiscoveryService.build_time_series_query_async(
                    project_id=project_id,
                    dataset_id=dataset_id,
                    date_column=date_column,
                    target_column=target_column,
                    aggregation=aggregation,
                    group_by=group_by
                )
            )
        except Exception:
            agg_fmt = "month" if aggregation.lower() == "monthly" else ("day" if aggregation.lower() == "daily" else "week")
            tbl = (dataset_id or "dataset").replace("-", "_").lower()
            date_col = date_column or "date"
            target_col = target_column or "revenue"
            sql = f'SELECT date_trunc(\'{agg_fmt}\', CAST("{date_col}" AS TIMESTAMP)) AS date_bucket, SUM("{target_col}") AS metric_value FROM "{tbl}" WHERE "{date_col}" IS NOT NULL GROUP BY 1 ORDER BY 1 ASC'
            return sql, {"dataset_name": "Dataset", "date_column": date_col, "target_column": target_col}

