from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    agent_node,
    execute_tools,
    resume_check_node,
    resume_upload_node,
    find_jobs_node,
    collect_job_preferences_node,
)
from agents.routers.router import route_model_output
from agents.routers.resume_router import entry_point, route_resume, route_resume_upload, route_job_preferences

# Initialize memory
memory = MemorySaver()

# ── Build the graph ────────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)

# Standard nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", execute_tools)

# Job Application subgraph nodes
workflow.add_node("resume_check", resume_check_node)
workflow.add_node("resume_upload", resume_upload_node)
workflow.add_node("collect_job_preferences", collect_job_preferences_node)
workflow.add_node("find_jobs", find_jobs_node)

# ── Edges ──────────────────────────────────────────────────────────────────────

# Entry point: bypass agent if we're already waiting for the user's resume
workflow.add_conditional_edges(START, entry_point, ["agent", "resume_upload", "collect_job_preferences"])

# From agent: intercept start_job_application → resume_check; else tools / END
workflow.add_conditional_edges(
    "agent",
    route_model_output,
    ["tools", "resume_check", END],
)

# Tools always loop back to agent
workflow.add_edge("tools", "agent")

# ── Job Application subgraph ───────────────────────────────────────────────────

# After checking storage: resume found → collect_job_preferences; not found → ask user
workflow.add_conditional_edges(
    "resume_check",
    route_resume,
    ["collect_job_preferences", "resume_upload"],
)

# After upload node: profile ready → collect_job_preferences; waiting for user → END
workflow.add_conditional_edges(
    "resume_upload",
    route_resume_upload,
    ["collect_job_preferences", END],
)

# After preferences collected → find_jobs; waiting for user → END
workflow.add_conditional_edges(
    "collect_job_preferences",
    route_job_preferences,
    ["find_jobs", END],
)

# Job results flow back to agent for a final natural-language response
workflow.add_edge("find_jobs", "agent")

agent_executor = workflow.compile(checkpointer=memory)
