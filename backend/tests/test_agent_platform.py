import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.features.agents.graph import agent_graph
from app.features.agents.agents import planner_agent, router_agent

# 1. Unit Tests for Planner and Router Nodes
def test_planner_and_router_nodes():
    # Test Planner Agent
    initial_state = {
        "query": "Generate sales forecast and run a sql query on marketing RAG documents, then visualize it",
        "workspace": "default",
        "plan": [],
        "completed_steps": [],
        "next_agent": "",
        "execution_logs": [],
        "reasoning_path": []
    }
    
    plan_res = planner_agent(initial_state)
    assert "forecast_agent" in plan_res["plan"]
    assert "sql_agent" in plan_res["plan"]
    assert "rag_agent" in plan_res["plan"]
    assert "visualization_agent" in plan_res["plan"]
    assert len(plan_res["execution_logs"]) == 1
    
    # Test Router Agent routing to first step
    router_res1 = router_agent(plan_res)
    assert router_res1["next_agent"] in plan_res["plan"]
    
    # Test Router Agent routing when some steps completed
    plan_res["completed_steps"] = ["rag_agent", "sql_agent"]
    router_res2 = router_agent(plan_res)
    assert router_res2["next_agent"] == "forecast_agent"

# 2. Integration Tests for Compiled LangGraph & Interrupts
def test_compiled_agent_graph_execution():
    thread_id = "test-thread-123"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Run the graph with a query requiring SQL and RAG
    input_state = {
        "query": "Retrieve financials from RAG and run SQL analytics",
        "workspace": "default",
        "plan": [],
        "completed_steps": [],
        "next_agent": "",
        "sql_query": None,
        "sql_result": None,
        "analytics_result": None,
        "ml_result": None,
        "forecast_result": None,
        "rag_result": None,
        "visualization_spec": None,
        "recommendations": None,
        "executive_summary": None,
        "final_response": None,
        "is_approved": False,
        "execution_logs": [],
        "reasoning_path": []
    }
    
    # Invoke graph - it should run planner -> router -> rag_agent -> router,
    # and then halt before entering sql_agent (since we have interrupt_before=["sql_agent"])
    agent_graph.invoke(input_state, config)
    
    # Inspect paused state
    paused_state = agent_graph.get_state(config)
    assert paused_state.next == ("sql_agent",)
    assert paused_state.values["is_approved"] is False
    assert "rag_agent" in paused_state.values["completed_steps"]
    assert "sql_agent" not in paused_state.values["completed_steps"]
    
    # Resume execution with user approval
    agent_graph.update_state(config, {"is_approved": True})
    agent_graph.invoke(None, config)
    
    # Check post-resume final state
    final_state = agent_graph.get_state(config)
    assert final_state.next == ()  # Execution completed
    assert "sql_agent" in final_state.values["completed_steps"]
    assert "response_synthesizer" in final_state.values["completed_steps"]
    assert final_state.values["final_response"] is not None
    assert final_state.values["sql_result"] is not None

# 3. End-to-End API Integration Tests (chat + approve resume)
def test_agent_api_endpoints():
    client = TestClient(app)
    
    # 1. Trigger agent query requiring SQL approval
    chat_payload = {
        "message": "Execute custom SQL on revenue logs, generate charts, and summarize reports.",
        "workspace": "sales"
    }
    
    response = client.post("/api/v1/agents/chat", json=chat_payload)
    assert response.status_code == 200
    resp_json = response.json()
    
    thread_id = resp_json["thread_id"]
    assert "sql_agent" not in resp_json["reasoning_path"]
    assert "planner_agent" in resp_json["reasoning_path"]
    
    # Confirm SQL query is prepared but result is not populated yet
    assert resp_json["sql_query"] is not None
    
    # 2. Approve execution via API
    approve_payload = {
        "thread_id": thread_id,
        "approved": True
    }
    approve_resp = client.post("/api/v1/agents/approve", json=approve_payload)
    assert approve_resp.status_code == 200
    approve_json = approve_resp.json()
    
    # Execution should now complete
    assert approve_json["status"] == "completed"
    assert approve_json["response"] is not None
    assert "response_synthesizer" in approve_json["reasoning_path"]
    
    # Confirm SQL results, visualization spec, and recommendations are returned
    assert approve_json["visualization_spec"] is not None
    assert approve_json["recommendations"] is not None
    assert approve_json["executive_summary"] is not None
    
    # Confirm observability execution logs exist and contain duration info
    logs = approve_json["execution_logs"]
    assert len(logs) > 0
    assert logs[0]["duration_ms"] >= 0.0
