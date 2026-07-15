import logging
import os
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from agents.state import AgentState

from schemas.job_preferences import JobPreferences

logger = logging.getLogger(__name__)

_ASK_FOR_PREFERENCES_MSG = (
    "Before I start searching, I'd love to tailor the results specifically for you! 🎯\n\n"
    "Please answer the following questions (feel free to answer all at once):\n\n"
    "1. 🏷️ **Target Roles** — What job titles are you pursuing?\n"
    "   _(e.g., \"Front-End Developer\", \"Digital Marketing Manager\")_\n\n"
    "2. 🏠 **Work Arrangement** — Do you prefer **remote**, **hybrid**, or **on-site**?\n\n"
    "3. 📍 **Location & Time Zone** — Where are you located or which regions/time zones are you targeting?\n"
    "   _(e.g., \"Panabo, Davao del Norte\" or \"US time zones\")_\n\n"
    "4. 💰 **Salary Expectations** — What is your minimum acceptable compensation or hourly rate?\n"
    "   _(e.g., \"₱50,000/month\" or \"$25/hr\")_\n\n"
    "_Take your time — the more detail you provide, the better I can match you with the right opportunities!_"
)


_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "job_preferences_parser.md"
_PARSE_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


def _parse_preferences(user_reply: str) -> dict:
    """Use an LLM with structured output to parse the user's reply into JobPreferences."""
    model = os.environ.get("OPENAI_GP_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model, temperature=0)
    structured_llm = llm.with_structured_output(JobPreferences)

    prompt = _PARSE_PROMPT_TEMPLATE.format(user_reply=user_reply)
    try:
        result: JobPreferences = structured_llm.invoke(prompt)
        return result.model_dump()
    except Exception as e:
        logger.warning(f"collect_job_preferences_node: structured output failed — {e}")
        # Graceful fallback so find_jobs can still attempt a search
        return {"raw": user_reply}


def _get_latest_user_text(state: AgentState) -> str | None:
    """Return the content of the most recent HumanMessage."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return None


def collect_job_preferences_node(state: AgentState) -> dict:
    """
    Two-pass node:
      Pass 1 (job_preferences_requested is False):
        Ask the user the four preference questions, set the flag, and wait.
      Pass 2 (job_preferences_requested is True):
        Parse the user's reply into a structured dict and store it in state.
    """
    job_preferences_requested = state.get("job_preferences_requested", False)

    if not job_preferences_requested:
        return {
            "messages": [AIMessage(content=_ASK_FOR_PREFERENCES_MSG)],
            "job_preferences_requested": True,
        }

    # Second visit — parse the user's answer
    user_reply = _get_latest_user_text(state)
    if not user_reply or len(user_reply.strip()) < 5:
        return {
            "messages": [AIMessage(
                content="I didn't catch your preferences. Could you please answer the four questions above so I can find the best matches for you?"
            )],
        }

    preferences = _parse_preferences(user_reply)
    logger.info(f"collect_job_preferences_node: parsed preferences — {preferences}")

    return {
        "job_preferences": preferences,
        "job_preferences_requested": False,
    }
