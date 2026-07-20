import os
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage
from agents.researcher.state import ResearcherState

logger = logging.getLogger(__name__)

model_name = os.environ.get("OPENAI_GP_MODEL", "gpt-4o-mini")

_llm = ChatOpenAI(model=model_name, temperature=0)

_SYSTEM_PROMPT = """You are a product research assistant.
The user will describe the product or category they want to find.
Extract the core search query — product name, category, or keywords — and confirm back to the user what you're searching for.
Keep your reply short (1–2 sentences). Do NOT list products yet; that comes next.
"""


def researcher_agent_node(state: ResearcherState) -> dict:
    """
    Interprets the user's message, extracts the product query, and
    acknowledges what we're about to search for.
    """
    messages = state.get("messages", [])

    # Build prompt
    system = SystemMessage(content=_SYSTEM_PROMPT)
    conversation = [system] + list(messages)

    response = _llm.invoke(conversation)
    query_text = response.content.strip()

    # Derive a clean search query by stripping the conversational wrapper.
    # Use the last user message as the raw query for downstream nodes.
    raw_query = ""
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
            raw_query = msg.content.strip()
            break

    logger.info(f"researcher_agent_node: query={raw_query!r}")

    return {
        "messages": [AIMessage(content=query_text)],
        "query": raw_query,
    }
