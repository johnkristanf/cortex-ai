from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    agent_node,
    execute_tools,
    drive_reader,
    summarizer,
    route_model_output
)

# Initialize memory
memory = MemorySaver()

# Build the graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", execute_tools)
workflow.add_node("drive_reader", drive_reader)
workflow.add_node("summarizer", summarizer)

workflow.add_edge(START, "agent")

# Route based on tool calls
workflow.add_conditional_edges(
    "agent",
    route_model_output,
    ["drive_reader", "tools", END]
)

# Edges back to agent
workflow.add_edge("tools", "agent")
workflow.add_edge("drive_reader", "summarizer")
workflow.add_edge("summarizer", "agent")

agent_executor = workflow.compile(checkpointer=memory)
