from langgraph.graph import END
from agents.state import AgentState

def route_model_output(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    if not last_message.tool_calls:
        return END
        
    destinations = []
    has_standard_tools = False
    for tool_call in last_message.tool_calls:
        has_standard_tools = True
            
    if has_standard_tools:
        destinations.append("tools")
        
    return destinations
