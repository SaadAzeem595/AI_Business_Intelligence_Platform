import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)


def build_catalog_from_datasets(available_datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizes dataset metadata into a uniform catalog format with lowercased table names and column maps.
    """
    catalog = []
    seen_tables = set()

    for item in available_datasets:
        is_dict = isinstance(item, dict)
        item_id = str(item.get("id") if is_dict else item.id)
        filename = item.get("filename") if is_dict else (item.filename or "")
        duckdb_table = item.get("duckdb_table") if is_dict else getattr(item, "duckdb_table", None)
        
        table_name = duckdb_table
        if not table_name:
            table_name = os.path.splitext(filename)[0].lower().replace(" ", "_").replace("-", "_").replace(".", "_")
            
        if table_name in seen_tables:
            continue
        seen_tables.add(table_name)
        
        # Parse schema
        schema_json = item.get("schema_json") if is_dict else getattr(item, "schema_json", None)
        cols_json = item.get("columns_json") if is_dict else getattr(item, "columns_json", None)
        
        columns_dict = {}
        if schema_json:
            try:
                s_val = json.loads(schema_json) if isinstance(schema_json, str) else schema_json
                if isinstance(s_val, dict):
                    for col_name, info in s_val.items():
                        col_type = info.get("type", "UNKNOWN") if isinstance(info, dict) else str(info)
                        columns_dict[col_name.lower()] = {
                            "name": col_name,
                            "type": col_type
                        }
            except Exception:
                pass
                
        if not columns_dict and cols_json:
            try:
                c_val = json.loads(cols_json) if isinstance(cols_json, str) else cols_json
                if isinstance(c_val, list):
                    for col_name in c_val:
                        columns_dict[str(col_name).lower()] = {
                            "name": str(col_name),
                            "type": "UNKNOWN"
                        }
            except Exception:
                pass
                
        display_name = item.get("display_name") if is_dict else getattr(item, "display_name", None)
        
        catalog.append({
            "id": item_id,
            "filename": filename,
            "table_name": table_name,
            "display_name": display_name or table_name,
            "columns": columns_dict
        })

    return catalog


def find_column_in_catalog(catalog: List[Dict[str, Any]], keywords: List[str]) -> List[Tuple[Dict[str, Any], str]]:
    """
    Searches the catalog for tables containing columns matching any of the given keywords.
    Returns list of tuples: (table_entry, matched_column_original_name).
    """
    matches = []
    for table in catalog:
        for col_lower, col_info in table["columns"].items():
            if any(kw in col_lower for kw in keywords):
                matches.append((table, col_info["name"]))
    return matches


def find_join_key(table1: Dict[str, Any], table2: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Finds matching join columns between two tables.
    Returns tuple: (table1_col_name, table2_col_name) or None.
    """
    # Priority join keys
    priority_keys = ["product_id", "order_id", "customer_id", "user_id", "item_id", "seller_id", "category_id"]
    
    t1_cols = table1["columns"]
    t2_cols = table2["columns"]

    # First check priority keys
    for p_key in priority_keys:
        if p_key in t1_cols and p_key in t2_cols:
            return (t1_cols[p_key]["name"], t2_cols[p_key]["name"])

    # Next check any matching column name
    common_cols = set(t1_cols.keys()).intersection(set(t2_cols.keys()))
    if common_cols:
        matched_key = sorted(list(common_cols))[0]
        return (t1_cols[matched_key]["name"], t2_cols[matched_key]["name"])

    return None


def is_analytical_query(query: str) -> bool:
    """
    Determines if the user's question requires analytical SQL (aggregation, ranking, comparison, trends).
    """
    q = query.lower()
    analytical_keywords = [
        "highest", "most", "top", "lowest", "least", "best", "worst",
        "orders", "sales", "revenue", "trend", "monthly", "average", "avg",
        "total", "sum", "count", "distribution", "category", "categories",
        "product", "products", "customer", "customers", "user", "users",
        "by category", "by product", "by customer", "by state", "by month",
        "which category", "which product", "which customer", "performance"
    ]
    return any(kw in q for kw in analytical_keywords)


def pick_table_matching_query(matches: List[Tuple[Dict[str, Any], str]], q_lower: str) -> Optional[Tuple[Dict[str, Any], str]]:
    if not matches:
        return None
    for match in matches:
        t = match[0]
        fn = t.get("filename", "").lower()
        tb = t.get("table_name", "").lower()
        fn_base = os.path.splitext(fn)[0] if fn else ""
        if (fn and fn in q_lower) or (fn_base and len(fn_base) > 3 and fn_base in q_lower) or (tb and tb in q_lower):
            return match
    return matches[0]


from app.features.agents.relationship_graph import build_project_relationship_graph


def parse_and_generate_semantic_sql(query: str, catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes user intent, checks dataset availability across the project, resolves join relationships,
    and returns a structured result dict:
      {
        "success": True/False,
        "sql": str,
        "explanation": str,
        "missing_dataset_msg": str (if dataset/column is missing),
        "tables_used": List[str]
      }
    """
    if not catalog:
        return {
            "success": False,
            "sql": None,
            "explanation": None,
            "missing_dataset_msg": "No datasets are currently available in the active project.",
            "tables_used": []
        }

    q_lower = query.lower()
    rel_graph = build_project_relationship_graph(catalog)

    # 0. Check if query explicitly specifies an unknown dataset filename
    req_file_match = re.search(r'\b([\w\-]+\.(csv|xlsx|xls|json|pdf|parquet))\b', query, re.IGNORECASE)
    if req_file_match:
        req_file = req_file_match.group(1).lower()
        if not any(t.get("filename", "").lower() == req_file for t in catalog):
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": f"I couldn't analyze the requested dataset because '{req_file}' was not found in the active project.",
                "tables_used": []
            }

    # 1. Detect requested dimension & metrics
    wants_category = any(k in q_lower for k in ["category", "categories", "product category"])
    wants_product = any(k in q_lower for k in ["product", "products", "item", "items"])
    wants_customer = any(k in q_lower for k in ["customer", "customers", "user", "users", "client"])
    wants_monthly = any(k in q_lower for k in ["monthly", "month", "trend", "trends", "by month", "over time"])
    wants_revenue = any(k in q_lower for k in ["revenue", "sales", "price", "amount", "total sales", "total revenue", "highest revenue", "top selling", "top-selling", "selling"])
    wants_orders = any(k in q_lower for k in ["order", "orders", "most orders", "highest orders", "order count", "number of orders", "delivered orders"])
    wants_summary = any(k in q_lower for k in ["summary", "summarize", "overview", "describe", "details"])
    wants_name_length = any(k in q_lower for k in ["name length", "name_length", "name_lenght", "product name length", "longest average product name", "average product name length"])
    wants_delivered = "delivered" in q_lower

    # Determine limit N (default 10 or 1 if asking for 'longest' or 'which product category')
    limit_match = re.search(r'\b(?:top|limit|first)\s+(\d+)\b', q_lower)
    if not limit_match:
        limit_match = re.search(r'\b(\d+)\s+(?:orders|categories|products|items|customers|users|rows|records)\b', q_lower)
    
    if limit_match:
        limit_n = int(limit_match.group(1))
    elif any(k in q_lower for k in ["which product category", "which category", "longest", "highest", "most", "best"]) and not wants_revenue:
        limit_n = 1
    else:
        limit_n = 10

    # Locate candidate tables
    cat_matches = find_column_in_catalog(catalog, ["product_category_name", "category_name", "category", "cat_name"])
    order_matches = find_column_in_catalog(catalog, ["order_id", "order_id_pkey"])
    rev_matches = find_column_in_catalog(catalog, ["price", "revenue", "sales", "total_amount", "amount", "value"])
    length_matches = find_column_in_catalog(catalog, ["product_name_lenght", "product_name_length", "name_lenght", "name_length"])

    # -------------------------------------------------------------
    # Scenario 0: Average Product Name Length by Category
    # -------------------------------------------------------------
    if wants_name_length or ("product name" in q_lower and "length" in q_lower):
        if not cat_matches:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "Product category name length cannot be calculated from the currently connected datasets because category information is unavailable.",
                "tables_used": []
            }
        
        target_table = None
        length_col = None
        cat_col = None

        if length_matches:
            target_table, length_col = length_matches[0]
            for c_lower, c_info in target_table["columns"].items():
                if "category" in c_lower:
                    cat_col = c_info["name"]
                    break

        if not target_table or not length_col or not cat_col:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "Average product name length cannot be calculated from the currently connected datasets because product_name_lenght column is unavailable.",
                "tables_used": [t["table_name"] for t in catalog]
            }

        sql = (
            f'SELECT "{cat_col}", AVG("{length_col}") AS avg_product_name_length '
            f'FROM "{target_table["table_name"]}" '
            f'WHERE "{cat_col}" IS NOT NULL '
            f'GROUP BY "{cat_col}" '
            f'ORDER BY avg_product_name_length DESC '
            f'LIMIT {limit_n}'
        )
        explanation = f"Calculated average product name length by `{cat_col}` using `{target_table['filename']}`."
        return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [target_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario A: Summary / Single-table Category Product Count (e.g. "How many products are in each category in olist_products_dataset.csv?")
    # -------------------------------------------------------------
    if (wants_category or wants_summary) and not wants_orders and not wants_revenue and not wants_delivered:
        if cat_matches:
            cat_table, cat_col = cat_matches[0]
            target_table = cat_table
            if req_file_match:
                for t in catalog:
                    if t.get("filename", "").lower() == req_file_match.group(1).lower():
                        target_table = t
                        break

            target_cat_col = None
            for c_lower, c_info in target_table["columns"].items():
                if "category" in c_lower or "type" in c_lower:
                    target_cat_col = c_info["name"]
                    break

            if target_cat_col:
                sql = (
                    f'SELECT "{target_cat_col}" AS category, COUNT(*) AS product_count '
                    f'FROM "{target_table["table_name"]}" '
                    f'WHERE "{target_cat_col}" IS NOT NULL '
                    f'GROUP BY 1 ORDER BY product_count DESC LIMIT {limit_n}'
                )
                explanation = f"Queried `{target_table['filename']}` grouping by `{target_cat_col}` and calculated product counts."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [target_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario B: Delivered Orders by Category (3-table JOIN: products + order_items + orders)
    # -------------------------------------------------------------
    if wants_category and wants_delivered:
        if not cat_matches:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "Orders by category cannot be calculated from the currently connected datasets because category information is unavailable.",
                "tables_used": []
            }
        cat_table, cat_col = cat_matches[0]
        item_table = None
        orders_table = None

        for t in catalog:
            tb = t["table_name"].lower()
            if "item" in tb or "order_items" in tb:
                item_table = t
            elif "orders" in tb and "item" not in tb:
                orders_table = t

        if cat_table and item_table and orders_table:
            j1 = find_join_key(cat_table, item_table)
            j2 = find_join_key(item_table, orders_table)
            if j1 and j2:
                order_col = orders_table["columns"]["order_id"]["name"] if "order_id" in orders_table["columns"] else "order_id"
                status_col = "order_status" if "order_status" in orders_table["columns"] else None
                where_clause = f'WHERE o."{status_col}" = \'delivered\' AND p."{cat_col}" IS NOT NULL' if status_col else f'WHERE p."{cat_col}" IS NOT NULL'

                sql = (
                    f'SELECT p."{cat_col}" AS category, COUNT(DISTINCT o."{order_col}") AS delivered_orders '
                    f'FROM "{cat_table["table_name"]}" p '
                    f'JOIN "{item_table["table_name"]}" oi ON p."{j1[0]}" = oi."{j1[1]}" '
                    f'JOIN "{orders_table["table_name"]}" o ON oi."{j2[0]}" = o."{j2[1]}" '
                    f'{where_clause} '
                    f'GROUP BY p."{cat_col}" ORDER BY delivered_orders DESC LIMIT {limit_n}'
                )
                explanation = f"Joined `{cat_table['filename']}`, `{item_table['filename']}`, and `{orders_table['filename']}` to count delivered orders by category."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"], item_table["table_name"], orders_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario C: Orders / Revenue / Top Selling by Category
    # -------------------------------------------------------------
    if wants_category or ("category" in q_lower and (wants_orders or wants_revenue)):
        if not cat_matches:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "Category analysis cannot be calculated from the currently connected datasets because category column is unavailable.",
                "tables_used": []
            }
        cat_table, cat_col = cat_matches[0]

        # Case C1: Orders by Category
        if wants_orders:
            if not order_matches:
                return {
                    "success": False,
                    "sql": None,
                    "explanation": None,
                    "missing_dataset_msg": "Order counts cannot be calculated from the currently connected datasets because order_id column is unavailable.",
                    "tables_used": [cat_table["table_name"]]
                }
            
            order_table, order_id_col = order_matches[0]
            if cat_table["table_name"] == order_table["table_name"]:
                sql = (
                    f'SELECT "{cat_col}" AS category, COUNT(DISTINCT "{order_id_col}") AS order_count '
                    f'FROM "{cat_table["table_name"]}" WHERE "{cat_col}" IS NOT NULL '
                    f'GROUP BY 1 ORDER BY order_count DESC LIMIT {limit_n}'
                )
                return {"success": True, "sql": sql, "explanation": f"Queried `{cat_table['filename']}` by `{cat_col}` counting distinct orders.", "missing_dataset_msg": None, "tables_used": [cat_table["table_name"]]}

            join_pair = find_join_key(cat_table, order_table)
            if join_pair:
                sql = (
                    f'SELECT p."{cat_col}" AS category, COUNT(DISTINCT oi."{order_id_col}") AS order_count '
                    f'FROM "{cat_table["table_name"]}" p '
                    f'JOIN "{order_table["table_name"]}" oi ON p."{join_pair[0]}" = oi."{join_pair[1]}" '
                    f'WHERE p."{cat_col}" IS NOT NULL '
                    f'GROUP BY p."{cat_col}" ORDER BY order_count DESC LIMIT {limit_n}'
                )
                explanation = f"Joined `{cat_table['filename']}` and `{order_table['filename']}` on `{join_pair[0]}` to count orders by category."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"], order_table["table_name"]]}

        # Case C2: Revenue by Category
        if wants_revenue or "selling" in q_lower:
            if not rev_matches:
                return {
                    "success": False,
                    "sql": None,
                    "explanation": None,
                    "missing_dataset_msg": "Revenue cannot be calculated from the currently connected datasets because price/sales column is unavailable.",
                    "tables_used": [cat_table["table_name"]]
                }
            rev_table, rev_col = rev_matches[0]

            if cat_table["table_name"] == rev_table["table_name"]:
                sql = (
                    f'SELECT "{cat_col}" AS category, SUM("{rev_col}") AS total_revenue, COUNT(*) AS items_sold '
                    f'FROM "{cat_table["table_name"]}" WHERE "{cat_col}" IS NOT NULL '
                    f'GROUP BY 1 ORDER BY total_revenue DESC LIMIT {limit_n}'
                )
                explanation = f"Queried `{cat_table['filename']}` grouping by `{cat_col}` and aggregated total revenue."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"]]}

            join_pair = find_join_key(cat_table, rev_table)
            if join_pair:
                sql = (
                    f'SELECT p."{cat_col}" AS category, SUM(oi."{rev_col}") AS total_revenue, COUNT(*) AS items_sold '
                    f'FROM "{cat_table["table_name"]}" p '
                    f'JOIN "{rev_table["table_name"]}" oi ON p."{join_pair[0]}" = oi."{join_pair[1]}" '
                    f'WHERE p."{cat_col}" IS NOT NULL '
                    f'GROUP BY p."{cat_col}" ORDER BY total_revenue DESC LIMIT {limit_n}'
                )
                explanation = f"Joined `{cat_table['filename']}` and `{rev_table['filename']}` on `{join_pair[0]}` to calculate sales and revenue by category."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"], rev_table["table_name"]]}


    # -------------------------------------------------------------
    # Scenario D: Product Revenue / Highest Revenue Products
    # -------------------------------------------------------------
    if (wants_revenue or (wants_product and "revenue" in q_lower)) and not wants_monthly:
        if rev_matches:
            rev_table, rev_col = rev_matches[0]
            prod_col = rev_table["columns"]["product_id"]["name"] if "product_id" in rev_table["columns"] else list(rev_table["columns"].keys())[0]

            if cat_matches and cat_matches[0][0]["table_name"] != rev_table["table_name"]:
                cat_table, cat_col = cat_matches[0]
                join_pair = find_join_key(cat_table, rev_table)
                if join_pair:
                    sql = (
                        f'SELECT p."{cat_col}" AS category, oi."{prod_col}" AS product_id, '
                        f'SUM(oi."{rev_col}") AS total_revenue, COUNT(DISTINCT oi.order_id) AS order_count '
                        f'FROM "{rev_table["table_name"]}" oi '
                        f'JOIN "{cat_table["table_name"]}" p ON oi."{join_pair[1]}" = p."{join_pair[0]}" '
                        f'GROUP BY 1, 2 ORDER BY total_revenue DESC LIMIT {limit_n}'
                    )
                    explanation = f"Joined `{rev_table['filename']}` and `{cat_table['filename']}` on `{join_pair[0]}`, calculated total revenue by product."
                    return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [rev_table["table_name"], cat_table["table_name"]]}

            sql = (
                f'SELECT "{prod_col}" AS product_id, SUM("{rev_col}") AS total_revenue, COUNT(*) AS items_sold '
                f'FROM "{rev_table["table_name"]}" '
                f'GROUP BY 1 ORDER BY total_revenue DESC LIMIT {limit_n}'
            )
            explanation = f"Queried `{rev_table['filename']}` grouping by `{prod_col}` and calculated total revenue from `{rev_col}`."
            return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [rev_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario E: Monthly Sales Trends
    # -------------------------------------------------------------
    if wants_monthly:
        date_matches = find_column_in_catalog(catalog, ["purchase_timestamp", "order_date", "created_at", "date", "timestamp", "month"])
        if not date_matches:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "Monthly trends cannot be calculated from the currently connected datasets because date/timestamp column is unavailable.",
                "tables_used": []
            }
        date_table, date_col = date_matches[0]
        if rev_matches:
            rev_table, rev_col = rev_matches[0]
            join_pair = find_join_key(date_table, rev_table)
            if join_pair and date_table["table_name"] != rev_table["table_name"]:
                sql = (
                    f'SELECT strftime(o."{date_col}", \'%Y-%m\') AS month, SUM(oi."{rev_col}") AS total_revenue, COUNT(DISTINCT o.order_id) AS order_count '
                    f'FROM "{date_table["table_name"]}" o '
                    f'JOIN "{rev_table["table_name"]}" oi ON o."{join_pair[0]}" = oi."{join_pair[1]}" '
                    f'WHERE o."{date_col}" IS NOT NULL '
                    f'GROUP BY 1 ORDER BY month ASC'
                )
                explanation = f"Joined `{date_table['filename']}` and `{rev_table['filename']}` to calculate monthly revenue trends."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [date_table["table_name"], rev_table["table_name"]]}

            sql = (
                f'SELECT strftime("{date_col}", \'%Y-%m\') AS month, COUNT(*) AS order_count '
                f'FROM "{date_table["table_name"]}" WHERE "{date_col}" IS NOT NULL '
                f'GROUP BY 1 ORDER BY month ASC'
            )
            return {"success": True, "sql": sql, "explanation": f"Calculated monthly order trends from `{date_table['filename']}`.", "missing_dataset_msg": None, "tables_used": [date_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario F: Dataset Summary / Record Count fallback
    # -------------------------------------------------------------
    target_table = catalog[0]
    if req_file_match:
        for t in catalog:
            if t.get("filename", "").lower() == req_file_match.group(1).lower():
                target_table = t
                break

    str_cols = [c["name"] for c in target_table["columns"].values() if "cat" in c["name"].lower() or "type" in c["name"].lower() or "name" in c["name"].lower() or "status" in c["name"].lower()]
    num_cols = [c["name"] for c in target_table["columns"].values() if "price" in c["name"].lower() or "amount" in c["name"].lower() or "sales" in c["name"].lower() or "val" in c["name"].lower()]

    if str_cols and num_cols:
        sql = f'SELECT "{str_cols[0]}", SUM("{num_cols[0]}") AS total_val, COUNT(*) AS count FROM "{target_table["table_name"]}" GROUP BY 1 ORDER BY total_val DESC LIMIT {limit_n}'
        return {"success": True, "sql": sql, "explanation": f"Summarized `{target_table['filename']}` grouping by `{str_cols[0]}`.", "missing_dataset_msg": None, "tables_used": [target_table["table_name"]]}
    elif str_cols:
        sql = f'SELECT "{str_cols[0]}", COUNT(*) AS total_count FROM "{target_table["table_name"]}" WHERE "{str_cols[0]}" IS NOT NULL GROUP BY 1 ORDER BY total_count DESC LIMIT {limit_n}'
        return {"success": True, "sql": sql, "explanation": f"Summarized `{target_table['filename']}` by `{str_cols[0]}`.", "missing_dataset_msg": None, "tables_used": [target_table["table_name"]]}

    sql = f'SELECT COUNT(*) AS total_count FROM "{target_table["table_name"]}"'
    return {"success": True, "sql": sql, "explanation": f"Counted total records in `{target_table['filename']}`.", "missing_dataset_msg": None, "tables_used": [target_table["table_name"]]}


def validate_semantic_concepts(user_query: str, sql_query: str, target_dataset: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validates that the generated SQL query contains the required semantic concepts requested in user_query.
    Rejects unrelated queries (e.g. order_status + COUNT when sales by category is requested).
    """
    if not sql_query or not sql_query.strip():
        return False, "Generated SQL is empty."

    q_lower = user_query.lower()
    sql_upper = sql_query.upper()

    # Rule A: If explicit target dataset was named in user prompt, query MUST reference that table or join it
    fn_target = target_dataset.get("filename", "") if target_dataset else ""
    if fn_target and fn_target.lower() in q_lower:
        tbl = target_dataset.get("duckdb_table") or target_dataset.get("view_name") or fn_target
        tbl_clean = tbl.lower().split(".")[0]
        fn_clean = fn_target.lower().split(".")[0]
        if tbl_clean not in sql_query.lower() and fn_clean not in sql_query.lower():
            return False, f"Query does not reference the target dataset '{fn_target}'."

    # Rule B: Sales by category check
    wants_category = any(k in q_lower for k in ["category", "categories"])
    wants_sales = any(k in q_lower for k in ["sales", "revenue", "price", "amount", "total sales"])

    if wants_category and wants_sales:
        has_category = any(k in sql_upper for k in ["CATEGORY", "PROD_CAT", "PRODUCT_CATEGORY_NAME"])
        has_sales_agg = "SUM" in sql_upper or "PRICE" in sql_upper or "REVENUE" in sql_upper or "SALES" in sql_upper
        if not (has_category and has_sales_agg):
            return False, "Query lacks required sales and category concepts requested by user."
        if "ORDER_STATUS" in sql_upper and not has_category:
            return False, "Query substituted order_status for category sales."

    return True, None


def validate_semantic_sql(sql_query: Optional[str], user_query: str, catalog: List[Dict[str, Any]], target_dataset: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Performs pre-execution semantic & schema validation on a generated DuckDB SQL query.
    Returns (is_valid, rejection_reason).
    """
    if not sql_query or not sql_query.strip():
        return False, "Generated SQL query is empty."

    sql_upper = sql_query.strip().upper()

    # Rule 0: Read-only safety validation
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE", "COPY"]
    for kw in forbidden_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', sql_upper):
            return False, f"Forbidden SQL operation '{kw}' detected. Only read-only SELECT queries are allowed."

    # Rule 1: Never allow un-aggregated SELECT * FROM table for analytical queries
    if is_analytical_query(user_query):
        has_aggregation = any(k in sql_upper for k in ["GROUP BY", "COUNT", "SUM", "AVG", "MAX", "MIN"])
        if re.search(r'SELECT\s+\*\s+FROM', sql_upper) and not has_aggregation:
            return False, "Query uses un-aggregated 'SELECT *' without aggregation for an analytical request."
        if not has_aggregation and "ORDER BY" not in sql_upper and "LIMIT" not in sql_upper:
            return False, "Query lacks required aggregation, ordering, or limit clause for an analytical request."

    # Rule 2: Verify table names and column names exist in catalog
    if catalog:
        valid_tables = set()
        table_column_map = {}
        for t in catalog:
            t_name = t["table_name"].lower()
            valid_tables.add(t_name)
            if t.get("filename"):
                valid_tables.add(t["filename"].lower())
                valid_tables.add(os.path.splitext(t["filename"])[0].lower())
            table_column_map[t_name] = {c.lower() for c in t["columns"].keys()}

        table_matches = re.findall(r'(?:FROM|JOIN)\s+["\']?([\w_]+)["\']?', sql_query, re.IGNORECASE)
        for tbl in table_matches:
            tbl_clean = tbl.strip('"\'').lower()
            if tbl_clean not in valid_tables and not tbl_clean.startswith("read_csv") and not tbl_clean.startswith("project_"):
                avail = ", ".join(sorted(list(valid_tables)))
                return False, f"Table '{tbl}' does not exist in the current project catalog. Available tables: {avail}."

        dot_matches = re.findall(r'["\']?([\w_]+)["\']?\s*\.\s*["\']?([\w_]+)["\']?', sql_query, re.IGNORECASE)
        for tbl_ref, col_ref in dot_matches:
            t_lower = tbl_ref.lower()
            c_lower = col_ref.lower()
            if t_lower in table_column_map and c_lower not in table_column_map[t_lower]:
                avail_cols = ", ".join(sorted(list(table_column_map[t_lower])))
                return False, f"Column '{col_ref}' does not exist in table '{tbl_ref}'. Available columns: {avail_cols}."

    # Rule 3: Validate semantic concepts against user query
    is_concept_valid, concept_err = validate_semantic_concepts(user_query, sql_query, target_dataset)
    if not is_concept_valid:
        return False, concept_err

    return True, None

