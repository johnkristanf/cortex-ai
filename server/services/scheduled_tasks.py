"""
scheduled_tasks.py

Service that executes scheduled tasks using APScheduler and pushes
results to a user-specific SSE stream.
"""

import asyncio
import logging
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import langsmith as ls

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module load time
def _get_agent_executor():
    from agents import agent_executor
    return agent_executor





@dataclass
class ScheduledTaskSubscriptionEntry:
    user_id: str
    thread_id: str
    google_access_token: str | None = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class ScheduledTaskService:
    """
    Manages cron jobs and subscriptions for scheduled agent tasks.
    """

    def __init__(self):
        self._subscriptions: Dict[str, ScheduledTaskSubscriptionEntry] = {}
        self._scheduler = AsyncIOScheduler()

    def register(self, user_id: str, thread_id: str, google_access_token: str | None = None) -> asyncio.Queue:
        """
        Subscribe a user to scheduled task notifications.
        Returns the asyncio.Queue that will receive the summaries.
        """
        if user_id not in self._subscriptions:
            self._subscriptions[user_id] = ScheduledTaskSubscriptionEntry(
                user_id=user_id,
                thread_id=thread_id,
                google_access_token=google_access_token,
            )
        else:
            self._subscriptions[user_id].thread_id = thread_id
            if google_access_token:
                self._subscriptions[user_id].google_access_token = google_access_token
            
        logger.info("Registered scheduled task subscription for user=%s", user_id)
        return self._subscriptions[user_id].queue

    def get_queue(self, user_id: str) -> asyncio.Queue | None:
        """Return the notification queue for a user, or None if not subscribed."""
        entry = self._subscriptions.get(user_id)
        return entry.queue if entry else None

    def start(self) -> None:
        """Start the APScheduler."""
        logger.info("Starting ScheduledTaskService scheduler...")
        print("Starting ScheduledTaskService scheduler...")
        
        # AI News Web Search - every minute (for testing; set to cron 8:30 AM PH for production)
        self._scheduler.add_job(
            self._run_scheduled_tasks,
            'cron',
            minute='*',
            id='scheduled_ai_news_tasks',
            replace_existing=True,
            args=["ai_news"]
        )

        # Product Hunt Trending - every minute (for testing; set to cron schedule for production)
        self._scheduler.add_job(
            self._run_scheduled_tasks,
            'cron',
            minute='*',
            id='scheduled_product_hunt_tasks',
            replace_existing=True,
            args=["product_hunt"]
        )
        
        # Email Check & Draft Replies - 9:00 AM PH time
        self._scheduler.add_job(
            self._run_scheduled_tasks,
            'cron',
            hour=9,
            minute=0,
            timezone='Asia/Manila',
            id='scheduled_email_tasks',
            replace_existing=True,
            args=["email"]
        )
        
        self._scheduler.start()
        print("ScheduledTaskService scheduler started successfully!")

    def stop(self) -> None:
        """Stop the APScheduler."""
        logger.info("Stopping ScheduledTaskService scheduler...")
        print("Stopping ScheduledTaskService scheduler...")
        self._scheduler.shutdown()

    @ls.traceable(name="run_scheduled_tasks")
    async def _run_scheduled_tasks(self, task_type: str = "email") -> None:
        """
        Scheduled job that triggers the tasks for all subscribed users.
        """
        if not self._subscriptions:
            print(f"No active subscriptions for scheduled tasks ({task_type}). Skipping.")
            return
            
        logger.info("Running scheduled %s tasks for %d users...", task_type, len(self._subscriptions))
        
        # Run agent invocations concurrently
        tasks = []
        for entry in self._subscriptions.values():
            tasks.append(self._invoke_agent_task(entry, task_type))
            
        await asyncio.gather(*tasks, return_exceptions=True)

    def _get_task_details(self, task_type: str) -> tuple[str, str]:
        """Return the prompt and task title for a given task type."""
        if task_type == "ai_news":
            prompt_subpath = os.path.join("search", "ai_news.md")
            task_title = "Daily AI News Summary"
            fallback_prompt = "Search the web for the latest AI news, tech developments, and new tools. Provide a detailed summary with headlines and source links."
        elif task_type == "product_hunt":
            prompt_subpath = os.path.join("search", "product_hunt.md")
            task_title = "Product Hunt Trending"
            fallback_prompt = "Search the web for the top 3 trending products on Product Hunt for today (daily), this week (weekly), and this month (monthly). Include product names, descriptions, and links."
        else:
            prompt_subpath = "email_check.md"
            task_title = "Email Check & Draft Replies"
            fallback_prompt = "Check my email and draft replies for each unread message."

        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            prompt_subpath
        )
        try:
            with open(prompt_path, "r") as f:
                prompt = f.read()
        except FileNotFoundError:
            prompt = fallback_prompt

        # Inject the current US Eastern date so the model has an unambiguous
        # anchor for "today" regardless of where the server is running.
        us_eastern_date = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
        prompt = prompt.replace("{date_us_eastern}", us_eastern_date)

        return prompt, task_title

    @ls.traceable(name="invoke_scheduled_agent_task")
    async def _invoke_agent_task(self, entry: ScheduledTaskSubscriptionEntry, task_type: str) -> None:
        """Invoke the agent to perform the scheduled task."""
        print(f"Invoking agent task ({task_type}) for user={entry.user_id} on thread={entry.thread_id}...")
        agent_executor = _get_agent_executor()
        
        prompt, task_title = self._get_task_details(task_type)
        
        config = {
            "configurable": {
                "thread_id": entry.thread_id,
                "google_access_token": entry.google_access_token,
            },
            # Bubble user metadata into every child LLM trace in LangSmith
            "tags": ["scheduled_task", "cortex-ai"],
            "metadata": {
                "user_id": entry.user_id,
                "source": "scheduled_task",
                "ls_provider": "openai",
                "ls_model_name": "gpt-5.4-nano",
            },
        }

        try:
            print(f"Calling agent_executor.ainvoke for user={entry.user_id}...")
            with ls.tracing_context(
                project_name="cortex-ai",
                tags=["scheduled_task", "cortex-ai"],
                metadata={
                    "user_id": entry.user_id, 
                    "source": "scheduled_task",
                    "ls_provider": "openai",
                    "ls_model_name": "gpt-5.4-nano",
                },
            ):
                result = await agent_executor.ainvoke(
                    {"messages": [("user", prompt)]},
                    config
                )
            print(f"agent_executor.ainvoke returned for user={entry.user_id}!")

            last_msg = result["messages"][-1]
            summary = last_msg.content

            # ── Read draft proposals directly from state ───────────────────
            drafts: list[dict] = result.get("drafts_proposed", [])
            # ──────────────────────────────────────────────────────────────

            # ── LLM cost logging ───────────────────────────────────────────
            usage = getattr(last_msg, "usage_metadata", None)
            if usage:
                logger.info(
                    "[LLM usage] user=%s task=scheduled_task "
                    "input_tokens=%d output_tokens=%d total_tokens=%d",
                    entry.user_id,
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0),
                    usage.get("total_tokens", 0),
                )
            # ──────────────────────────────────────────────────────────────

            await entry.queue.put({
                "type": "scheduled_task",
                "task": task_title,
                "summary": summary,
                "drafts": drafts,
            })
            logger.info("Scheduled task (%s) queued for user=%s", task_type, entry.user_id)
            print(f"Scheduled task ({task_type}) successfully queued for user={entry.user_id}")

        except Exception as exc:
            logger.error("Scheduled task (%s) failed for user=%s: %s", task_type, entry.user_id, exc)
            print(f"Scheduled task ({task_type}) FAILED for user={entry.user_id}: {exc}")
            await entry.queue.put({
                "type": "error",
                "task": task_title,
                "message": str(exc),
            })

# Module-level singleton
scheduled_task_service = ScheduledTaskService()
