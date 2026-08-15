import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app.features.datasets.router import analyze_file_schema
from app.features.agents.agents import resolve_dataset, planner_agent, sql_agent, response_synthesizer
from app.features.analytics.service import AnalyticsService
from app.core.llm import LLMService, LLMConfigurationError


@pytest.fixture
def temp_csv_file():
    """Creates a temporary CSV file with sample data."""
    data = (
        "order_id,customer_id,order_status,price,order_date\n"
        "o1,c1,delivered,10.5,2026-08-01\n"
        "o2,c2,shipped,20.0,2026-08-02\n"
        "o3,c1,delivered,15.75,2026-08-03\n"
        "o4,c3,delivered,50.0,2026-08-04\n"
        "o5,c4,canceled,99.99,2026-08-05\n"
    )
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
        f.write(data)
        f_path = f.name
    yield f_path
    if os.path.exists(f_path):
        os.remove(f_path)


def test_schema_intelligent_extraction(temp_csv_file):
    """Verifies that analyze_file_schema correctly extracts column counts, quality score, and data types."""
    rows, columns, schema = analyze_file_schema(temp_csv_file, "CSV")
    
    assert rows == 5
    assert "order_id" in columns
    assert "price" in columns
    assert "order_date" in columns
    
    # Check detail properties
    assert schema["price"]["is_numeric"] is True
    assert schema["order_date"]["is_date"] is True
    assert schema["order_status"]["is_categorical"] is True
    assert schema["price"]["min"] == "10.5"
    assert schema["price"]["max"] == "99.99"
    assert len(schema["order_id"]["sample_values"]) <= 5
    assert schema["order_status"]["unique_count"] == 3


def test_dataset_resolver_rules():
    """Tests the DatasetResolver matching priority rules and ambiguity detection."""
    available_datasets = [
        {"id": "uuid-1", "filename": "olist_orders_dataset.csv", "display_name": "Orders Dataset", "duckdb_table": "olist_orders"},
        {"id": "uuid-2", "filename": "olist_customers_dataset.csv", "display_name": "Customers List", "duckdb_table": "olist_customers"},
        {"id": "uuid-3", "filename": "sales_records.csv", "display_name": "Sales Records", "duckdb_table": "sales_records"}
    ]
    
    # 1. Explicit ID
    res = resolve_dataset("show data", selected_dataset_id="uuid-2", available_datasets=available_datasets)
    assert res is not None
    assert res["id"] == "uuid-2"
    
    # 2. Filename check
    res = resolve_dataset("Show records in olist_orders_dataset.csv please", available_datasets=available_datasets)
    assert res is not None
    assert res["id"] == "uuid-1"
    
    # 3. Table name check
    res = resolve_dataset("Select count from olist_customers", available_datasets=available_datasets)
    assert res is not None
    assert res["id"] == "uuid-2"
    
    # 4. Fuzzy match
    res = resolve_dataset("What is the sales performance", available_datasets=available_datasets)
    assert res is not None
    assert res["id"] == "uuid-3"
    
    # 5. Ambiguity check: multiple match words -> returns None (AI should not guess)
    res = resolve_dataset("Analyze customer orders", available_datasets=available_datasets)
    assert res is None


def test_sql_safety_validation():
    """Verifies that execute_duckdb_query rejects mutating SQL operations and permits SELECT."""
    service = AnalyticsService()
    
    # Safe SELECT should run or fail on view mapping rather than safety rejection
    try:
        service.execute_duckdb_query("SELECT 1")
    except Exception as e:
        assert "rejected for safety" not in str(e)
        
    # Dangerous statements must be blocked
    with pytest.raises(Exception) as exc_info:
        service.execute_duckdb_query("DROP TABLE datasets")
    assert "rejected for safety" in str(exc_info.value)
    
    with pytest.raises(Exception) as exc_info:
        service.execute_duckdb_query("DELETE FROM datasets WHERE id = '1'")
    assert "rejected for safety" in str(exc_info.value)
    
    with pytest.raises(Exception) as exc_info:
        service.execute_duckdb_query("ALTER TABLE datasets ADD COLUMN hack VARCHAR")
    assert "rejected for safety" in str(exc_info.value)


@patch("app.features.agents.agents.execute_duckdb_query", return_value={"columns": ["count"], "rows": [{"count": 99441}], "elapsed_ms": 5})
@patch("app.core.llm.LLMService.is_configured")
@patch("app.core.llm.LLMService.generate_response")
def test_end_to_end_chat_pipeline(mock_generate, mock_is_configured, mock_exec_duckdb):

    """Tests the full pipeline from planner to SQL generation and dynamic synthesis response."""
    mock_is_configured.return_value = True
    
    # Mock SQL generation and response synthesis
    def generate_side_effect(system_prompt, user_prompt):
        if "SQL Generator" in system_prompt:
            return "SELECT COUNT(*) FROM \"olist_orders\""
        if "AI Synthesizer" in system_prompt:
            return "The database contains 99,441 orders in total."
        return "Generic response"
    
    mock_generate.side_effect = generate_side_effect
    
    available_datasets = [
        {
            "id": "uuid-orders",
            "filename": "olist_orders_dataset.csv",
            "display_name": "Orders",
            "duckdb_table": "olist_orders",
            "schema_json": '{"order_id": {"type": "VARCHAR"}, "customer_id": {"type": "VARCHAR"}}'
        }
    ]
    
    state = {
        "query": "How many orders are there in olist_orders?",
        "workspace": "default",
        "dataset": None,
        "selected_dataset_ids": [],
        "available_datasets": available_datasets,
        "plan": [],
        "completed_steps": [],
        "errors": []
    }
    
    # 1. Planner Agent
    plan_out = planner_agent(state)
    assert "sql_agent" in plan_out["plan"]
    assert plan_out["dataset_id"] == "uuid-orders"
    assert plan_out["intent"] == "sql"
    
    # Update state
    state.update(plan_out)
    
    # 2. SQL Agent
    sql_out = sql_agent(state)
    assert sql_out["sql_query"] == 'SELECT COUNT(*) FROM "olist_orders"'
    assert "sql_result" in sql_out
    
    # Update state with mock successful result
    state.update(sql_out)
    state["sql_result"] = {"columns": ["count"], "rows": [{"count": 99441}], "elapsed_ms": 5}
    
    # 3. Response Synthesizer
    synth_out = response_synthesizer(state)
    assert "99,441 orders" in synth_out["final_response"]


