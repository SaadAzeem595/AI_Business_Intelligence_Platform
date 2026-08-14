import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.agents.schemas import AgentChatPayload, ApproveQueryPayload, AgentChatResponse, ExecutionLogItem
from app.features.agents.graph import agent_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["LangGraph Multi-Agent Platform"])


def build_response_from_state(thread_id: str, graph_state: Any, execution_time_ms: Optional[float] = None) -> AgentChatResponse:
    state_values = graph_state.values if graph_state else {}
    next_nodes = graph_state.next if graph_state else []
    
    # Map execution logs to ExecutionLogItem schemas
    raw_logs = state_values.get("execution_logs", [])
    logs = [
        ExecutionLogItem(
            agent_name=log.get("agent_name"),
            status=log.get("status"),
            duration_ms=log.get("duration_ms"),
            timestamp=log.get("timestamp"),
            details=log.get("details")
        )
        for log in raw_logs
    ]
    
    status_str = "completed"
    if next_nodes:
        status_str = "paused"
        
    # Build Table
    table = None
    sql_result = state_values.get("sql_result")
    if sql_result and isinstance(sql_result, dict) and "columns" in sql_result and "rows" in sql_result:
        table = {
            "columns": [{"header": col, "accessorKey": col} for col in sql_result["columns"]],
            "data": sql_result["rows"]
        }
    
    analytics_result = state_values.get("analytics_result")
    if not table and analytics_result and isinstance(analytics_result, dict) and "columns" in analytics_result:
        cols = analytics_result["columns"]
        if isinstance(cols, dict):
            table_rows = []
            for col_name, prof in cols.items():
                table_rows.append({
                    "column": col_name,
                    "type": prof.get("type", "unknown"),
                    "missing": prof.get("missing_count", 0),
                    "completeness": f"{prof.get('completeness', 100.0):.1f}%",
                    "cardinality": prof.get("cardinality", 0)
                })
            table = {
                "columns": [
                    {"header": "Column Name", "accessorKey": "column"},
                    {"header": "Data Type", "accessorKey": "type"},
                    {"header": "Missing Count", "accessorKey": "missing"},
                    {"header": "Completeness", "accessorKey": "completeness"},
                    {"header": "Distinct Values", "accessorKey": "cardinality"}
                ],
                "data": table_rows
            }

    # Build Chart
    chart = None
    vis_spec = state_values.get("visualization_spec")
    if vis_spec and isinstance(vis_spec, dict):
        if "data" in vis_spec and "values" in vis_spec["data"]:
            data = vis_spec["data"]["values"]
            x_key = None
            y_keys = []
            if "encoding" in vis_spec:
                encoding = vis_spec["encoding"]
                if "x" in encoding and "field" in encoding["x"]:
                    x_key = encoding["x"]["field"]
                if "y" in encoding and "field" in encoding["y"]:
                    y_keys.append(encoding["y"]["field"])
            if not x_key and data and len(data) > 0:
                keys = list(data[0].keys())
                x_key = keys[0]
                y_keys = keys[1:]
            chart = {
                "type": vis_spec.get("mark", "bar"),
                "data": data,
                "xKey": x_key or "category",
                "yKeys": y_keys or ["value"]
            }
        elif "series" in vis_spec and isinstance(vis_spec["series"], list):
            data = []
            x_key = vis_spec.get("xAxis", {}).get("name", "category")
            y_keys = [s["name"] for s in vis_spec["series"]]
            x_data = vis_spec["xAxis"].get("data", [])
            for idx, x_val in enumerate(x_data):
                row = {x_key: x_val}
                for s in vis_spec["series"]:
                    if idx < len(s["data"]):
                        row[s["name"]] = s["data"][idx]
                data.append(row)
            chart = {
                "type": vis_spec.get("chart_type", "line"),
                "data": data,
                "xKey": x_key,
                "yKeys": y_keys
            }

    final_resp = state_values.get("final_response") or "I processed your request successfully."

    data_rows = None
    data_cols = None
    data_count = None
    if sql_result and isinstance(sql_result, dict) and "rows" in sql_result:
        data_rows = sql_result.get("rows")
        data_cols = sql_result.get("columns")
        data_count = len(data_rows) if data_rows is not None else 0

    dataset_id = state_values.get("dataset_id")
    dataset_name = state_values.get("dataset")
    sql_q = state_values.get("sql_query")

    logger.info(
        f"AI_CHAT_RESPONSE_COMPILED: user_id={state_values.get('user_id')} "
        f"project_id={state_values.get('active_project')} dataset_id={dataset_id} "
        f"sql_executed='{sql_q}' row_count={data_count} "
        f"response_len={len(final_resp)}"
    )

    return AgentChatResponse(
        thread_id=thread_id,
        status=status_str,
        response=final_resp,
        content=final_resp,
        reasoning_path=state_values.get("reasoning_path", []),
        execution_logs=logs,
        visualization_spec=state_values.get("visualization_spec"),
        recommendations=state_values.get("recommendations"),
        executive_summary=state_values.get("executive_summary"),
        sql_query=sql_q,
        sql=sql_q,
        chart=chart,
        table=table,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        data=data_rows,
        columns=data_cols,
        row_count=data_count,
        execution_time_ms=execution_time_ms or state_values.get("execution_time_ms")
    )


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agents(
    payload: AgentChatPayload,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> AgentChatResponse:
    """Sends a query to the multi-agent planning & execution graph, preserving session memory."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User query message cannot be empty."
        )

    active_proj = payload.active_project or payload.project_id
    thread_id = payload.thread_id or payload.conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(
        f"AI_CHAT_REQUEST_RECEIVED: user_id={current_user.id} project_id={active_proj} "
        f"dataset_id={payload.dataset_id or payload.dataset} thread_id={thread_id} "
        f"message='{payload.message}'"
    )

    try:
        import time
        from app.core.telemetry import LANGGRAPH_LATENCY
        from app.features.datasets.repository import dataset_repo
        from sqlalchemy import select
        from app.features.datasets.models import Dataset
        
        # Load all datasets asynchronously (thread-safe, loop-safe)
        if active_proj:
            from app.features.projects.router import get_project_and_verify_access
            await get_project_and_verify_access(active_proj, current_user, db)
            stmt = select(Dataset).where(Dataset.project_id == active_proj)
        else:
            stmt = select(Dataset).where(
                (Dataset.project_id == None) & 
                ((Dataset.workspace_id == current_user.workspace_id) | (Dataset.workspace_id == "default"))
            )
        result = await db.execute(stmt)
        db_items = list(result.scalars().all())
        available_datasets = [
            {
                "id": str(item.id),
                "filename": item.filename,
                "display_name": item.display_name,
                "storage_path": item.storage_path,
                "duckdb_table": item.duckdb_table,
                "type": item.type,
                "columns_json": item.columns_json,
                "schema_json": item.schema_json,
                "rows": item.rows,
                "status": item.status,
            }
            for item in db_items
        ]
        
        # Check if thread already exists
        current_state = agent_graph.get_state(config)
        
        start_time = time.perf_counter()
        # If thread has never run, run initial input query
        if not current_state or not current_state.values:
            initial_state = {
                "query": payload.message,
                "workspace": current_user.workspace_id,
                "dataset": payload.dataset_id or payload.dataset,
                "selected_dataset_ids": payload.selected_dataset_ids,
                "available_datasets": available_datasets,
                "active_project": active_proj,
                "history": payload.history or [],
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
                "is_approved": True,  # Auto-approve read-only SELECT queries
                "execution_logs": [],
                "reasoning_path": [],
                
                # Context keys
                "workspace_id": current_user.workspace_id,
                "dataset_id": payload.dataset_id or payload.dataset,
                "dataset_context": None,
                "dataset_schema": None,
                "user_message": payload.message,
                "intent": None,
                "generated_sql": None,
                "errors": [],
                "user_id": current_user.id,
                "roles": [current_user.role],
            }
            agent_graph.invoke(initial_state, config)
        else:
            # Override query to start a new loop under the same thread memory, wiping per-turn execution outputs
            agent_graph.update_state(config, {
                "query": payload.message,
                "dataset": payload.dataset_id or payload.dataset,
                "selected_dataset_ids": payload.selected_dataset_ids,
                "available_datasets": available_datasets,
                "active_project": active_proj,
                "history": payload.history or [],
                "plan": [],
                "completed_steps": [],
                "next_agent": "",
                
                # Wipe execution outputs from previous turns
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
                "generated_sql": None,
                "execution_logs": [],
                "reasoning_path": [],
                "errors": [],
                
                # Context keys
                "workspace_id": current_user.workspace_id,
                "dataset_id": payload.dataset_id or payload.dataset,
                "user_message": payload.message,
                "intent": None,
                "user_id": current_user.id,
                "roles": [current_user.role],
                "is_approved": True,
            }, as_node="__start__")
            agent_graph.invoke(None, config)
            
        duration = time.perf_counter() - start_time
        LANGGRAPH_LATENCY.labels(thread_id=thread_id).observe(duration)
        
        # Calculate execution_time_ms
        exec_ms = round(duration * 1000, 2)
        
        # Get post-execution state
        final_state = agent_graph.get_state(config)
        return build_response_from_state(thread_id, final_state, execution_time_ms=exec_ms)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent chat execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent chat execution failed: {str(e)}"
        )


@router.post("/approve", response_model=AgentChatResponse)
async def approve_pending_agent_action(
    payload: ApproveQueryPayload,
    current_user: MockUser = Depends(require_role(["Analyst", "Admin"]))
) -> AgentChatResponse:
    """Approves (or skips) SQL execution on an active paused thread, resuming graph flow."""
    thread_id = payload.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        current_state = agent_graph.get_state(config)
        if not current_state or not current_state.next:
            raise ValueError("No pending paused nodes found for this thread ID.")
            
        state_values = current_state.values
        
        if payload.approved:
            logger.info(f"User approved SQL action on thread {thread_id}. Resuming execution.")
            # Set is_approved to True, resuming sql_agent node
            agent_graph.update_state(config, {"is_approved": True})
            agent_graph.invoke(None, config)
        else:
            logger.info(f"User skipped SQL action on thread {thread_id}. Marking step completed and resuming.")
            # Bypass sql_agent by adding it to completed steps
            completed = list(state_values.get("completed_steps", []))
            completed.append("sql_agent")
            agent_graph.update_state(config, {"completed_steps": completed, "is_approved": False}, as_node="sql_agent")
            agent_graph.invoke(None, config)
            
        final_state = agent_graph.get_state(config)
        return build_response_from_state(thread_id, final_state)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval resumption failed: {str(e)}"
        )
