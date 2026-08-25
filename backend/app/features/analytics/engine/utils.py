import os
import pandas as pd
import duckdb
from typing import Optional
from app.core.database import get_duckdb_conn

def load_dataset(dataset_ref: str, conn: Optional[duckdb.DuckDBPyConnection] = None, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Loads a dataset into a pandas DataFrame.
    
    Args:
        dataset_ref: An absolute file path (CSV, Excel, JSON, Parquet) or a registered DuckDB table/view name.
        conn: Optional DuckDB connection.
        nrows: Optional limit on number of rows to load.
        
    Returns:
        pd.DataFrame containing the dataset.
    """
    if os.path.exists(dataset_ref):
        ext = os.path.splitext(dataset_ref)[1].lower()
        try:
            if ext == '.csv':
                return pd.read_csv(dataset_ref, nrows=nrows)
            elif ext in ['.xlsx', '.xls']:
                return pd.read_excel(dataset_ref, nrows=nrows)
            elif ext == '.json':
                return pd.read_json(dataset_ref)
            elif ext == '.parquet':
                return pd.read_parquet(dataset_ref)
            else:
                # Fallback to pandas read_csv
                return pd.read_csv(dataset_ref, nrows=nrows)
        except Exception as e:
            # Fallback to DuckDB if pandas reading fails
            pass

    # If it is not a file or pandas fails, query DuckDB
    close_conn = False
    if conn is None:
        conn = next(get_duckdb_conn())
        close_conn = True
        
    limit_clause = f" LIMIT {nrows}" if nrows else ""
    try:
        # Check if the table/view name has special characters and needs quoting
        df = conn.execute(f'SELECT * FROM "{dataset_ref}"{limit_clause}').df()
        return df
    except Exception as db_err:
        # If it's a file path and we tried view-based selection, try DuckDB CSV reader directly
        if os.path.exists(dataset_ref):
            try:
                df = conn.execute(f"SELECT * FROM read_csv_auto('{dataset_ref}'){limit_clause}").df()
                return df
            except Exception:
                raise Exception(f"Failed to load dataset from file path: {dataset_ref}. Error: {str(db_err)}")
        raise Exception(f"Failed to load dataset: {dataset_ref}. Error: {str(db_err)}")
    finally:
        if close_conn:
            conn.close()

