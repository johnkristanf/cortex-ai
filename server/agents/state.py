import operator
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The state of the agent.
    
    Attributes:
        messages: A list of messages in the conversation.
                  The `add_messages` reducer appends new messages to the existing list.
        file_content: The content of a file read from Google Drive.
        file_summary: The summary of the file content.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    file_content: str | None
    file_summary: str | None
    
    # Email processing state
    drafts_proposed: Annotated[list[dict], operator.add]
