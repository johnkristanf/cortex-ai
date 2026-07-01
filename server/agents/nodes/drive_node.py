from agents.state import AgentState
from tools.drive import fetch_drive_file_content

def drive_reader(state: AgentState, config):
    messages = state["messages"]
    last_message = messages[-1]
    
    drive_tool_call = next(tc for tc in last_message.tool_calls if tc["name"] == "read_drive_file")
    filename = drive_tool_call["args"].get("filename", "")
    google_access_token = config.get("configurable", {}).get("google_access_token")
    
    content = fetch_drive_file_content(filename, google_access_token)
    return {"file_content": content}
