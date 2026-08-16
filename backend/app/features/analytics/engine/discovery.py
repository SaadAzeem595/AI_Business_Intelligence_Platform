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

DATE_KEYWORDS = ["date", "time", "created_at", "timestamp", "purchase", "month", "year", "dt"]
METRIC_KEYWORDS = ["revenue", "sales", "price", "amount", "cost", "total", "spend", "freight_value", "quantity", "order_count", "units", "profit"]
ID_EXCLUDE_KEYWORDS = ["id", "zip", "code", "index", "phone", "lat", "lng", "geo", "cpf", "cnpj"]


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
                    suggested_metric="total_order_value (price + freight_value)"
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

                    # 1. Check Date Column
                    is_date = False
                    if any(k in col_lower for k in DATE_KEYWORDS):
                        is_date = True
                    elif df[col_str].dtype == 'object' or pd.api.types.is_datetime64_any_dtype(df[col_str]):
                        try:
                            sample = df[col_str].dropna().head(10)
                            if len(sample) > 0 and pd.to_datetime(sample, errors='coerce').notna().all():
                                is_date = True
                        except Exception:
                            pass

                    if is_date:
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

                if date_cols or metric_cols:
                    suggested_date = date_cols[0] if date_cols else None
                    
                    # Prefer revenue/sales/amount for suggested metric
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
                            suggested_metric=suggested_metric
                        )
                    )
            except Exception as e:
                logger.error(f"Error inspecting dataset {ds['filename']}: {e}")

        has_valid_ts = len(candidates) > 0

        message = None
        if not has_valid_ts:
            message = (
                "No suitable time-series data was found in this project. "
                "To run forecasting, your project requires at least one dataset with a date/time column, "
                "a numeric metric, and sufficient historical observations."
            )

        return ProjectSchemaInfoResponse(
            has_time_series=has_valid_ts,
            candidates=candidates,
            message=message
        )

    @staticmethod
    def build_time_series_query(
        project_id: str,
        dataset_id: Optional[str],
        date_column: Optional[str],
        target_column: Optional[str],
        aggregation: str = "monthly",
        group_by: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Constructs schema-aware DuckDB SQL query to aggregate project datasets into clean time-series.
        Supports single datasets as well as relational joins (e.g. Olist dataset).
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
        table_name = None
        ds_name = "Dataset"

        for d_id, cached in UPLOADED_PATHS_CACHE.items():
            if str(d_id) == str(dataset_id) or dataset_id is None:
                table_name = cached.get("duckdb_table") or cached.get("filename", "").split(".")[0]
                ds_name = cached.get("filename", "Dataset")
                break

        if not table_name:
            table_name = "active_dataset"

        date_col = date_column or "date"
        target_col = target_column or "revenue"
        group_sql = f', "{group_by}"' if group_by else ""
        select_group = f', "{group_by}" AS group_key' if group_by else ""

        sql = f"""
        SELECT 
          date_trunc('{agg_fmt}', CAST("{date_col}" AS TIMESTAMP)) AS date_bucket,
          SUM("{target_col}") AS metric_value
          {select_group}
        FROM "{table_name}"
        WHERE "{date_col}" IS NOT NULL AND "{target_col}" IS NOT NULL
        GROUP BY 1 {group_sql}
        ORDER BY 1 ASC
        """

        return sql, {"dataset_name": ds_name, "date_column": date_col, "target_column": target_col}
