import os
import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from agents.state import AgentState
from lib.supabase import get_supabase

logger = logging.getLogger(__name__)


def extract_resume_profile(resume_text: str) -> dict:
    """Use an LLM to extract structured key fields from raw resume text."""
    model_name = os.environ.get("OPENAI_GP_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        metadata={"ls_provider": "openai", "ls_model_name": model_name},
    )

    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts", "resume_parser.md")
    with open(prompt_path, "r") as f:
        prompt_template = f.read()
    
    prompt = prompt_template.format(resume_text=resume_text)

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return json.loads(response.content)
    except Exception as e:
        logger.warning(f"Failed to parse resume profile JSON: {e}")
        return {
            "summary": "",
            "skills": [],
            "experiences": [],
            "education": [],
            "target_role": "Professional",
        }


def resume_check_node(state: AgentState, config) -> dict:
    """
    Check Supabase Storage for the user's resume.
    If found, extract key profile fields and store in state.
    If not found, signal that upload is needed.
    """
    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        logger.warning("resume_check_node: no user_id in config — skipping storage lookup")
        return {"resume_profile": None}

    try:
        sb = get_supabase()
        data: bytes = sb.storage.from_("resumes").download(f"{user_id}/resume.txt")
        resume_text = data.decode("utf-8")
        logger.info(f"resume_check_node: found resume for user {user_id} ({len(resume_text)} chars)")

        profile = extract_resume_profile(resume_text)
        return {"resume_profile": profile}

    except Exception as e:
        logger.info(f"resume_check_node: no resume found for user {user_id} — {e}")
        return {"resume_profile": None}
