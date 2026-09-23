import re
import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns for detecting schema / metadata questions
COLUMN_COUNT_PATTERNS = [
    r'\b(how\s+many|number\s+of|count\s+of|total)\s+(total\s+)?(columns|cols|fields|attributes|features|variables)\b',
    r'\b(columns?|fields?)\s+(count|total|number)\b',
    r'\bwhat\s+(is|are)\s+the\s+(total\s+)?(count|number)\s+of\s+columns\b',
    r'\bhow\s+many\s+columns\b',
]

COLUMN_LIST_PATTERNS = [
    r'\b(what\s+are\s+the|list|show|get|display|print|enumerate|view|give\s+me)\s+(all\s+the\s+|the\s+)?(total\s+)?(columns|column\s+names|fields|attributes|features)\b',
    r'\bwhat\s+columns\b',
    r'\bwhich\s+columns\b',
    r'\bcolumn\s+names\b',
    r'\bnames\s+of\s+(the\s+)?columns\b',
    r'\b(available|existing)\s+columns\b',
    r'\ball\s+columns\b',
]

ROW_COUNT_PATTERNS = [
    r'\b(how\s+many|number\s+of|count\s+of|total)\s+(total\s+)?(rows|records|entries|samples|tuples|observations)\b',
    r'\b(rows?|records?)\s+(count|total|number)\b',
    r'\bwhat\s+(is|are)\s+the\s+(total\s+)?(count|number)\s+of\s+(rows|records)\b',
    r'\bhow\s+many\s+rows\b',
    r'\bhow\s+many\s+records\b',
]

SCHEMA_STRUCTURE_PATTERNS = [
    r'\b(what\s+is\s+the|show|describe|get|view|display)\s+(the\s+)?(schema|structure|data\s+types?|table\s+structure|table\s+schema)\b',
    r'\b(dataset|table)\s+schema\b',
    r'\bdata\s+types?\b',
    r'\bdescribe\s+(the\s+)?(table|dataset|data)\b',
    r'\bdescribe\s+[\w\-]+\.(csv|xlsx|xls|json|parquet)\b',
]

DATASET_SHAPE_PATTERNS = [
    r'\b(rows\s+and\s+columns|columns\s+and\s+rows|shape|dimensions|dimension|size)\s+of\b',
    r'\bhow\s+many\s+rows\s+and\s+(how\s+many\s+)?columns\b',
    r'\bshape\s+of\s+(the\s+)?dataset\b',
    r'\bdataset\s+(shape|dimensions)\b',
]


def is_schema_metadata_query(query: str) -> bool:
    """
    Returns True if the user query is asking about dataset schema, column names/count,
    row count, or table structure rather than an aggregated business metric.
    """
    if not query or not query.strip():
        return False
    q = query.strip().lower()

    # Queries asking for aggregations grouped by a dimension are NOT pure schema queries
    # e.g., "count of orders by status", "total sales by category"
    if re.search(r'\b(by\s+\w+|group\s+by|per\s+\w+|highest|lowest|top\s+\d+|bottom\s+\d+|trend|average|avg|sum\s+of)\b', q):
        # But if it explicitly says "total columns" or "how many columns", it's still a schema query
        if not any(re.search(pat, q) for pat in COLUMN_COUNT_PATTERNS + COLUMN_LIST_PATTERNS):
            return False

    all_patterns = (
        COLUMN_COUNT_PATTERNS +
        COLUMN_LIST_PATTERNS +
        ROW_COUNT_PATTERNS +
        SCHEMA_STRUCTURE_PATTERNS +
        DATASET_SHAPE_PATTERNS
    )
    return any(re.search(pat, q) for pat in all_patterns)


def classify_schema_query(query: str) -> str:
    """
    Categorizes the schema question into:
    - 'column_count': asking specifically for the number/count of columns
    - 'column_list': asking for the names/list of columns
    - 'row_count': asking specifically for the total row count
    - 'dataset_shape': asking for rows and columns / dimensions
    - 'schema_structure': asking for data types / full table schema
    """
    q = query.strip().lower()

    if any(re.search(pat, q) for pat in DATASET_SHAPE_PATTERNS):
        return "dataset_shape"
    if any(re.search(pat, q) for pat in COLUMN_COUNT_PATTERNS):
        return "column_count"
    if any(re.search(pat, q) for pat in COLUMN_LIST_PATTERNS):
        return "column_list"
    if any(re.search(pat, q) for pat in ROW_COUNT_PATTERNS):
        return "row_count"
    if any(re.search(pat, q) for pat in SCHEMA_STRUCTURE_PATTERNS):
        return "schema_structure"
    return "schema_structure"


