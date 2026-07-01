from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, AIMessage
from agents.state import AgentState

llm = ChatOpenAI(model="gpt-5.4-nano", temperature=0)

def summarizer(state: AgentState):
    content = state.get("file_content", "")
    messages = state["messages"]
    
    # Find the tool call for read_drive_file
    ai_message = next(m for m in reversed(messages) if isinstance(m, AIMessage) and m.tool_calls)
    drive_tool_call = next(tc for tc in ai_message.tool_calls if tc["name"] == "read_drive_file")
    
    if content.startswith("Error:"):
        summary_text = content
    else:
        prompt = f"Please provide a brief, comprehensive summary of the following file content:\n\n{content}"
        summary_response = llm.invoke(prompt)
        summary_text = summary_response.content
        
    tool_message = ToolMessage(
        content=f"Summary of the file:\n{summary_text}",
        tool_call_id=drive_tool_call["id"],
        name="read_drive_file"
    )
    
    return {"messages": [tool_message], "file_summary": summary_text}
