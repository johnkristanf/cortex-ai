"""
schedule.py

LangChain tools that let the LLM register, list, and remove dynamic
scheduled tasks on behalf of the user via natural language.
"""

import logging
from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
def _get_service():
    from services.scheduled_tasks import scheduled_task_service
    return scheduled_task_service


def _build_schedule_task_docstring():
    from services.task_registry import task_registry
    tasks = task_registry.get_all_tasks()
    keys = list(tasks.keys())
    keys_str = ", ".join(f'"{k}"' for k in keys) + ', or "custom"'
    
    descriptions = []
    for k, v in tasks.items():
        desc = v.get("tool_description", f"Use '{k}' for {v.get('title', k)} tasks.")
        descriptions.append(f"                   {desc}")
    
    descriptions_str = "\n".join(descriptions)
    
    return f"""Register a recurring scheduled task for the user based on their natural language request.

    Use this tool whenever the user says something like:
    - "Check and summarize my email every day at 8 AM"
    - "Search for the latest AI news every morning"
    - "Look up trending products on Product Hunt every Monday at 9 AM"
    - "Search for crypto news every weekday at noon"

    You must convert the user's time expression into a valid 5-field cron string
    (minute hour day-of-month month day-of-week). Examples:
    - "every day at 8 AM"  → "0 8 * * *"
    - "every Monday at 9 AM" → "0 9 * * 1"
    - "every hour"         → "0 * * * *"
    - "every weekday at noon" → "0 12 * * 1-5"

    Args:
        task_type: One of {keys_str}.
{descriptions_str}
                   Use "custom" for any other topic — also fill in custom_prompt.
        cron_expression: A valid 5-field cron string (e.g. "0 8 * * *" for 8 AM daily).
        description: A short human-readable label for this schedule (e.g. "Daily email check at 8 AM").
        custom_prompt: Required when task_type is "custom". The exact search or task
                       instruction to run (e.g. "Search for the latest crypto news and summarize the top 5 stories").
        timezone: IANA timezone string. Defaults to "Asia/Manila".
    """

@tool
def schedule_task(
    task_type: str,
    cron_expression: str,
    description: str,
    config: RunnableConfig,
    custom_prompt: str = "",
    timezone: str = "Asia/Manila",
) -> str:
    """Register a recurring scheduled task for the user based on their natural language request. (See dynamic description)"""
    service = _get_service()
    try:
        user_id = config.get("configurable", {}).get("thread_id", "default")
        print(f"user_id on schedule task: {user_id}")
        job_id = service.add_dynamic_job(
            user_id=user_id,
            task_type=task_type,
            cron_expression=cron_expression,
            description=description,
            custom_prompt=custom_prompt,
            timezone=timezone,
        )
        return (
            f"✅ Scheduled! I'll run **{description}** on the schedule `{cron_expression}` "
            f"({timezone}). Job ID: `{job_id}`"
        )
    except Exception as exc:
        logger.exception("schedule_task tool error")
        return f"❌ Failed to schedule task: {exc}"

schedule_task.description = _build_schedule_task_docstring()


@tool
def list_scheduled_tasks(config: RunnableConfig) -> str:
    """List all active scheduled tasks for the user.

    Use this when the user asks:
    - "What tasks do I have scheduled?"
    - "Show me my reminders / automations"
    - "What's running in the background?"
    """
    service = _get_service()
    try:
        user_id = config.get("configurable", {}).get("thread_id", "default")
        jobs = service.list_jobs(user_id)
        if not jobs:
            return "You have no scheduled tasks set up yet."
        lines = ["Here are your active scheduled tasks:\n"]
        for job in jobs:
            lines.append(
                f"• **{job['description']}** — `{job['cron']}` ({job['timezone']})\n"
                f"  Type: `{job['task_type']}` | Job ID: `{job['job_id']}`\n"
                f"  Next run: {job['next_run']}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("list_scheduled_tasks tool error")
        return f"❌ Could not list tasks: {exc}"


@tool
def remove_scheduled_task(job_id: str) -> str:
    """Remove (cancel) a specific scheduled task by its job ID.

    Use this when the user says:
    - "Cancel my email reminder"
    - "Stop the AI news search"
    - "Remove the task with ID xyz"

    If the user doesn't know the exact job ID, first call list_scheduled_tasks
    to show them the IDs, then call this tool with the one they want removed.

    Args:
        job_id: The job ID returned by schedule_task or list_scheduled_tasks.
    """
    service = _get_service()
    try:
        service.remove_job(job_id)
        return f"✅ Scheduled task `{job_id}` has been cancelled."
    except Exception as exc:
        logger.exception("remove_scheduled_task tool error")
        return f"❌ Could not remove task `{job_id}`: {exc}"
