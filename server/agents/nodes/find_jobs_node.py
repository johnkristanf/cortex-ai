import os
import logging

from firecrawl import Firecrawl
from langchain_core.messages import AIMessage
from agents.state import AgentState

logger = logging.getLogger(__name__)


def _build_search_query(profile: dict) -> str:
    target_role = profile.get("target_role") or "software engineer"
    skills: list = profile.get("skills") or []
    top_skills = " ".join(skills[:4])
    return f'"{target_role}" full-time job opening 2024 2025 {top_skills}'


def _format_jobs(profile: dict, web_results: list) -> str:
    target_role = profile.get("target_role", "your target role")
    skills: list = profile.get("skills") or []
    summary: str = profile.get("summary") or ""

    output = f"## 🎯 Your Profile\n"
    if summary:
        output += f"{summary}\n\n"
    output += f"**Target Role:** {target_role}\n"
    if skills:
        output += f"**Key Skills:** {', '.join(skills[:8])}\n"
    output += "\n---\n\n## 💼 Job Matches\n\n"

    for i, result in enumerate(web_results, 1):
        title = result.title or "Job Opening"
        url = result.url or ""
        description = getattr(result, "description", "") or ""
        snippet = (description[:280] + "…") if len(description) > 280 else description

        output += f"### {i}. {title}\n"
        if url:
            output += f"🔗 [View & Apply]({url})\n"
        if snippet:
            output += f"{snippet}\n"
        output += "\n---\n\n"

    output += "_Would you like help tailoring your resume or writing a cover letter for any of these?_"
    return output


def find_jobs_node(state: AgentState) -> dict:
    """
    Build a search query from the extracted resume profile and
    return a formatted markdown list of job matches via Firecrawl.
    """
    profile: dict = state.get("resume_profile") or {}
    query = _build_search_query(profile)
    logger.info(f"find_jobs_node: searching with query: {query!r}")

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return {
            "messages": [AIMessage(content="⚠️ Job search is unavailable: Firecrawl API key not configured.")],
        }

    try:
        fc = Firecrawl(api_key=api_key)
        results = fc.search(query, limit=5)
        web_results = results.web or []

        if not web_results:
            return {
                "messages": [AIMessage(
                    content=f"I searched for **{profile.get('target_role', 'jobs')}** positions "
                            "but found no listings right now. Try again later or refine your target role."
                )],
            }

        formatted = _format_jobs(profile, web_results)
        return {
            "messages": [AIMessage(content=formatted)],
            "job_results": formatted,
        }

    except Exception as e:
        logger.exception("find_jobs_node: Firecrawl error")
        return {
            "messages": [AIMessage(content=f"I encountered an error searching for jobs: {e}")],
        }
