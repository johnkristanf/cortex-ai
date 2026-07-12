from langchain_core.messages import ToolMessage
from agents.state import AgentState
from tools import TOOLS

def execute_tools(state: AgentState, config):
    last_message = state["messages"][-1]
    outputs = []
    drafts_proposed = []
    tool_map = {tool.name: tool for tool in TOOLS}
    
    for tool_call in last_message.tool_calls:
        if tool_call["name"] in tool_map:
            tool = tool_map[tool_call["name"]]
            try:
                result = tool.invoke(tool_call["args"], config=config)
                
                # Check if the tool returned a draft dict directly
                if isinstance(result, dict) and "draft" in result:
                    drafts_proposed.append(result["draft"])
                    outputs.append(ToolMessage(content="Draft saved successfully.", tool_call_id=tool_call["id"], name=tool_call["name"]))
                else:
                    outputs.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_call["name"]))
            except Exception as e:
                outputs.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call["id"], name=tool_call["name"]))
                
    return {"messages": outputs, "drafts_proposed": drafts_proposed}
