from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    agent_node,
    execute_tools,
    route_model_output,
    read_email_node,
    write_reply_node,
    should_continue_writing,
)

# Initialize memory
memory = MemorySaver()

# ── Build the graph ────────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)

# Standard agent + tools nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", execute_tools)

# Explicit email pipeline nodes
workflow.add_node("read_email", read_email_node)
workflow.add_node("write_reply", write_reply_node)

# ── Edges ──────────────────────────────────────────────────────────────────────
workflow.add_edge(START, "agent")

# From agent: route to tools, email pipeline, or END
workflow.add_conditional_edges(
    "agent",
    route_model_output,
    ["tools", "read_email", END],
)

# Tools always return to agent for another reasoning step
workflow.add_edge("tools", "agent")

# Email pipeline: after reading, start the write loop
workflow.add_edge("read_email", "write_reply")

# Write reply loop: keep writing until all emails are processed
workflow.add_conditional_edges(
    "write_reply",
    should_continue_writing,
    {
        "write_reply": "write_reply",
        "end": END,
    },
)

agent_executor = workflow.compile(checkpointer=memory)
