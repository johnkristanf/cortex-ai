from agents.nodes.router import route_model_output
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    agent_node,
    execute_tools,
)

# Initialize memory
memory = MemorySaver()

# ── Build the graph ────────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)

# Standard agent + tools nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", execute_tools)

# ── Edges ──────────────────────────────────────────────────────────────────────
workflow.add_edge(START, "agent")

# From agent: route to tools or END
workflow.add_conditional_edges(
    "agent",
    route_model_output,
    ["tools", END],
)

# Tools always return to agent for another reasoning step
workflow.add_edge("tools", "agent")

agent_executor = workflow.compile(checkpointer=memory)
