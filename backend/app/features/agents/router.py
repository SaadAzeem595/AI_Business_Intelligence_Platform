import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user, MockUser
from app.features.agents.schemas import AgentChatPayload, ApproveQueryPayload, AgentChatResponse, ExecutionLogItem
from app.features.agents.graph import agent_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["LangGraph Multi-Agent Platform"])


def build_response_from_state(thread_id: str, graph_state: Any) -> AgentChatResponse:
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
        
    return AgentChatResponse(
        thread_id=thread_id,
        status=status_str,
        response=state_values.get("final_response"),
        reasoning_path=state_values.get("reasoning_path", []),
        execution_logs=logs,
        visualization_spec=state_values.get("visualization_spec"),
        recommendations=state_values.get("recommendations"),
        executive_summary=state_values.get("executive_summary"),
        sql_query=state_values.get("sql_query")
    )


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agents(
    payload: AgentChatPayload,
    current_user: MockUser = Depends(get_current_user)
) -> AgentChatResponse:
    """Sends a query to the multi-agent planning & execution graph, preserving session memory."""
    thread_id = payload.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Check if thread already exists and is in a paused state
        current_state = agent_graph.get_state(config)
        
        # If thread has never run, run initial input query
        if not current_state or not current_state.values:
            initial_state = {
                "query": payload.message,
                "workspace": payload.workspace or "default",
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
            agent_graph.invoke(initial_state, config)
        else:
            # If paused on an interrupt, we require /approve endpoint instead of repeating chat
            if current_state.next:
                raise ValueError("Graph execution is currently paused awaiting human SQL approval. Please approve first.")
            # Otherwise, override query to start a new loop under the same thread memory
            agent_graph.update_state(config, {"query": payload.message, "plan": [], "completed_steps": [], "next_agent": ""})
            agent_graph.invoke(None, config)
            
        # Get post-execution state
        final_state = agent_graph.get_state(config)
        return build_response_from_state(thread_id, final_state)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent chat execution failed: {str(e)}"
        )


@router.post("/approve", response_model=AgentChatResponse)
async def approve_pending_agent_action(
    payload: ApproveQueryPayload,
    current_user: MockUser = Depends(get_current_user)
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
