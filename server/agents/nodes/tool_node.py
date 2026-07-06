from langchain_core.messages import ToolMessage
from agents.state import AgentState
from tools import TOOLS

def execute_tools(state: AgentState, config):
    last_message = state["messages"][-1]
    outputs = []
    tool_map = {tool.name: tool for tool in TOOLS}
    
    for tool_call in last_message.tool_calls:
        if tool_call["name"] in tool_map:
            tool = tool_map[tool_call["name"]]
            try:
                result = tool.invoke(tool_call["args"], config=config)
                outputs.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_call["name"]))
            except Exception as e:
                outputs.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call["id"], name=tool_call["name"]))
                
    return {"messages": outputs}
