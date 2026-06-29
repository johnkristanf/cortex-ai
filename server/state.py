from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The state of the agent.
    
    Attributes:
        messages: A list of messages in the conversation.
                  The `add_messages` reducer appends new messages to the existing list.
    """
    messages: Annotated[list[BaseMessage], add_messages]
