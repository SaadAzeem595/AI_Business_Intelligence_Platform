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

    # 1. Detect requested dimension & metrics
    wants_category = any(k in q_lower for k in ["category", "categories", "product category"])
    wants_product = any(k in q_lower for k in ["product", "products", "item", "items"]) and not wants_category
    wants_customer = any(k in q_lower for k in ["customer", "customers", "user", "users", "client"])
    wants_monthly = any(k in q_lower for k in ["monthly", "month", "trend", "trends", "by month", "over time"])
    wants_revenue = any(k in q_lower for k in ["revenue", "sales", "price", "amount", "total sales", "total revenue", "highest revenue"])
    wants_orders = any(k in q_lower for k in ["order", "orders", "most orders", "highest orders", "order count", "number of orders"])
    wants_aov = any(k in q_lower for k in ["average order value", "aov", "avg order value", "average order"])

    # Determine limit N (default 10 for ranking queries)
    limit_match = re.search(r'\b(?:top|limit|first)\s+(\d+)\b', q_lower)
    if not limit_match:
        limit_match = re.search(r'\b(\d+)\s+(?:orders|categories|products|items|customers|users|rows|records)\b', q_lower)

    if limit_match:
        limit_n = int(limit_match.group(1))
    else:
        limit_n = 10

    # -------------------------------------------------------------
    # Scenario 0: How many / Count queries (e.g. "How many orders are in the dataset?")
    # -------------------------------------------------------------
    if any(k in q_lower for k in ["how many", "total records", "total rows", "total count", "count of", "number of records", "how many rows"]):
        target_table = catalog[0]
        for t in catalog:
            fn = t.get("filename", "").lower()
            tb = t.get("table_name", "").lower()
            fn_base = os.path.splitext(fn)[0] if fn else ""
            if (fn and fn in q_lower) or (fn_base and len(fn_base) > 3 and fn_base in q_lower) or (tb and tb in q_lower):
                target_table = t
                break
        sql = f'SELECT COUNT(*) AS total_count FROM "{target_table["table_name"]}"'
        explanation = f"Counted total records in `{target_table['filename']}`."
        return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [target_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario A: Category + Orders / Revenue (e.g. "highest orders by category", "top categories by orders")
    # -------------------------------------------------------------
    if wants_category or ("category" in q_lower and (wants_orders or wants_revenue)):
        cat_matches = find_column_in_catalog(catalog, ["product_category_name", "category_name", "category", "cat_name"])
        order_matches = find_column_in_catalog(catalog, ["order_id", "order_id_pkey"])
        rev_matches = find_column_in_catalog(catalog, ["price", "revenue", "sales", "total_amount", "amount", "value"])

        if not cat_matches:
            cat_matches = find_column_in_catalog(catalog, ["product_name", "prod_cat"])

        if not cat_matches:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "I need a dataset containing product category information (such as olist_products_dataset.csv) to analyze orders by category.",
                "tables_used": []
            }

        cat_table, cat_col = cat_matches[0]

        # Case A1: Orders requested by category
        if wants_orders or not wants_revenue:
            if not order_matches:
                return {
                    "success": False,
                    "sql": None,
                    "explanation": None,
                    "missing_dataset_msg": "I need olist_order_items_dataset.csv (or a dataset containing order_id) to calculate orders by product category.",
                    "tables_used": [cat_table["table_name"]]
                }
            
            # Check if category table itself contains order_id
            if "order_id" in cat_table["columns"]:
                sql = (
                    f'SELECT "{cat_col}" AS category, COUNT(DISTINCT "{cat_table["columns"]["order_id"]["name"]}") AS order_count '
                    f'FROM "{cat_table["table_name"]}" '
                    f'GROUP BY 1 ORDER BY order_count DESC LIMIT {limit_n}'
                )
                explanation = f"Queried `{cat_table['filename']}` grouping by `{cat_col}` and counted distinct `order_id`."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"]]}

            # Category table does not contain order_id -> JOIN with order_items or orders table!
            order_table, order_id_col = order_matches[0]
            join_pair = find_join_key(cat_table, order_table)

            if not join_pair:
                # Try finding an intermediate join table (e.g. products -> order_items -> orders)
                for candidate_table in catalog:
                    j1 = find_join_key(cat_table, candidate_table)
                    j2 = find_join_key(candidate_table, order_table)
                    if j1 and j2:
                        sql = (
                            f'SELECT p."{cat_col}" AS category, COUNT(DISTINCT o."{order_id_col}") AS order_count '
                            f'FROM "{cat_table["table_name"]}" p '
                            f'JOIN "{candidate_table["table_name"]}" i ON p."{j1[0]}" = i."{j1[1]}" '
                            f'JOIN "{order_table["table_name"]}" o ON i."{j2[0]}" = o."{j2[1]}" '
                            f'GROUP BY p."{cat_col}" ORDER BY order_count DESC LIMIT {limit_n}'
                        )
                        explanation = f"Joined `{cat_table['filename']}`, `{candidate_table['filename']}`, and `{order_table['filename']}` using `{j1[0]}` and `{j2[0]}`, and counted distinct `{order_id_col}`."
                        return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"], candidate_table["table_name"], order_table["table_name"]]}

                return {
                    "success": False,
                    "sql": None,
                    "explanation": None,
                    "missing_dataset_msg": f"I need a dataset linking `{cat_table['filename']}` and `{order_table['filename']}` (such as olist_order_items_dataset.csv) to calculate orders by product category.",
                    "tables_used": [cat_table["table_name"], order_table["table_name"]]
                }

            sql = (
                f'SELECT p."{cat_col}" AS category, COUNT(DISTINCT oi."{order_id_col}") AS order_count '
                f'FROM "{cat_table["table_name"]}" p '
                f'JOIN "{order_table["table_name"]}" oi ON p."{join_pair[0]}" = oi."{join_pair[1]}" '
                f'GROUP BY p."{cat_col}" ORDER BY order_count DESC LIMIT {limit_n}'
            )
            explanation = f"Joined `{cat_table['filename']}` and `{order_table['filename']}` using `{join_pair[0]}` and counted distinct `{order_id_col}`."
            return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"], order_table["table_name"]]}

        # Case A2: Revenue requested by Category
        if wants_revenue:
            if not rev_matches:
                return {
                    "success": False,
                    "sql": None,
                    "explanation": None,
                    "missing_dataset_msg": "I need olist_order_items_dataset.csv (or a dataset containing price/revenue) to calculate revenue by product category.",
                    "tables_used": [cat_table["table_name"]]
                }
            rev_table, rev_col = rev_matches[0]
            if cat_table["table_name"] == rev_table["table_name"]:
                sql = (
                    f'SELECT "{cat_col}" AS category, SUM("{rev_col}") AS total_revenue '
                    f'FROM "{cat_table["table_name"]}" '
                    f'GROUP BY 1 ORDER BY total_revenue DESC LIMIT {limit_n}'
                )
                explanation = f"Queried `{cat_table['filename']}` grouping by `{cat_col}` and calculated total revenue from `{rev_col}`."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"]]}

            join_pair = find_join_key(cat_table, rev_table)
            if join_pair:
                sql = (
                    f'SELECT p."{cat_col}" AS category, SUM(oi."{rev_col}") AS total_revenue '
                    f'FROM "{cat_table["table_name"]}" p '
                    f'JOIN "{rev_table["table_name"]}" oi ON p."{join_pair[0]}" = oi."{join_pair[1]}" '
                    f'GROUP BY p."{cat_col}" ORDER BY total_revenue DESC LIMIT {limit_n}'
                )
                explanation = f"Joined `{cat_table['filename']}` and `{rev_table['filename']}` using `{join_pair[0]}` and summed `{rev_col}`."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cat_table["table_name"], rev_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario B: Monthly Order Trends (e.g. "show monthly order trends", "monthly sales")
    # -------------------------------------------------------------
    if wants_monthly:
        date_matches = find_column_in_catalog(catalog, ["purchase_timestamp", "order_date", "created_at", "date", "timestamp", "month"])
        if not date_matches:
            return {
                "success": False,
                "sql": None,
                "explanation": None,
                "missing_dataset_msg": "I need a dataset containing order timestamps or dates (such as olist_orders_dataset.csv) to calculate monthly trends.",
                "tables_used": []
            }
        date_table, date_col = date_matches[0]
        rev_matches = find_column_in_catalog(catalog, ["price", "revenue", "sales", "total_amount", "amount", "value"])

        if wants_revenue and rev_matches:
            rev_table, rev_col = rev_matches[0]
            if rev_table["table_name"] == date_table["table_name"]:
                sql = (
                    f'SELECT strftime("{date_col}", \'%Y-%m\') AS month, SUM("{rev_col}") AS total_revenue, COUNT(*) AS order_count '
                    f'FROM "{date_table["table_name"]}" WHERE "{date_col}" IS NOT NULL '
                    f'GROUP BY 1 ORDER BY month ASC'
                )
                explanation = f"Grouped `{date_table['filename']}` by month using `{date_col}` and aggregated total revenue and order count."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [date_table["table_name"]]}

        order_col_name = date_table["columns"]["order_id"]["name"] if "order_id" in date_table["columns"] else list(date_table["columns"].keys())[0]
        sql = (
            f'SELECT strftime("{date_col}", \'%Y-%m\') AS month, COUNT(DISTINCT "{order_col_name}") AS total_orders '
            f'FROM "{date_table["table_name"]}" WHERE "{date_col}" IS NOT NULL '
            f'GROUP BY 1 ORDER BY month ASC'
        )
        explanation = f"Grouped `{date_table['filename']}` by month using `{date_col}` and counted distinct orders."
        return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [date_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario C: Product Revenue / Highest Revenue Products
    # -------------------------------------------------------------
    if wants_revenue or (wants_product and "revenue" in q_lower):
        rev_matches = find_column_in_catalog(catalog, ["price", "revenue", "sales", "total_amount", "amount"])

        if rev_matches:
            rev_table, rev_col = rev_matches[0]
            prod_col = rev_table["columns"]["product_id"]["name"] if "product_id" in rev_table["columns"] else list(rev_table["columns"].keys())[0]
            
            cat_tables = find_column_in_catalog(catalog, ["product_category_name", "category"])
            if cat_tables and cat_tables[0][0]["table_name"] != rev_table["table_name"]:
                cat_table, cat_col = cat_tables[0]
                join_pair = find_join_key(cat_table, rev_table)
                if join_pair:
                    sql = (
                        f'SELECT p."{cat_col}" AS category, oi."{prod_col}" AS product_id, '
                        f'SUM(oi."{rev_col}") AS total_revenue, COUNT(DISTINCT oi.order_id) AS order_count '
                        f'FROM "{rev_table["table_name"]}" oi '
                        f'JOIN "{cat_table["table_name"]}" p ON oi."{join_pair[1]}" = p."{join_pair[0]}" '
                        f'GROUP BY 1, 2 ORDER BY total_revenue DESC LIMIT {limit_n}'
                    )
                    explanation = f"Joined `{rev_table['filename']}` and `{cat_table['filename']}` using `{join_pair[0]}`, calculated total revenue by product."
                    return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [rev_table["table_name"], cat_table["table_name"]]}

            sql = (
                f'SELECT "{prod_col}" AS product_id, '
                f'SUM("{rev_col}") AS total_revenue, COUNT(*) AS items_sold '
                f'FROM "{rev_table["table_name"]}" '
                f'GROUP BY 1 ORDER BY total_revenue DESC LIMIT {limit_n}'
            )
            explanation = f"Queried `{rev_table['filename']}` grouping by `{prod_col}` and calculated total revenue from `{rev_col}`."
            return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [rev_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario D: Top Customers by Number of Orders
    # -------------------------------------------------------------
    if wants_customer or "customer" in q_lower:
        cust_matches = find_column_in_catalog(catalog, ["customer_id", "customer_unique_id", "user_id", "client_id"])
        order_matches = find_column_in_catalog(catalog, ["order_id"])

        if cust_matches:
            cust_table, cust_col = cust_matches[0]
            if "order_id" in cust_table["columns"]:
                sql = (
                    f'SELECT "{cust_col}" AS customer_id, COUNT(DISTINCT "{cust_table["columns"]["order_id"]["name"]}") AS order_count '
                    f'FROM "{cust_table["table_name"]}" '
                    f'GROUP BY 1 ORDER BY order_count DESC LIMIT {limit_n}'
                )
                explanation = f"Queried `{cust_table['filename']}` grouping by `{cust_col}` and counted distinct `order_id`."
                return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cust_table["table_name"]]}

            if order_matches:
                order_table, order_col = order_matches[0]
                join_pair = find_join_key(cust_table, order_table)
                if join_pair:
                    sql = (
                        f'SELECT c."{cust_col}" AS customer_id, COUNT(DISTINCT o."{order_col}") AS order_count '
                        f'FROM "{cust_table["table_name"]}" c '
                        f'JOIN "{order_table["table_name"]}" o ON c."{join_pair[0]}" = o."{join_pair[1]}" '
                        f'GROUP BY 1 ORDER BY order_count DESC LIMIT {limit_n}'
                    )
                    explanation = f"Joined `{cust_table['filename']}` and `{order_table['filename']}` using `{join_pair[0]}` and counted distinct `{order_col}`."
                    return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [cust_table["table_name"], order_table["table_name"]]}

    # -------------------------------------------------------------
    # Scenario E: Top N individual records / orders (e.g. "top 5 orders")
    # -------------------------------------------------------------
    if wants_orders and not (wants_category or wants_customer or wants_monthly):
        order_matches = find_column_in_catalog(catalog, ["order_id"])
        if order_matches:
            matched = pick_table_matching_query(order_matches, q_lower)
            order_table, order_col = matched
            rev_col = None
            for c_lower, c_info in order_table["columns"].items():
                if any(kw in c_lower for kw in ["price", "revenue", "amount", "total", "val"]):
                    rev_col = c_info["name"]
                    break
            
            if rev_col:
                sql = f'SELECT * FROM "{order_table["table_name"]}" ORDER BY "{rev_col}" DESC LIMIT {limit_n}'
            else:
                sql = f'SELECT * FROM "{order_table["table_name"]}" LIMIT {limit_n}'
                
            explanation = f"Queried top {limit_n} orders from `{order_table['filename']}`."
            return {"success": True, "sql": sql, "explanation": explanation, "missing_dataset_msg": None, "tables_used": [order_table["table_name"]]}

    # Fallback to single table best guess if available
    first_table = catalog[0]
    str_cols = [c["name"] for c in first_table["columns"].values() if "cat" in c["name"].lower() or "type" in c["name"].lower() or "name" in c["name"].lower() or "status" in c["name"].lower()]
    num_cols = [c["name"] for c in first_table["columns"].values() if "price" in c["name"].lower() or "amount" in c["name"].lower() or "sales" in c["name"].lower() or "val" in c["name"].lower()]

    if str_cols and num_cols:
        sql = f'SELECT "{str_cols[0]}", SUM("{num_cols[0]}") AS total_val, COUNT(*) AS count FROM "{first_table["table_name"]}" GROUP BY 1 ORDER BY total_val DESC LIMIT {limit_n}'
        return {"success": True, "sql": sql, "explanation": f"Grouped `{first_table['filename']}` by `{str_cols[0]}` and aggregated `{num_cols[0]}`.", "missing_dataset_msg": None, "tables_used": [first_table["table_name"]]}
    elif str_cols:
        sql = f'SELECT "{str_cols[0]}", COUNT(*) AS total_count FROM "{first_table["table_name"]}" GROUP BY 1 ORDER BY total_count DESC LIMIT {limit_n}'
        return {"success": True, "sql": sql, "explanation": f"Grouped `{first_table['filename']}` by `{str_cols[0]}`.", "missing_dataset_msg": None, "tables_used": [first_table["table_name"]]}

    sql = f'SELECT COUNT(*) AS total_count FROM "{first_table["table_name"]}"'
    return {"success": True, "sql": sql, "explanation": f"Counted total records in `{first_table['filename']}`.", "missing_dataset_msg": None, "tables_used": [first_table["table_name"]]}


