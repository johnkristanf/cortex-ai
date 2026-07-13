from langgraph.graph import END
from langsmith import traceable
from agents.state import AgentState

_JOB_APPLICATION_TOOL = "start_job_application"

@traceable
def route_model_output(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        # Intercept the job-application sentinel — route to subgraph instead of tool executor
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == _JOB_APPLICATION_TOOL:
                return "resume_check"
        return "tools"

    return END
