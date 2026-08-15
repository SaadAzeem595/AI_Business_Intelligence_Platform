import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core.llm import LLMService, LLMConfigurationError
from app.features.analytics.service import AnalyticsService
from app.features.agents.semantic_sql import (
    build_catalog_from_datasets,
    parse_and_generate_semantic_sql,
    validate_semantic_sql
)

logger = logging.getLogger(__name__)


def list_project_datasets(available_datasets: Optional[List[Dict[str, Any]]] = None, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Tool function: list_project_datasets()
    Returns normalized dataset metadata belonging to the current project.
    """
    if not available_datasets:
        return []

    project_datasets = []
    seen_ids = set()

    for item in available_datasets:
        is_dict = isinstance(item, dict)
        item_id = str(item.get("id") if is_dict else item.id)
        if item_id in seen_ids:
            continue
        
        item_proj = item.get("project_id") if is_dict else getattr(item, "project_id", None)
        # Filter by project_id if explicitly specified
        if project_id and item_proj and str(item_proj) != str(project_id):
            continue

        seen_ids.add(item_id)
        project_datasets.append(item if is_dict else {
            "id": item_id,
            "filename": item.filename,
            "display_name": getattr(item, "display_name", None),
            "storage_path": getattr(item, "storage_path", None),
            "duckdb_table": getattr(item, "duckdb_table", None),
            "type": getattr(item, "type", "CSV"),
            "columns_json": getattr(item, "columns_json", None),
            "schema_json": getattr(item, "schema_json", None),
            "rows": getattr(item, "rows", 0),
            "project_id": item_proj
        })

    return project_datasets


def get_dataset_schema(dataset_id: str, available_datasets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Tool function: get_dataset_schema(dataset_id)
    Returns full table & column schema for the specified dataset.
    """
    catalog = build_catalog_from_datasets(available_datasets)
    for entry in catalog:
        if entry["id"].lower() == dataset_id.lower() or entry["filename"].lower() == dataset_id.lower() or entry["table_name"].lower() == dataset_id.lower():
            return entry
    if catalog:
        return catalog[0]
    return None


def get_dataset_preview(dataset_id: str, available_datasets: List[Dict[str, Any]], limit: int = 5, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Tool function: get_dataset_preview(dataset_id)
    Executes a SELECT preview query against the DuckDB table for dataset_id.
    """
    schema_entry = get_dataset_schema(dataset_id, available_datasets)
    if not schema_entry:
        return None
    table_name = schema_entry["table_name"]
    query = f'SELECT * FROM "{table_name}" LIMIT {limit}'
    try:
        res = AnalyticsService.execute_duckdb_query(query, project_id=project_id)
        return {
            "table_name": table_name,
            "columns": res.columns,
            "rows": res.rows,
            "count": len(res.rows)
        }
    except Exception as e:
        logger.error(f"Failed to fetch preview for table {table_name}: {e}")
        return None


from app.features.agents.relationship_graph import build_project_relationship_graph


def generate_sql(
    user_query: str,
    available_datasets: List[Dict[str, Any]],
    target_dataset: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
    retry_count: int = 0,
    last_error: Optional[str] = None
) -> Tuple[Optional[str], str]:
    """
    Tool function: generate_sql()
    Generates read-only DuckDB SQL using OpenRouter LLM (or semantic fallback) given actual database schemas.
    Returns (sql_query, explanation_or_error_msg).
    """
    catalog = build_catalog_from_datasets(available_datasets)
    if not catalog:
        return None, "No active datasets found for project."

    rel_graph = build_project_relationship_graph(catalog)
    rel_summary = rel_graph.get_summary()

    # If LLM is configured, construct prompt with actual schemas
    if LLMService.is_configured():
        try:
            key, provider = LLMService.get_api_key_and_provider()
            model_name = LLMService.get_configured_model()

            all_tables_info = ""
            for tbl in catalog:
                cols_str = ", ".join(f"\"{col_info['name']}\" ({col_info['type']})" for col_info in tbl["columns"].values())
                all_tables_info += f"- Table: \"{tbl['table_name']}\" (File: {tbl['filename']}) (Columns: {cols_str})\n"

            relationships_info = ""
            for rel in rel_summary.get("relationships", []):
                relationships_info += f"- Join key: \"{rel['table1']}\".\"{rel['table1_col']}\" = \"{rel['table2']}\".\"{rel['table2_col']}\"\n"

            target_info = f"Preferred target table: \"{target_dataset['table_name']}\"\n" if target_dataset and "table_name" in target_dataset else ""
            error_feedback = f"\nPREVIOUS ATTEMPT ERROR (Retry #{retry_count}): {last_error}\nPlease fix the SQL query to resolve this error.\n" if last_error else ""

            system_prompt = (
                "You are an expert SQL Generator for DuckDB. Your task is to generate a valid, highly accurate DuckDB SQL query.\n"
                "RULES:\n"
                "1. Output ONLY raw executable DuckDB SQL. Do NOT wrap in markdown code fences or explain.\n"
                "2. Perform ONLY read operations (SELECT).\n"
                "3. Use double quotes around table and column names (e.g., SELECT \"col\" FROM \"table\").\n"
                "4. Match requested dimensions and metrics strictly against the provided table schemas.\n"
                "5. If a request can be answered from a single table (e.g. product count by category), query ONLY that single table without forcing JOINs.\n"
                "6. If a request requires multiple tables (e.g. sales/revenue by category or delivered orders), use the provided relationships to JOIN tables.\n"
                "7. Never invent table or column names that do not exist in the provided database schema.\n"
                "8. For analytical ranking/aggregation, use GROUP BY, SUM(), COUNT(DISTINCT order_id), and ORDER BY."
            )

            user_prompt = (
                f"Project Database Schemas:\n{all_tables_info}\n"
                f"Discovered Table Relationships:\n{relationships_info if relationships_info else 'None'}\n"
                f"{target_info}"
                f"User Question: {user_query}\n"
                f"{error_feedback}\n"
                f"DuckDB SQL query:"
            )


            logger.info(
                f"GENERATING_SQL_VIA_LLM: provider={provider} model={model_name} "
                f"project_id={project_id} retry={retry_count}"
            )

            raw_sql = LLMService.generate_response(system_prompt, user_prompt)
            clean_sql = raw_sql.strip().replace("```sql", "").replace("```", "").strip()

            return clean_sql, f"Generated SQL query using {provider} model '{model_name}'."
        except LLMConfigurationError as e:
            logger.warning(f"LLM generation failed: {e}. Falling back to SemanticSQLPlanner.")
        except Exception as e:
            logger.error(f"Unexpected error in LLM SQL generation: {e}")

    # Fallback to Semantic SQL Builder
    sem_res = parse_and_generate_semantic_sql(user_query, catalog)
    if sem_res.get("success") and sem_res.get("sql"):
        return sem_res["sql"], sem_res.get("explanation", "Generated SQL via semantic planner.")
    elif sem_res.get("missing_dataset_msg"):
        return None, sem_res["missing_dataset_msg"]

    primary_table = target_dataset["table_name"] if target_dataset and "table_name" in target_dataset else catalog[0]["table_name"]
    return f'SELECT * FROM "{primary_table}" LIMIT 5', "Default dataset preview query."


def validate_sql(
    sql_query: Optional[str],
    user_query: str,
    available_datasets: List[Dict[str, Any]],
    target_dataset: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Tool function: validate_sql()
    Performs safety, schema-existence, project-scoping, and semantic intent checks on generated SQL.
    Returns (is_valid, error_reason).
    """
    catalog = build_catalog_from_datasets(available_datasets)
    return validate_semantic_sql(sql_query, user_query, catalog, target_dataset=target_dataset)


def execute_duckdb_query(sql_query: str, project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool function: execute_duckdb_query()
    Executes the validated SQL against DuckDB service and returns rows, columns, and elapsed time.
    """
    res = AnalyticsService.execute_duckdb_query(sql_query, project_id=project_id)
    return {
        "columns": res.columns,
        "rows": res.rows,
        "elapsed_ms": res.elapsedMs,
        "row_count": len(res.rows)
    }


def analyze_query_result(
    user_query: str,
    sql_query: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    target_dataset: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Tool function: analyze_query_result()
    Verifies semantic alignment between user intent ↔ selected dataset ↔ generated SQL ↔ returned results.
    Returns (is_aligned, mismatch_reason).
    """
    if not columns and not rows:
        return False, "Query executed but returned no data rows or columns."

    q_lower = user_query.lower()
    
    # Check category sales intent
    if "category" in q_lower and any(w in q_lower for w in ["sales", "revenue", "orders"]):
        cols_lower = [c.lower() for c in columns]
        has_cat_col = any("cat" in c or "category" in c for c in cols_lower)
        has_val_col = any(v in c for c in cols_lower for v in ["sum", "total", "sales", "revenue", "price", "count", "amount"])
        if not (has_cat_col or has_val_col):
            return False, "Query results lack requested category or sales metrics."

    return True, None


def generate_chart(user_query: str, columns: List[str], rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Tool function: generate_chart()
    Builds chart visualization spec from DuckDB query results.
    """
    if not columns or not rows:
        return None

    numeric_cols = []
    categorical_cols = []
    for col in columns:
        sample_val = rows[0].get(col)
        if isinstance(sample_val, (int, float)) or (isinstance(sample_val, str) and sample_val.replace('.', '', 1).isdigit()):
            numeric_cols.append(col)
        else:
            categorical_cols.append(col)

    if numeric_cols:
        y_col = numeric_cols[0]
        x_col = categorical_cols[0] if categorical_cols else next(c for c in columns if c != y_col)
    else:
        x_col = columns[0]
        y_col = columns[1] if len(columns) > 1 else columns[0]

    chart_type = "bar"
    if "line" in user_query.lower() or "trend" in user_query.lower() or "month" in user_query.lower():
        chart_type = "line"
    elif "pie" in user_query.lower():
        chart_type = "pie"

    chart_data = []
    for r in rows[:15]:
        chart_data.append({
            x_col: str(r.get(x_col, "")),
            y_col: float(r.get(y_col, 0)) if isinstance(r.get(y_col), (int, float)) else 0.0
        })

    return {
        "type": chart_type,
        "data": chart_data,
        "xKey": x_col,
        "yKeys": [y_col]
    }
