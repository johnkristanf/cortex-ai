from langgraph.graph import END
from agents.state import AgentState

def route_model_output(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]

    # If agent produced tool calls, dispatch them
    if last_message.tool_calls:
        return "tools"

    return END
