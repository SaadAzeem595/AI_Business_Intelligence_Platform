import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import duckdb
import re
from app.features.analytics.engine.utils import load_dataset

class KpiEngineService:
    """
    Service to automatically detect and compute standard business KPIs
    (Revenue, Profit, Growth, Retention, CAC, LTV, Conversion Rate)
    and evaluate custom user-defined KPIs.
    """
    
    def compute_kpis(
        self, 
        dataset_ref: str, 
        conn: Optional[duckdb.DuckDBPyConnection] = None, 
        custom_kpis: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Computes standard and custom KPIs from the dataset.
        
        Args:
            dataset_ref: File path or view name.
            conn: Optional DuckDB connection.
            custom_kpis: Dict of custom KPI names to formulas.
            
        Returns:
            Dict containing computed standard and custom KPIs.
        """
        df = load_dataset(dataset_ref, conn)
        if len(df) == 0:
            return {
                "standard_kpis": {
                    "revenue": None, "profit": None, "growth": None, 
                    "retention": None, "cac": None, "ltv": None, "conversion_rate": None
                },
                "custom_kpis": {}
            }
            
        # Clean column names for easier mapping (strip whitespace, lowercase)
        col_map = {col: str(col).strip().lower() for col in df.columns}
        inv_col_map = {v: k for k, v in col_map.items()}
        
        # Find column mappings based on synonyms
        revenue_col = self._find_col(col_map, ['revenue', 'sales', 'amount', 'turnover', 'gross_revenue', 'sales_amount'])
        profit_col = self._find_col(col_map, ['profit', 'margin', 'earnings', 'net_income', 'net_profit'])
        cost_col = self._find_col(col_map, ['cost', 'expenses', 'spend', 'marketing_spend', 'total_cost'])
        date_col = self._find_col(col_map, ['date', 'time', 'timestamp', 'transaction_date', 'created_at'])
        user_col = self._find_col(col_map, ['user_id', 'customer_id', 'client_id', 'member_id', 'user', 'customer'])
        conversions_col = self._find_col(col_map, ['conversions', 'converts', 'signups', 'purchases', 'leads'])
        visitors_col = self._find_col(col_map, ['visitors', 'traffic', 'sessions', 'clicks', 'views'])
        
        kpis = {}
        
        # 1. Revenue
        if revenue_col:
            kpis['revenue'] = float(df[revenue_col].sum())
        else:
            kpis['revenue'] = None
            
        # 2. Profit
        if profit_col:
            kpis['profit'] = float(df[profit_col].sum())
        elif revenue_col and cost_col:
            kpis['profit'] = float((df[revenue_col] - df[cost_col]).sum())
        else:
            kpis['profit'] = None
            
        # 3. Growth
        if revenue_col and date_col:
            try:
                temp_df = df.copy()
                temp_df[date_col] = pd.to_datetime(temp_df[date_col], errors='coerce')
                temp_df = temp_df.dropna(subset=[date_col])
                
                if len(temp_df) > 0:
                    # Group by year-month
                    monthly = temp_df.groupby(temp_df[date_col].dt.to_period('M'))[revenue_col].sum().sort_index()
                    if len(monthly) > 1:
                        last_period_val = monthly.iloc[-1]
                        prev_period_val = monthly.iloc[-2]
                        if prev_period_val > 0:
                            kpis['growth'] = float((last_period_val - prev_period_val) / prev_period_val * 100)
                        else:
                            kpis['growth'] = 0.0
                    else:
                        kpis['growth'] = 0.0
                else:
                    kpis['growth'] = None
            except Exception:
                kpis['growth'] = None
        else:
            kpis['growth'] = None
            
        # 4. Retention Rate
        if user_col and date_col:
            try:
                temp_df = df.copy()
                temp_df[date_col] = pd.to_datetime(temp_df[date_col], errors='coerce')
                temp_df = temp_df.dropna(subset=[date_col, user_col])
                
                if len(temp_df) > 0:
                    temp_df['month'] = temp_df[date_col].dt.to_period('M')
                    user_months = temp_df.groupby(user_col)['month'].apply(set).to_dict()
                    
                    all_months = sorted(list(set(temp_df['month'])))
                    if len(all_months) > 1:
                        retention_rates = []
                        for i in range(len(all_months) - 1):
                            m1 = all_months[i]
                            m2 = all_months[i+1]
                            
                            active_m1 = {u for u, ms in user_months.items() if m1 in ms}
                            active_m2 = {u for u, ms in user_months.items() if m2 in ms}
                            
                            if len(active_m1) > 0:
                                retained = active_m1.intersection(active_m2)
                                retention_rates.append(len(retained) / len(active_m1) * 100)
                        kpis['retention'] = float(np.mean(retention_rates)) if retention_rates else 0.0
                    else:
                        user_counts = temp_df[user_col].value_counts()
                        retained_users = (user_counts > 1).sum()
                        total_users = len(user_counts)
                        kpis['retention'] = float(retained_users / total_users * 100) if total_users > 0 else 0.0
                else:
                    kpis['retention'] = None
            except Exception:
                kpis['retention'] = None
        else:
            kpis['retention'] = None
            
        # 5. CAC (Customer Acquisition Cost)
        if cost_col:
            total_cost = df[cost_col].sum()
            if conversions_col:
                total_conversions = df[conversions_col].sum()
                kpis['cac'] = float(total_cost / total_conversions) if total_conversions > 0 else 0.0
            elif user_col:
                unique_users = df[user_col].nunique()
                kpis['cac'] = float(total_cost / unique_users) if unique_users > 0 else 0.0
            else:
                kpis['cac'] = None
        else:
            kpis['cac'] = None
            
        # 6. LTV (Lifetime Value)
        if user_col and revenue_col:
            user_rev = df.groupby(user_col)[revenue_col].sum()
            kpis['ltv'] = float(user_rev.mean()) if len(user_rev) > 0 else 0.0
        elif revenue_col:
            kpis['ltv'] = float(df[revenue_col].mean() * 5)
        else:
            kpis['ltv'] = None
            
        # 7. Conversion Rate
        if conversions_col and visitors_col:
            total_conversions = df[conversions_col].sum()
            total_visitors = df[visitors_col].sum()
            kpis['conversion_rate'] = float(total_conversions / total_visitors * 100) if total_visitors > 0 else 0.0
        elif conversions_col:
            kpis['conversion_rate'] = float(df[conversions_col].sum() / len(df) * 100) if len(df) > 0 else 0.0
        else:
            kpis['conversion_rate'] = None
            
        # Evaluate Custom KPIs
        custom_results = {}
        if custom_kpis:
            for name, formula in custom_kpis.items():
                try:
                    custom_results[name] = self._evaluate_formula(formula, df, kpis, inv_col_map)
                except Exception as e:
                    custom_results[name] = f"Error: {str(e)}"
                    
        return {
            "standard_kpis": kpis,
            "custom_kpis": custom_results
        }
        
    def _find_col(self, col_map: Dict[str, str], synonyms: List[str]) -> Optional[str]:
        for syn in synonyms:
            if syn in col_map.values():
                for orig, mapped in col_map.items():
                    if mapped == syn:
                        return orig
        return None
        
    def _evaluate_formula(self, formula: str, df: pd.DataFrame, computed_kpis: Dict[str, Any], inv_col_map: Dict[str, str]) -> Any:
        expr = formula.strip()
        
        # Replace column-level aggregations sum(col), mean(col), avg(col)
        def replace_agg(match):
            agg_type = match.group(1).lower()
            col_name = match.group(2).strip().lower()
            
            orig_col = None
            for mapped_name, orig in inv_col_map.items():
                if mapped_name == col_name or col_name in mapped_name:
                    orig_col = orig
                    break
            
            if orig_col is None:
                raise ValueError(f"Column '{col_name}' not found for aggregation {agg_type}")
                
            if agg_type == 'sum':
                return str(df[orig_col].sum())
            elif agg_type in ['mean', 'avg']:
                return str(df[orig_col].mean())
            elif agg_type == 'min':
                return str(df[orig_col].min())
            elif agg_type == 'max':
                return str(df[orig_col].max())
            elif agg_type == 'count':
                return str(df[orig_col].count())
            return "0"
            
        expr = re.sub(r'(sum|mean|avg|min|max|count)\(([^)]+)\)', replace_agg, expr, flags=re.IGNORECASE)
        
        # Replace standard computed KPIs if found in the expression
        for kpi_name, kpi_val in computed_kpis.items():
            if kpi_val is not None:
                expr = re.sub(rf'\b{kpi_name}\b', str(kpi_val), expr, flags=re.IGNORECASE)
            else:
                expr = re.sub(rf'\b{kpi_name}\b', "0", expr, flags=re.IGNORECASE)
                
        # Safely evaluate expression using simple mathematical eval
        clean_expr = re.sub(r'[^0-9+\-*/().\s]', '', expr)
        if not clean_expr.strip():
            return None
            
        try:
            val = eval(clean_expr, {"__builtins__": None}, {})
            return float(val)
        except Exception:
            # Fallback evaluation on columns
            df_expr = formula
            for mapped_name, orig in inv_col_map.items():
                df_expr = re.sub(rf'\b{mapped_name}\b', f"`{orig}`", df_expr, flags=re.IGNORECASE)
            res_series = df.eval(df_expr)
            return float(res_series.mean())
