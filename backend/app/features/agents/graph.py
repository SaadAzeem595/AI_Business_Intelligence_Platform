import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.features.agents.agents import (
    AgentState,
    planner_agent,
    router_agent,
    sql_agent,
    analytics_agent,
    ml_agent,
    forecast_agent,
    rag_agent,
    visualization_agent,
    recommendation_agent,
    executive_report_agent,
    response_synthesizer
)

logger = logging.getLogger(__name__)

# Initialize Multi-Agent StateGraph
builder = StateGraph(AgentState)

# Register agent nodes
builder.add_node("planner", planner_agent)
builder.add_node("router", router_agent)
builder.add_node("sql_agent", sql_agent)
builder.add_node("analytics_agent", analytics_agent)
builder.add_node("ml_agent", ml_agent)
builder.add_node("forecast_agent", forecast_agent)
builder.add_node("rag_agent", rag_agent)
builder.add_node("visualization_agent", visualization_agent)
builder.add_node("recommendation_agent", recommendation_agent)
builder.add_node("executive_report_agent", executive_report_agent)
builder.add_node("response_synthesizer", response_synthesizer)

# Add static transition edges
builder.add_edge(START, "planner")
builder.add_edge("planner", "router")

# Define conditional routing from Router Agent
def route_next_agent(state: AgentState) -> str:
    next_step = state.get("next_agent", "END")
    if next_step == "END" or next_step == "":
        return END
    return next_step

builder.add_conditional_edges(
    "router",
    route_next_agent,
    {
        "sql_agent": "sql_agent",
        "analytics_agent": "analytics_agent",
        "ml_agent": "ml_agent",
        "forecast_agent": "forecast_agent",
        "rag_agent": "rag_agent",
        "visualization_agent": "visualization_agent",
        "recommendation_agent": "recommendation_agent",
        "executive_report_agent": "executive_report_agent",
        "response_synthesizer": "response_synthesizer",
        END: END
    }
)

# Route all worker nodes back to Router for plan checking
builder.add_edge("sql_agent", "router")
builder.add_edge("analytics_agent", "router")
builder.add_edge("ml_agent", "router")
builder.add_edge("forecast_agent", "router")
builder.add_edge("rag_agent", "router")
builder.add_edge("visualization_agent", "router")
builder.add_edge("recommendation_agent", "router")
builder.add_edge("executive_report_agent", "router")

# Synthesizer completes the graph execution
builder.add_edge("response_synthesizer", END)

# In-Memory thread checkpointer
memory_checkpointer = MemorySaver()

# Compile the multi-agent graph
agent_graph = builder.compile(
    checkpointer=memory_checkpointer
)
