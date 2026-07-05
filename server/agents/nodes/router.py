from langgraph.graph import END
from agents.state import AgentState

_EMAIL_TRIGGER_KEYWORDS = frozenset([
    "check email", "check my email", "read email", "read my email",
    "unread email", "process email", "email replies", "draft replies",
    "check inbox", "read inbox",
])

def _wants_email_pipeline(state: AgentState) -> bool:
    """
    Returns True if the latest human message is asking to read/process emails.
    This lets the agent node short-circuit to read_email_node directly
    without needing a tool call round-trip.
    """
    messages = state.get("messages", [])
    for msg in reversed(messages):
        role = getattr(msg, "type", "")
        if role == "human":
            text = (msg.content or "").lower()
            if any(kw in text for kw in _EMAIL_TRIGGER_KEYWORDS):
                return True
            break
    return False


def route_model_output(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]

    # If agent produced tool calls, dispatch them
    if last_message.tool_calls:
        return "tools"

    # If no tool calls but the user clearly wants email processing, go to pipeline
    if _wants_email_pipeline(state):
        return "read_email"

    return END


def should_continue_writing(state: AgentState) -> str:
    """
    Conditional edge: loops back to write_reply while emails remain,
    routes to END when all drafts have been generated.
    """
    emails = state.get("unread_emails", [])
    index  = state.get("current_email_index", 0)
    return "write_reply" if index < len(emails) else "end"
