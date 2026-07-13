from langgraph.graph import END
from langsmith import traceable
from agents.state import AgentState

@traceable
def route_resume(state: AgentState):
    """After resume_check: route to find_jobs if resume was found, else ask user for resume."""
    if state.get("resume_profile"):
        return "find_jobs"
    return "resume_upload"

@traceable
def route_resume_upload(state: AgentState):
    """After resume_upload: route to find_jobs if profile was extracted, else end (waiting for user)."""
    if state.get("resume_profile"):
        return "find_jobs"
    return END

@traceable
def entry_point(state: AgentState):
    """Route from START: skip agent if we're waiting for the user to supply their resume."""
    if state.get("resume_requested") and not state.get("resume_profile"):
        return "resume_upload"
    return "agent"