def inspect_dataset_schema(
    view_name: str,
    filename: str,
    resolved: Dict[str, Any],
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inspects DuckDB (with fallbacks to resolved metadata) to retrieve exact column names,
    data types, and total row count.
    """
    from app.core.database import get_duckdb_conn
    from app.features.analytics.service import register_all_datasets_in_duckdb

    columns: List[Dict[str, Any]] = []
    total_rows: Optional[int] = None
    gen = get_duckdb_conn()
    conn = next(gen)

    try:
        try:
            register_all_datasets_in_duckdb(conn, project_id)
        except Exception as e:
            logger.warning(f"DuckDB registration warning in schema inspector: {e}")

        # 1. Fetch Columns from DuckDB
        try:
            # Check if view exists
            pragma_rows = conn.execute(f"PRAGMA table_info('{view_name}')").fetchall()
            for idx, row in enumerate(pragma_rows, 1):
                # (cid, name, type, notnull, dflt_value, pk)
                col_name = str(row[1])
                col_type = str(row[2])
                nullable = not bool(row[3])
                columns.append({
                    "index": idx,
                    "name": col_name,
                    "type": col_type,
                    "nullable": nullable
                })
        except Exception as e:
            logger.warning(f"PRAGMA table_info failed for '{view_name}': {e}. Trying DESCRIBE...")
            try:
                desc_rows = conn.execute(f'DESCRIBE "{view_name}"').fetchall()
                for idx, row in enumerate(desc_rows, 1):
                    col_name = str(row[0])
                    col_type = str(row[1])
                    columns.append({
                        "index": idx,
                        "name": col_name,
                        "type": col_type,
                        "nullable": True
                    })
            except Exception as de:
                logger.warning(f"DESCRIBE failed for '{view_name}': {de}")

        # Fallback to resolved schema/columns_json if DuckDB table wasn't available
        if not columns:
            schema_dict = resolved.get("schema") or {}
            if isinstance(schema_dict, str):
                try:
                    schema_dict = json.loads(schema_dict)
                except Exception:
                    schema_dict = {}

            if schema_dict:
                for idx, (col_name, details) in enumerate(schema_dict.items(), 1):
                    col_type = details.get("type", "VARCHAR") if isinstance(details, dict) else str(details)
                    columns.append({
                        "index": idx,
                        "name": col_name,
                        "type": col_type,
                        "nullable": True
                    })

            cols_list = resolved.get("columns") or resolved.get("columns_json")
            if not columns and cols_list:
                if isinstance(cols_list, str):
                    try:
                        cols_list = json.loads(cols_list)
                    except Exception:
                        cols_list = []
                if isinstance(cols_list, list):
                    for idx, col_name in enumerate(cols_list, 1):
                        columns.append({
                            "index": idx,
                            "name": str(col_name),
                            "type": "VARCHAR",
                            "nullable": True
                        })

        # 2. Fetch Row Count from DuckDB
        try:
            count_res = conn.execute(f'SELECT COUNT(*) FROM "{view_name}"').fetchone()
            if count_res and count_res[0] is not None:
                total_rows = int(count_res[0])
        except Exception as ce:
            logger.warning(f"SELECT COUNT failed for '{view_name}': {ce}")

        if total_rows is None:
            raw_rows = resolved.get("rows")
            if raw_rows is not None:
                try:
                    total_rows = int(raw_rows)
                except Exception:
                    total_rows = None
    finally:
        try:
            gen.close()
        except Exception:
            pass

    return {
        "view_name": view_name,
        "filename": filename,
        "columns": columns,
        "total_columns": len(columns),
        "total_rows": total_rows,
    }


def format_schema_response(query: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a structured and clean markdown response answering the user's specific
    schema/metadata question, along with table specifications for UI visualization.
    """
    category = classify_schema_query(query)
    filename = schema_info.get("filename") or "dataset"
    view_name = schema_info.get("view_name") or filename
    columns = schema_info.get("columns", [])
    total_cols = schema_info.get("total_columns", len(columns))
    total_rows = schema_info.get("total_rows")

    rows_str = f"{total_rows:,}" if total_rows is not None else "N/A"

    # Construct clean markdown response text
    if category == "column_count":
        header_text = f"The dataset **{filename}** has **{total_cols} total columns**."
        if total_rows is not None:
            header_text += f" (Total records: **{rows_str}**)"
        sql_query = f'DESCRIBE "{view_name}";'
    elif category == "row_count":
        header_text = f"The dataset **{filename}** contains **{rows_str} total rows** (and **{total_cols} columns**)."
        sql_query = f'SELECT COUNT(*) AS total_rows FROM "{view_name}";'
    elif category == "dataset_shape":
        header_text = (
            f"The dataset **{filename}** has dimensions of **{rows_str} rows** "
            f"and **{total_cols} columns**."
        )
        sql_query = f'DESCRIBE "{view_name}";'
    elif category == "column_list":
        header_text = f"Here are the **{total_cols} columns** in **{filename}**:"
        sql_query = f'DESCRIBE "{view_name}";'
    else:  # schema_structure
        header_text = (
            f"### Dataset Schema: **{filename}**\n\n"
            f"- **Total Columns**: **{total_cols}**\n"
            f"- **Total Records**: **{rows_str}**"
        )
        sql_query = f'DESCRIBE "{view_name}";'

    # Build Markdown table of columns
    lines = [header_text, ""]
    if columns:
        lines.append("| # | Column Name | Data Type | Nullable |")
        lines.append("|---|---|---|---|")
        for col in columns:
            nullable_str = "Yes" if col.get("nullable", True) else "No"
            lines.append(f"| {col['index']} | **{col['name']}** | `{col['type']}` | {nullable_str} |")
        lines.append("")

    lines.append(f"```sql\n{sql_query}\n```")
    response_md = "\n".join(lines)

    # Format table for UI rendering in frontend
    ui_table = {
        "columns": [
            {"accessorKey": "index", "header": "#"},
            {"accessorKey": "column_name", "header": "Column Name"},
            {"accessorKey": "data_type", "header": "Data Type"},
            {"accessorKey": "nullable", "header": "Nullable"}
        ],
        "data": [
            {
                "index": col["index"],
                "column_name": col["name"],
                "data_type": col["type"],
                "nullable": "Yes" if col.get("nullable", True) else "No"
            }
            for col in columns
        ]
    }

    # Format sql_result dictionary for state compatibility
    sql_result = {
        "columns": ["index", "column_name", "data_type", "nullable"],
        "rows": ui_table["data"],
        "row_count": len(columns),
        "elapsed_ms": 2
    }

    return {
        "response": response_md,
        "sql_query": sql_query,
        "sql_result": sql_result,
        "table": ui_table,
        "data": ui_table["data"],
        "columns": ["index", "column_name", "data_type", "nullable"],
        "row_count": len(columns)
    }