def validate_semantic_concepts(user_query: str, sql_query: str, target_dataset: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validates that the generated SQL query contains the required semantic concepts requested in user_query.
    Rejects unrelated queries (e.g. order_status + COUNT when sales by category is requested).
    """
    if not sql_query or not sql_query.strip():
        return False, "Generated SQL is empty."

    q_lower = user_query.lower()
    sql_upper = sql_query.upper()

    # Rule A: If explicit target dataset was requested, query MUST reference that table or join it
    if target_dataset:
        tbl = target_dataset.get("duckdb_table") or target_dataset.get("view_name") or target_dataset.get("filename")
        if tbl:
            tbl_clean = tbl.lower().split(".")[0]
            fn_clean = target_dataset.get("filename", "").lower().split(".")[0]
            if tbl_clean not in sql_query.lower() and fn_clean not in sql_query.lower():
                return False, f"Query does not reference the target dataset '{target_dataset.get('filename')}'."

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
    Performs pre-execution semantic validation on a generated DuckDB SQL query.
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

    # Rule 1: Never allow un-aggregated SELECT * LIMIT 5 without ORDER BY for analytical queries
    if is_analytical_query(user_query):
        if re.search(r'SELECT\s+\*\s+FROM', sql_upper) and "ORDER BY" not in sql_upper and "GROUP BY" not in sql_upper:
            return False, "Query uses un-aggregated 'SELECT *' without ordering for an analytical request."
        if re.search(r'LIMIT\s+5\b', sql_upper) and "GROUP BY" not in sql_upper and "ORDER BY" not in sql_upper and "COUNT" not in sql_upper and "SUM" not in sql_upper:
            return False, "Query uses raw un-aggregated 'LIMIT 5' preview for an analytical question."
        if "GROUP BY" not in sql_upper and "ORDER BY" not in sql_upper and "COUNT" not in sql_upper and "SUM" not in sql_upper and "AVG" not in sql_upper:
            return False, "Query lacks required aggregation or ordering for an analytical request."

    # Rule 2: Verify table names exist in catalog
    if catalog:
        valid_tables = {t["table_name"].lower() for t in catalog}
        table_matches = re.findall(r'(?:FROM|JOIN)\s+["\']?([\w_]+)["\']?', sql_query, re.IGNORECASE)
        for tbl in table_matches:
            tbl_clean = tbl.strip('"\'').lower()
            if tbl_clean not in valid_tables and not tbl_clean.startswith("read_csv"):
                return False, f"Query references non-existent table '{tbl}'."

    # Rule 3: Validate semantic concepts against user query
    is_concept_valid, concept_err = validate_semantic_concepts(user_query, sql_query, target_dataset)
    if not is_concept_valid:
        return False, concept_err

    return True, None

