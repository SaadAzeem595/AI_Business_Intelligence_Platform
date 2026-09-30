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

NON_DATE_UNIT_SUFFIXES = (
    "_cm", "_mm", "_kg", "_g", "_qty", "_quantity", "_price", "_cost",
    "_amount", "_score", "_count", "_id", "_size", "_dimension",
    "_description", "_category", "_name", "_lenght", "_length", "_weight",
    "_width", "_height", "_pct", "_percent"
)

METRIC_KEYWORDS = ["revenue", "sales", "price", "amount", "cost", "total", "spend", "freight_value", "quantity", "order_count", "units", "profit"]
ID_EXCLUDE_KEYWORDS = ["id", "zip", "code", "index", "phone", "lat", "lng", "geo", "cpf", "cnpj"]
STRICT_DATE_REGEX = re.compile(
    r'(?:^|[\W_])(date|time|timestamp|datetime|created|updated|purchased|approved|delivered|shipped|invoiced|trans|event|period|day|month|year|week|quarter|dt|ds|ts)(?:[\W_]|$)',
    re.IGNORECASE
)


def is_valid_date_column(df: pd.DataFrame, col_name: str) -> bool:
    """
    Dynamically and robustly validates if a column represents temporal/date/time data.
    - Rejects explicit non-temporal dimensions and measurement attributes (e.g. product_width_cm, price, weight).
    - Detects native datetime dtypes.
    - Detects numeric columns storing Excel serial dates (30000..60000) or Unix epoch timestamps.
    - Accurately tests object/string columns across ISO, slash, hyphen, mixed date formats with safe parsing.
    """
    col_str = str(col_name)
    col_lower = col_str.lower().strip()
    series = df[col_str]

    # Rule 1: Tokenize column name to prevent substring collisions (e.g. 'g' matching 'shipping_date' or 'id' matching 'paid_at')
    tokens = set(re.split(r'[\W_]+', col_lower))
    has_explicit_date_term = bool(STRICT_DATE_REGEX.search(col_lower))

    # Reject measurement suffixes unless column name explicitly indicates date/time (e.g. shipping_date vs product_weight_g)
    if col_lower.endswith(NON_DATE_UNIT_SUFFIXES) and not has_explicit_date_term:
        return False

    strong_non_date_tokens = {"width", "height", "length", "lenght", "weight", "qty", "quantity", "price", "cost", "score", "cm", "mm", "kg", "dimension", "size", "geo", "lat", "lng", "cnpj", "cpf"}
    if any(t in strong_non_date_tokens for t in tokens) and not has_explicit_date_term:
        return False

    # Rule 2: Datetime dtype is inherently temporal
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    # Rule 3: Numeric columns check (Excel serial or Unix epoch timestamps)
    if pd.api.types.is_numeric_dtype(series):
        non_null = series.dropna()
        if len(non_null) > 0:
            vals = non_null.head(40)
            is_excel_serial = ((vals >= 30000) & (vals <= 65000)).all()
            is_unix_sec = ((vals >= 9.46e8) & (vals <= 2.5e9)).all()
            is_unix_ms = ((vals >= 9.46e11) & (vals <= 2.5e12)).all()
            if is_excel_serial or is_unix_sec or is_unix_ms:
                if has_explicit_date_term or len(tokens.intersection({"year", "month", "day", "date", "time", "timestamp", "period"})) > 0:
                    return True
        return False

    # Rule 4: String / object column validation using DateTimeNormalizer
    if series.dtype == 'object' or isinstance(series.dtype, pd.StringDtype):
        non_null_samples = series.dropna()
        if len(non_null_samples) == 0:
            return False

        sample = non_null_samples.head(50)

        # Reject columns whose non-null samples are all plain numbers without date separators
        is_all_pure_numbers = True
        for val in sample:
            s_val = str(val).strip()
            if not re.match(r'^-?\d+(\.\d+)?$', s_val):
                is_all_pure_numbers = False
                break
        if is_all_pure_numbers:
            return False

        from app.features.analytics.engine.date_normalizer import DateTimeNormalizer
        detection = DateTimeNormalizer.detect_format(sample.tolist(), column_name=col_str)
        if detection.get("detected_type") == "datetime" and detection.get("parse_success_rate", 0) >= 0.7:
            return True

    return False