def test_dynamic_sql_generation_and_execution(temp_csv_file):
    """Verifies that AnalyticsService can register a dataset and execute a dynamically generated SQL query in DuckDB."""
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    from app.features.analytics.service import AnalyticsService
    from app.features.agents.agents import generate_sql_query
    
    dataset_id = "test-dynamic-db-id"
    resolved_info = {
        "id": dataset_id,
        "path": temp_csv_file,
        "filename": "temp_orders.csv",
        "duckdb_table": "temp_orders",
        "view_name": "temp_orders",
        "display_name": "Temp Orders",
        "schema": {"price": {"type": "DOUBLE"}}
    }
    
    # Register temp file in the uploaded cache so DuckDB registration can find it
    UPLOADED_PATHS_CACHE[dataset_id] = {
        "path": temp_csv_file,
        "filename": "temp_orders.csv",
        "duckdb_table": "temp_orders"
    }
    
    try:
        # A. Test generation of SQL query
        query_text = "how many orders are there in temp_orders"
        sql = generate_sql_query(query_text, resolved_info)
        # Should generate standard fallback/count/preview query since LLM is not configured
        assert "temp_orders" in sql
        
        # B. Test execution in DuckDB
        service = AnalyticsService()
        response = service.execute_duckdb_query("SELECT COUNT(*) as cnt FROM temp_orders")
        
        assert response.columns == ["cnt"]
        assert len(response.rows) == 1
        assert response.rows[0]["cnt"] == 5
    finally:
        if dataset_id in UPLOADED_PATHS_CACHE:
            del UPLOADED_PATHS_CACHE[dataset_id]


@patch("app.core.llm.LLMService.is_configured")
@patch("app.core.llm.LLMService.generate_response")
def test_end_to_end_flow_csv_to_duckdb_to_agent_response(mock_generate, mock_is_configured, temp_csv_file):
    """Tests the full end-to-end integration flow: CSV file -> DuckDB registration -> Chat agents execution -> SQL execution -> Synthesized Response."""
    mock_is_configured.return_value = True
    
    # Mock LLM generation for SQL generator and Synthesizer responses
    def generate_side_effect(system_prompt, user_prompt):
        if "SQL Generator" in system_prompt:
            return "SELECT COUNT(*) as total_count FROM \"temp_orders\" WHERE order_status = 'delivered'"
        if "AI Synthesizer" in system_prompt:
            return "Based on the database, there are exactly 3 delivered orders."
        return "Generic response"
        
    mock_generate.side_effect = generate_side_effect
    
    from app.features.datasets.router import UPLOADED_PATHS_CACHE
    dataset_id = "test-orders-e2e-id"
    
    # 1. Simulate file upload by placing the temp csv in the uploaded cache
    # (The schema extraction was tested, now we link the file to the virtual DuckDB registration)
    available_datasets = [
        {
            "id": dataset_id,
            "filename": "temp_orders.csv",
            "display_name": "Temp Orders",
            "duckdb_table": "temp_orders",
            "schema_json": '{"order_id": {"type": "VARCHAR"}, "price": {"type": "DOUBLE"}, "order_status": {"type": "VARCHAR"}}'
        }
    ]
    
    UPLOADED_PATHS_CACHE[dataset_id] = {
        "path": temp_csv_file,
        "filename": "temp_orders.csv",
        "duckdb_table": "temp_orders"
    }
    
    try:
        # 2. Setup agent state simulating a user chat query
        state = {
            "query": "How many orders are delivered in temp_orders?",
            "workspace": "default",
            "dataset": None,
            "selected_dataset_ids": [],
            "available_datasets": available_datasets,
            "plan": [],
            "completed_steps": [],
            "errors": [],
            "is_approved": True  # Bypass human approval pause for testing
        }
        
        # 3. Step 1: Planner Agent resolves the dataset and plans steps
        planner_state = planner_agent(state)
        assert "sql_agent" in planner_state["plan"]
        assert planner_state["dataset_id"] == dataset_id
        
        state.update(planner_state)
        
        # 4. Step 2: SQL Agent generates the query and actually executes it in DuckDB
        sql_state = sql_agent(state)
        assert sql_state["sql_query"] == 'SELECT COUNT(*) as total_count FROM "temp_orders" WHERE order_status = \'delivered\''
        
        # Verify SQL agent executed against the real DuckDB view created from temp_csv_file
        # Temp orders data: o1 (delivered), o2 (shipped), o3 (delivered), o4 (delivered), o5 (canceled)
        # Total delivered: 3
        sql_result = sql_state["sql_result"]
        assert sql_result["columns"] == ["total_count"]
        assert len(sql_result["rows"]) == 1
        assert sql_result["rows"][0]["total_count"] == 3
        
        state.update(sql_state)
        
        # 5. Step 3: Response Synthesizer combines the dynamic SQL result and answers the user
        synth_state = response_synthesizer(state)
        assert "3 delivered orders" in synth_state["final_response"]
        
    finally:
        if dataset_id in UPLOADED_PATHS_CACHE:
            del UPLOADED_PATHS_CACHE[dataset_id]

