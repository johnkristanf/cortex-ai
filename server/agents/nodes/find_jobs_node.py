import os
import logging

from firecrawl import Firecrawl
from langchain_core.messages import AIMessage
from agents.state import AgentState

logger = logging.getLogger(__name__)


def _build_search_query(profile: dict, preferences: dict | None = None) -> str:
    target_role = (
        (preferences or {}).get("target_roles") or []
    )
    # Prefer preferences target_roles over resume target_role
    if target_role:
        role_str = " OR ".join(f'"{r}"' for r in target_role)
    else:
        role_str = f'"{profile.get("target_role") or "software engineer"}"'

    skills: list = profile.get("skills") or []
    top_skills = " ".join(skills[:3])

    work = (preferences or {}).get("work_arrangement") or ""
    location = (preferences or {}).get("location") or ""
    salary = (preferences or {}).get("salary") or ""

    extra = " ".join(filter(None, [work if work != "any" else "", location]))
    return f"{role_str} job opening 2025 {top_skills} {extra}".strip()


def _format_jobs(profile: dict, web_results: list) -> str:
    output = "## 💼 Job Matches\n\n"

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
    preferences: dict | None = state.get("job_preferences")
    query = _build_search_query(profile, preferences)
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
