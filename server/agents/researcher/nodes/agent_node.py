import os
from pathlib import Path
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage
from agents.researcher.state import ResearcherState

logger = logging.getLogger(__name__)

model_name = os.environ.get("OPENAI_GP_MODEL", "gpt-4o-mini")

_llm = ChatOpenAI(model=model_name, temperature=0)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "agent_node.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


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