def build_duckdb_date_expr(col_ref: str, detected_format: Optional[str] = None) -> str:
    """Builds a safe, non-throwing COALESCE expression in DuckDB using DateTimeNormalizer."""
    from app.features.analytics.engine.date_normalizer import DateTimeNormalizer
    return DateTimeNormalizer.get_duckdb_date_expression(col_ref, detected_format)


def resolve_actual_file(storage_path: Optional[str], filename: Optional[str] = None) -> Optional[str]:
    """Resolves dataset file path on host or container across candidate storage locations."""
    if storage_path and os.path.exists(storage_path):
        return storage_path

    candidates = []

    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    root_dir = os.path.dirname(backend_dir)

    cand_dirs = [
        os.path.join(backend_dir, "app", "uploads"),
        os.path.join(backend_dir, "uploads"),
        os.path.join(root_dir, "backend", "app", "uploads"),
        os.path.join(root_dir, "backend", "uploads"),
        os.path.join(root_dir, "uploads"),
        os.path.join(os.getcwd(), "app", "uploads"),
        os.path.join(os.getcwd(), "backend", "app", "uploads"),
        os.path.join(os.getcwd(), "backend", "uploads"),
        os.path.join(os.getcwd(), "uploads"),
        os.path.join(os.getcwd(), "sample_data"),
        "/app/uploads",
        "/app/app/uploads",
        "/app/backend/uploads",
        "/app/backend/app/uploads",
        "backend/app/uploads",
        "backend/uploads",
        "uploads",
        "sample_data"
    ]
    fns = []
    if storage_path:
        fns.append(os.path.basename(storage_path))
    if filename:
        fns.append(filename)
        fns.append(os.path.basename(filename))

    for cdir in cand_dirs:
        if not cdir or not os.path.isdir(cdir):
            continue
        for fn in fns:
            if not fn:
                continue
            target = os.path.join(cdir, fn)
            if os.path.exists(target):
                candidates.append(target)
            try:
                for af in os.listdir(cdir):
                    if af == fn or af.endswith(f"_{fn}") or af.lower().endswith(fn.lower()) or af.lower().endswith(f"_{fn.lower()}"):
                        candidates.append(os.path.join(cdir, af))
            except Exception:
                pass

    if candidates:
        return max(set(candidates), key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
    return None


def check_file_has_col(file_path: str, col_name: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            header = f.readline().lower()
            return col_name.lower() in [c.strip().strip('"').strip("'") for c in header.split(",")]
    except Exception:
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
        # Fetch project datasets from DB
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

        from app.features.analytics.engine.date_normalizer import DateTimeNormalizer
        from app.features.analytics.schemas import DateDetectionMetadata

        if has_olist_orders and has_olist_items:
            olist_date_det = None
            orders_info = table_name_map.get("olist_orders_dataset") or next((d for name, d in table_name_map.items() if "orders" in name), None)
            if orders_info:
                real_orders_file = resolve_actual_file(orders_info.get("storage_path"), orders_info.get("filename"))
                if real_orders_file and os.path.exists(real_orders_file):
                    try:
                        sdf = pd.read_csv(real_orders_file, usecols=["order_purchase_timestamp"], nrows=100)
                        raw_det = DateTimeNormalizer.detect_format(sdf["order_purchase_timestamp"].dropna().tolist(), "order_purchase_timestamp")
                        olist_date_det = DateDetectionMetadata(**raw_det)
                    except Exception:
                        pass

            candidates.append(
                TimeSeriesCandidate(
                    dataset_id="olist_relational_derived",
                    dataset_name="Olist E-Commerce (Orders + Order Items Joined)",
                    date_columns=["order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date"],
                    metric_columns=["total_order_value (price + freight_value)", "price", "freight_value"],
                    categorical_columns=["product_category_name", "order_status", "customer_state"],
                    is_derived_olist=True,
                    suggested_date="order_purchase_timestamp",
                    suggested_metric="total_order_value (price + freight_value)",
                    dataset_type="Transactional / Time Series",
                    is_time_series_capable=True,
                    detected_date_metadata=olist_date_det
                )
            )

        # Inspect individual dataset files dynamically
        for ds in datasets_info:
            storage_path = ds.get("storage_path")
            real_file = resolve_actual_file(storage_path, ds.get("filename"))
            if not real_file or not os.path.exists(real_file):
                continue

            try:
                # Fast sample read to avoid scanning huge datasets
                if real_file.lower().endswith(".csv"):
                    try:
                        df = pd.read_csv(real_file, nrows=500, low_memory=False)
                    except Exception:
                        df = load_dataset(real_file)
                else:
                    df = load_dataset(real_file)

                if df.empty:
                    continue

                date_cols = []
                metric_cols = []
                cat_cols = []

                for col in df.columns:
                    col_str = str(col)
                    col_lower = col_str.lower()
                    col_tokens = set(re.split(r'[\W_]+', col_lower))

                    # 1. Check Date Column using dynamic strict validation
                    if is_valid_date_column(df, col_str):
                        date_cols.append(col_str)
                        continue

                    # 2. Check Numeric Metric
                    is_excluded_id = (
                        any(k in col_tokens for k in ID_EXCLUDE_KEYWORDS)
                        or col_lower.endswith("_id")
                        or col_lower.startswith("id_")
                        or col_lower in ["id", "uuid", "guid"]
                    )
                    if pd.api.types.is_numeric_dtype(df[col_str]) and not is_excluded_id:
                        metric_cols.append(col_str)
                    elif df[col_str].dtype == 'object':
                        # Check if string column contains formatted numeric values (e.g. $1,200.50)
                        sample_vals = df[col_str].dropna().head(30)
                        if len(sample_vals) > 0 and not is_excluded_id:
                            cleaned_nums = pd.to_numeric(
                                sample_vals.astype(str).str.replace(r'[\$,%]', '', regex=True).str.strip(),
                                errors='coerce'
                            )
                            if cleaned_nums.dropna().shape[0] / len(sample_vals) >= 0.8:
                                metric_cols.append(col_str)
                                continue

                        # Check low cardinality category for breakdown
                        unique_cnt = df[col_str].nunique()
                        if 1 < unique_cnt < 100:
                            cat_cols.append(col_str)

                # If dataset has valid temporal columns but no numeric metric, supply row_count
                if len(date_cols) > 0 and len(metric_cols) == 0:
                    metric_cols.append("row_count (Total Events / Volume)")

                is_ts_capable = len(date_cols) > 0 and len(metric_cols) > 0
                dataset_type = "Transactional / Time Series" if is_ts_capable else "Dimension / Master Data"

                # Prioritize primary timestamp/date columns
                suggested_date = None
                if date_cols:
                    date_priority = ["purchase", "order", "created", "trans", "sale", "date", "timestamp", "time"]
                    for kw in date_priority:
                        match = next((c for c in date_cols if kw in c.lower()), None)
                        if match:
                            suggested_date = match
                            break
                    if not suggested_date:
                        suggested_date = date_cols[0]

                suggested_metric = None
                for m in metric_cols:
                    if any(k in m.lower() for k in METRIC_KEYWORDS):
                        suggested_metric = m
                        break
                if not suggested_metric and metric_cols:
                    suggested_metric = metric_cols[0]

                detected_date_meta = None
                if suggested_date and suggested_date in df.columns:
                    try:
                        raw_det = DateTimeNormalizer.detect_format(df[suggested_date].dropna().head(100).tolist(), suggested_date)
                        detected_date_meta = DateDetectionMetadata(**raw_det)
                    except Exception:
                        pass

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
                        is_time_series_capable=is_ts_capable,
                        detected_date_metadata=detected_date_meta
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
        db: Optional[AsyncSession] = None,
        user_date_format: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Constructs schema-aware DuckDB SQL query to aggregate project datasets into clean time-series.
        Supports single datasets as well as relational joins (e.g. Olist dataset).
        Resolves table name dynamically from DB metadata or uploaded cache.
        Uses DateTimeNormalizer for dynamic format detection and safe SQL expression generation.
        """
        from app.features.analytics.engine.date_normalizer import DateTimeNormalizer

        agg_fmt = "month"
        if aggregation.lower() == "daily":
            agg_fmt = "day"
        elif aggregation.lower() == "weekly":
            agg_fmt = "week"

        # Check Olist derived join - only if explicitly requested or derived ID
        is_olist_derived = (
            dataset_id == "olist_relational_derived"
            or (dataset_id and "olist" in str(dataset_id).lower() and "derived" in str(dataset_id).lower())
            or (not dataset_id and date_column and "order_purchase_timestamp" in str(date_column).lower())
        )
        if is_olist_derived:
            date_col = date_column or "order_purchase_timestamp"
            orders_source = "olist_orders_dataset"
            items_source = "olist_order_items_dataset"
            products_source = None
            customers_source = None
            orders_real_file = None

            if db:
                from app.features.datasets.models import Dataset
                stmt = select(Dataset).where(Dataset.project_id == project_id)
                res = await db.execute(stmt)
                d_items = res.scalars().all()
                for d in d_items:
                    fname = (d.filename or "").lower()
                    d_table = d.duckdb_table or ""
                    real_file = resolve_actual_file(d.storage_path, d.filename)
                    if "orders" in fname and "items" not in fname and "reviews" not in fname:
                        if real_file:
                            clean_p = real_file.replace("\\", "/")
                            orders_source = f"read_csv_auto('{clean_p}')"
                            orders_real_file = real_file
                        elif d_table:
                            orders_source = f'"{d_table}"'
                    elif "items" in fname or "order_items" in fname:
                        if real_file:
                            clean_p = real_file.replace("\\", "/")
                            if not check_file_has_col(real_file, "freight_value"):
                                items_source = f"(SELECT *, CAST(0.0 AS DOUBLE) AS freight_value FROM read_csv_auto('{clean_p}'))"
                            else:
                                items_source = f"read_csv_auto('{clean_p}')"
                        elif d_table:
                            items_source = f'"{d_table}"'
                    elif "products" in fname:
                        if real_file:
                            clean_p = real_file.replace("\\", "/")
                            products_source = f"read_csv_auto('{clean_p}')"
                        elif d_table:
                            products_source = f'"{d_table}"'
                    elif "customers" in fname:
                        if real_file:
                            clean_p = real_file.replace("\\", "/")
                            customers_source = f"read_csv_auto('{clean_p}')"
                        elif d_table:
                            customers_source = f'"{d_table}"'

            if not orders_real_file:
                orders_real_file = resolve_actual_file(None, "olist_orders_dataset.csv")

            # Sample dates from orders file or table for dynamic format detection
            sample_dates = []
            if orders_real_file and os.path.exists(orders_real_file):
                try:
                    sdf = pd.read_csv(orders_real_file, usecols=[date_col], nrows=100)
                    sample_dates = sdf[date_col].dropna().tolist()
                except Exception:
                    pass

            if not sample_dates:
                try:
                    from app.core.database import get_duckdb_conn
                    gen = get_duckdb_conn()
                    c = next(gen)
                    res = c.execute(f'SELECT CAST("{date_col}" AS VARCHAR) FROM {orders_source} WHERE "{date_col}" IS NOT NULL LIMIT 100').fetchall()
                    sample_dates = [r[0] for r in res if r and r[0]]
                except Exception:
                    pass

            date_meta = DateTimeNormalizer.get_cached_or_detect(
                cache_key=f"{project_id}:olist:{date_col}",
                sample_values=sample_dates,
                column_name=date_col,
                user_format=user_date_format
            )
            detected_duckdb_format = date_meta.get("duckdb_format")

            # Build FROM clause with joined tables (LEFT JOIN to prevent dropping orders if items table is subset or sparse)
            from_clause = f"{orders_source} orders LEFT JOIN {items_source} items ON orders.order_id = items.order_id"
            if products_source:
                from_clause += f" LEFT JOIN {products_source} products ON items.product_id = products.product_id"
            if customers_source:
                from_clause += f" LEFT JOIN {customers_source} customers ON orders.customer_id = customers.customer_id"

            # Determine metric aggregation expression
            target_str = str(target_column or "").lower()
            if "row_count" in target_str or "order_count" in target_str or target_str in ["count", "orders"]:
                metric_expr = "COUNT(DISTINCT orders.order_id)"
            elif target_str == "freight_value":
                metric_expr = "SUM(COALESCE(items.freight_value, 0))"
            else:
                metric_expr = "SUM(items.price + COALESCE(items.freight_value, 0))"

            # Safe group by resolution across joined tables
            select_group = ""
            group_sql = ""
            if group_by and str(group_by).strip().lower() not in ["", "none", "null", "all", "undefined"]:
                clean_grp = group_by.strip().replace('"', '')
                grp_col = None
                if "category" in clean_grp.lower() or "product" in clean_grp.lower():
                    if products_source:
                        grp_col = f'COALESCE(products."{clean_grp}", \'Uncategorized\')'
                elif clean_grp in ["order_status", "order_id"]:
                    grp_col = f'orders."{clean_grp}"'
                elif clean_grp in ["customer_state", "customer_city", "customer_zip_code_prefix"]:
                    if customers_source:
                        grp_col = f'COALESCE(customers."{clean_grp}", \'Unknown\')'
                elif clean_grp in ["seller_id", "order_item_id"]:
                    grp_col = f'items."{clean_grp}"'
                else:
                    if products_source:
                        grp_col = f'COALESCE(products."{clean_grp}", \'Uncategorized\')'
                    else:
                        grp_col = f'items."{clean_grp}"'

                if grp_col:
                    select_group = f", {grp_col} AS group_key"
                    group_sql = f", {grp_col}"

            date_expr = build_duckdb_date_expr(f'orders."{date_col}"', detected_duckdb_format)

            sql = f"""
            SELECT 
              date_trunc('{agg_fmt}', {date_expr}) AS date_bucket,
              {metric_expr} AS metric_value
              {select_group}
            FROM {from_clause}
            WHERE orders."{date_col}" IS NOT NULL AND CAST(orders."{date_col}" AS VARCHAR) != '' AND {date_expr} IS NOT NULL
            GROUP BY 1 {group_sql}
            ORDER BY 1 ASC
            """
            return sql, {
                "dataset_name": "Olist E-Commerce (Derived Join)",
                "date_column": date_col,
                "target_column": target_column or "total_order_value",
                "date_detection": date_meta
            }

        # Single table query resolution
        from app.features.datasets.router import UPLOADED_PATHS_CACHE
        from app.features.auth.models import User
        from app.features.projects.models import Project
        from app.features.datasets.models import Dataset

        d_obj = None
        if db and dataset_id:
            stmt = select(Dataset).where(Dataset.id == dataset_id)
            res = await db.execute(stmt)
            d_obj = res.scalar_one_or_none()

        if db and not d_obj:
            stmt = select(Dataset).where(Dataset.project_id == project_id)
            res = await db.execute(stmt)
            d_items = res.scalars().all()
            if d_items:
                d_obj = next((d for d in d_items if str(d.id) == str(dataset_id)), d_items[0])

        real_file = None
        table_name = None
        ds_name = "Dataset"

        if d_obj:
            ds_name = d_obj.filename or "Dataset"
            table_name = d_obj.duckdb_table or (d_obj.display_name and d_obj.display_name.split(".")[0]) or (d_obj.filename and d_obj.filename.split(".")[0])
            real_file = resolve_actual_file(d_obj.storage_path, d_obj.filename)

        if not real_file:
            for d_id, cached in UPLOADED_PATHS_CACHE.items():
                if str(d_id) == str(dataset_id) or (dataset_id is None and cached.get("project_id") == project_id):
                    table_name = cached.get("duckdb_table") or cached.get("filename", "").split(".")[0]
                    ds_name = cached.get("filename", "Dataset")
                    real_file = resolve_actual_file(cached.get("path"), cached.get("filename"))
                    break

        if real_file and os.path.exists(real_file):
            clean_p = real_file.replace("\\", "/")
            from_clause = f"read_csv_auto('{clean_p}')"
        else:
            clean_table = (table_name or dataset_id or "dataset").strip().lower().replace(" ", "_").replace("-", "_")
            clean_table = "".join(c for c in clean_table if c.isalnum() or c == "_") or "dataset"
            from_clause = f'"{clean_table}"'

        date_col = date_column or "date"
        target_col = target_column or "revenue"

        # Sample dates from single dataset file for dynamic format detection
        sample_dates = []
        if real_file and os.path.exists(real_file):
            try:
                if real_file.lower().endswith(".csv"):
                    sdf = pd.read_csv(real_file, usecols=[date_col], nrows=100)
                else:
                    sdf = load_dataset(real_file)[[date_col]].head(100)
                sample_dates = sdf[date_col].dropna().tolist()
            except Exception:
                pass

        if not sample_dates:
            try:
                from app.core.database import get_duckdb_conn
                gen = get_duckdb_conn()
                c = next(gen)
                res = c.execute(f'SELECT CAST("{date_col}" AS VARCHAR) FROM {from_clause} WHERE "{date_col}" IS NOT NULL LIMIT 100').fetchall()
                sample_dates = [r[0] for r in res if r and r[0]]
            except Exception:
                pass

        date_meta = DateTimeNormalizer.get_cached_or_detect(
            cache_key=f"{project_id}:{dataset_id or 'dataset'}:{date_col}",
            sample_values=sample_dates,
            column_name=date_col,
            user_format=user_date_format
        )
        detected_duckdb_format = date_meta.get("duckdb_format")

        select_group = ""
        group_sql = ""
        if group_by and str(group_by).strip().lower() not in ["", "none", "null", "all", "undefined"]:
            clean_grp = group_by.strip().replace('"', '')
            select_group = f', "{clean_grp}" AS group_key'
            group_sql = f', "{clean_grp}"'

        date_expr = build_duckdb_date_expr(f'"{date_col}"', detected_duckdb_format)

        target_str = str(target_col).lower()
        if "row_count" in target_str or target_str in ["count", "record_count", "records"]:
            metric_expr = "COUNT(*)"
        else:
            clean_target = target_col.replace('"', '')
            metric_expr = f'SUM(COALESCE(TRY_CAST(REGEXP_REPLACE(CAST("{clean_target}" AS VARCHAR), \'[^0-9.-]\', \'\', \'g\') AS DOUBLE), 0.0))'

        sql = f"""
        SELECT 
          date_trunc('{agg_fmt}', {date_expr}) AS date_bucket,
          {metric_expr} AS metric_value
          {select_group}
        FROM {from_clause}
        WHERE "{date_col}" IS NOT NULL AND CAST("{date_col}" AS VARCHAR) != '' AND {date_expr} IS NOT NULL
        GROUP BY 1 {group_sql}
        ORDER BY 1 ASC
        """

        return sql, {
            "dataset_name": ds_name,
            "date_column": date_col,
            "target_column": target_col,
            "date_detection": date_meta
        }

    @staticmethod
    def build_time_series_query(
        project_id: str,
        dataset_id: Optional[str],
        date_column: Optional[str],
        target_column: Optional[str],
        aggregation: str = "monthly",
        group_by: Optional[str] = None,
        user_date_format: Optional[str] = None
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
                    group_by=group_by,
                    user_date_format=user_date_format
                )
            )
        except Exception:
            agg_fmt = "month" if aggregation.lower() == "monthly" else ("day" if aggregation.lower() == "daily" else "week")
            tbl = (dataset_id or "dataset").replace("-", "_").lower()
            date_col = date_column or "date"
            target_col = target_column or "revenue"
            date_expr = build_duckdb_date_expr(f'"{date_col}"')
            sql = f'SELECT date_trunc(\'{agg_fmt}\', {date_expr}) AS date_bucket, SUM("{target_col}") AS metric_value FROM "{tbl}" WHERE "{date_col}" IS NOT NULL AND {date_expr} IS NOT NULL GROUP BY 1 ORDER BY 1 ASC'
            return sql, {"dataset_name": "Dataset", "date_column": date_col, "target_column": target_col}

    @staticmethod
    async def execute_time_series_pandas_fallback(
        project_id: str,
        dataset_id: Optional[str],
        date_column: Optional[str],
        target_column: Optional[str],
        aggregation: str = "monthly",
        group_by: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        user_date_format: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Resilient Pandas fallback that directly reads files and computes time-series aggregation
        if DuckDB query returns zero rows or encounters SQL syntax/path resolution edge cases.
        Uses DateTimeNormalizer for dynamic date parsing and format adherence.
        """
        from app.features.analytics.engine.date_normalizer import DateTimeNormalizer
        from app.features.datasets.models import Dataset
        from app.core.json_utils import make_json_serializable

        is_olist_derived = (
            dataset_id == "olist_relational_derived"
            or (dataset_id and "olist" in str(dataset_id).lower() and "derived" in str(dataset_id).lower())
            or (not dataset_id and date_column and "order_purchase_timestamp" in str(date_column).lower())
        )

        freq_period = "M"
        if aggregation.lower() == "daily":
            freq_period = "D"
        elif aggregation.lower() == "weekly":
            freq_period = "W-MON"

        try:
            if is_olist_derived:
                orders_file = resolve_actual_file(None, "olist_orders_dataset.csv")
                items_file = resolve_actual_file(None, "olist_order_items_dataset.csv")

                if db and (not orders_file or not items_file):
                    stmt = select(Dataset).where(Dataset.project_id == project_id)
                    res = await db.execute(stmt)
                    for d in res.scalars().all():
                        fn = (d.filename or "").lower()
                        if "orders" in fn and "items" not in fn and not orders_file:
                            orders_file = resolve_actual_file(d.storage_path, d.filename)
                        elif ("items" in fn or "order_items" in fn) and not items_file:
                            items_file = resolve_actual_file(d.storage_path, d.filename)

                if not orders_file or not items_file:
                    return []

                df_orders = pd.read_csv(orders_file, low_memory=False)
                df_items = pd.read_csv(items_file, low_memory=False)

                df = pd.merge(df_orders, df_items, on="order_id", how="left")
                d_col = date_column or "order_purchase_timestamp"
                if d_col not in df.columns:
                    d_col = next((c for c in df.columns if "date" in c.lower() or "timestamp" in c.lower()), None)
                if not d_col:
                    return []

                parsed_dates = DateTimeNormalizer.normalize_series(df[d_col], user_format=user_date_format, column_name=d_col)
                df["date_bucket"] = parsed_dates.dt.to_period(freq_period).dt.to_timestamp()

                target_str = str(target_column or "").lower()
                if "row_count" in target_str or "order_count" in target_str or target_str in ["count", "orders"]:
                    df["metric_value"] = 1.0
                elif target_str == "price":
                    df["metric_value"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
                elif target_str == "freight_value":
                    df["metric_value"] = pd.to_numeric(df.get("freight_value", 0.0), errors="coerce").fillna(0.0)
                else:
                    df["metric_value"] = (
                        pd.to_numeric(df["price"], errors="coerce").fillna(0.0) +
                        pd.to_numeric(df.get("freight_value", 0.0), errors="coerce").fillna(0.0)
                    )

                clean_df = df.dropna(subset=["date_bucket"])
                if clean_df.empty:
                    return []

                agg_df = clean_df.groupby("date_bucket")["metric_value"].sum().reset_index()
                agg_df = agg_df.sort_values(by="date_bucket")

                rows = []
                for _, r in agg_df.iterrows():
                    rows.append({
                        "date_bucket": r["date_bucket"].isoformat() if hasattr(r["date_bucket"], "isoformat") else str(r["date_bucket"]),
                        "metric_value": float(r["metric_value"])
                    })
                return rows

            # Single dataset fallback
            real_file = None
            if db and dataset_id:
                stmt = select(Dataset).where(Dataset.id == dataset_id)
                res = await db.execute(stmt)
                d_obj = res.scalar_one_or_none()
                if d_obj:
                    real_file = resolve_actual_file(d_obj.storage_path, d_obj.filename)

            if not real_file:
                for d_id, cached in UPLOADED_PATHS_CACHE.items():
                    if str(d_id) == str(dataset_id) or (dataset_id is None and cached.get("project_id") == project_id):
                        real_file = resolve_actual_file(cached.get("path"), cached.get("filename"))
                        break

            if not real_file and db:
                stmt = select(Dataset).where(Dataset.project_id == project_id)
                res = await db.execute(stmt)
                d_items = res.scalars().all()
                if d_items:
                    real_file = resolve_actual_file(d_items[0].storage_path, d_items[0].filename)

            if not real_file or not os.path.exists(real_file):
                return []

            if real_file.lower().endswith(".csv"):
                df = pd.read_csv(real_file, low_memory=False)
            else:
                df = load_dataset(real_file)

            if df.empty:
                return []

            d_col = date_column
            if not d_col or d_col not in df.columns:
                for c in df.columns:
                    if is_valid_date_column(df, c):
                        d_col = c
                        break
            if not d_col:
                return []

            parsed_dates = DateTimeNormalizer.normalize_series(df[d_col], user_format=user_date_format, column_name=d_col)
            df["date_bucket"] = parsed_dates.dt.to_period(freq_period).dt.to_timestamp()

            t_col = target_column
            target_str = str(t_col or "").lower()
            if "row_count" in target_str or target_str in ["count", "record_count", "records"]:
                df["metric_value"] = 1.0
            else:
                if not t_col or t_col not in df.columns:
                    # Pick first numeric column
                    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                    t_col = num_cols[0] if num_cols else df.columns[-1]

                cleaned_series = (
                    df[t_col]
                    .astype(str)
                    .str.replace(r'[\$,%]', '', regex=True)
                    .str.strip()
                )
                df["metric_value"] = pd.to_numeric(cleaned_series, errors="coerce").fillna(0.0)

            clean_df = df.dropna(subset=["date_bucket"])
            if clean_df.empty:
                return []

            agg_df = clean_df.groupby("date_bucket")["metric_value"].sum().reset_index()
            agg_df = agg_df.sort_values(by="date_bucket")

            rows = []
            for _, r in agg_df.iterrows():
                rows.append({
                    "date_bucket": r["date_bucket"].isoformat() if hasattr(r["date_bucket"], "isoformat") else str(r["date_bucket"]),
                    "metric_value": float(r["metric_value"])
                })
            return rows
        except Exception as e:
            logger.error(f"Pandas fallback aggregation failed: {e}", exc_info=True)
            return []

