import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


def find_matching_join_keys(table1: Dict[str, Any], table2: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Analyzes schemas of table1 and table2 to find matching join columns.
    Returns tuple: (table1_col_name, table2_col_name) or None.
    """
    t1_cols = table1.get("columns", {})
    t2_cols = table2.get("columns", {})

    if not t1_cols or not t2_cols:
        return None

    # Priority foreign key candidates
    priority_keys = [
        "product_id", "order_id", "customer_id", "seller_id", "user_id",
        "item_id", "category_id", "product_category_name", "client_id", "account_id"
    ]

    for p_key in priority_keys:
        if p_key in t1_cols and p_key in t2_cols:
            return (t1_cols[p_key]["name"], t2_cols[p_key]["name"])

    # Any column name ending in '_id' or '_key' or matching names
    common_cols = set(t1_cols.keys()).intersection(set(t2_cols.keys()))
    if common_cols:
        # Prioritize '_id' columns first
        id_cols = [c for c in common_cols if c.endswith("_id") or c.endswith("_key")]
        if id_cols:
            best_key = sorted(id_cols)[0]
            return (t1_cols[best_key]["name"], t2_cols[best_key]["name"])

        # Exclude generic scalar columns like 'price', 'quantity', 'status' for joins unless id-like
        non_generic = [c for c in common_cols if c not in {"price", "status", "date", "created_at", "updated_at", "year", "month", "day"}]
        if non_generic:
            best_key = sorted(non_generic)[0]
            return (t1_cols[best_key]["name"], t2_cols[best_key]["name"])

    return None


class ProjectRelationshipGraph:
    """
    Project-scoped schema and relationship graph engine.
    Automatically maps foreign-key relationships across all datasets uploaded to a project.
    """

    def __init__(self, catalog: List[Dict[str, Any]]):
        self.catalog = catalog
        self.tables_by_name: Dict[str, Dict[str, Any]] = {t["table_name"].lower(): t for t in catalog}
        self.relationships: List[Dict[str, Any]] = []
        self._build_graph()

    def _build_graph(self):
        """Discovers all pairwise relationships between catalog tables."""
        n = len(self.catalog)
        for i in range(n):
            t1 = self.catalog[i]
            for j in range(i + 1, n):
                t2 = self.catalog[j]
                join_keys = find_matching_join_keys(t1, t2)
                if join_keys:
                    rel = {
                        "table1": t1["table_name"],
                        "table1_col": join_keys[0],
                        "table2": t2["table_name"],
                        "table2_col": join_keys[1],
                    }
                    self.relationships.append(rel)
                    logger.info(
                        f"RELATIONSHIP_DISCOVERED: {t1['table_name']}.{join_keys[0]} <-> {t2['table_name']}.{join_keys[1]}"
                    )

    def find_join_path(self, start_table: str, target_table: str) -> Optional[List[Dict[str, Any]]]:
        """
        Finds the shortest JOIN path between start_table and target_table.
        Returns list of relationship dicts or None if unconnected.
        """
        start = start_table.lower()
        target = target_table.lower()

        if start == target:
            return []

        # Breadth-first search for shortest join path
        queue = [(start, [])]
        visited = {start}

        while queue:
            curr_table, path = queue.pop(0)
            if curr_table == target:
                return path

            for rel in self.relationships:
                t1 = rel["table1"].lower()
                t2 = rel["table2"].lower()

                neighbor = None
                edge_info = None

                if curr_table == t1:
                    neighbor = t2
                    edge_info = {
                        "from_table": rel["table1"],
                        "from_col": rel["table1_col"],
                        "to_table": rel["table2"],
                        "to_col": rel["table2_col"],
                    }
                elif curr_table == t2:
                    neighbor = t1
                    edge_info = {
                        "from_table": rel["table2"],
                        "from_col": rel["table2_col"],
                        "to_table": rel["table1"],
                        "to_col": rel["table1_col"],
                    }

                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [edge_info]))

        return None

    def get_summary(self) -> Dict[str, Any]:
        """Returns summary of tables and discovered join edges."""
        return {
            "table_count": len(self.catalog),
            "tables": list(self.tables_by_name.keys()),
            "relationships_count": len(self.relationships),
            "relationships": self.relationships,
        }


def build_project_relationship_graph(catalog: List[Dict[str, Any]]) -> ProjectRelationshipGraph:
    """Factory helper to instantiate a ProjectRelationshipGraph."""
    return ProjectRelationshipGraph(catalog)
