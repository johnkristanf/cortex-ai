from langgraph.graph import END
from langsmith import traceable
from agents.state import AgentState

@traceable
def route_resume(state: AgentState):
    """After resume_check: route to collect_job_preferences if resume was found, else ask user for resume."""
    if state.get("resume_profile"):
        return "collect_job_preferences"
    return "resume_upload"

@traceable
def route_resume_upload(state: AgentState):
    """After resume_upload: route to collect_job_preferences if profile was extracted, else end (waiting for user)."""
    if state.get("resume_profile"):
        return "collect_job_preferences"
    return END

@traceable
def route_job_preferences(state: AgentState):
    """After collect_job_preferences: route to find_jobs once preferences are collected, else wait."""
    if state.get("job_preferences"):
        return "find_jobs"
    return END

@traceable
def entry_point(state: AgentState):
    """Route from START: skip agent if we're waiting for resume or job preferences."""
    if state.get("resume_requested") and not state.get("resume_profile"):
        return "resume_upload"
    if state.get("job_preferences_requested") and not state.get("job_preferences"):
        return "collect_job_preferences"
    return "agent"
