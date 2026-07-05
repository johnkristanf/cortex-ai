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
from typing import Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import langsmith as ls

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module load time
def _get_agent_executor():
    from agents import agent_executor
    return agent_executor


prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "ai_news_search.md")
with open(prompt_path, "r") as f:
    SCHEDULED_TASK_PROMPT = f.read().strip()


@dataclass
class ScheduledTaskSubscriptionEntry:
    user_id: str
    thread_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class ScheduledTaskService:
    """
    Manages cron jobs and subscriptions for scheduled agent tasks.
    """

    def __init__(self):
        self._subscriptions: Dict[str, ScheduledTaskSubscriptionEntry] = {}
        self._scheduler = AsyncIOScheduler()

    def register(self, user_id: str, thread_id: str) -> asyncio.Queue:
        """
        Subscribe a user to scheduled task notifications.
        Returns the asyncio.Queue that will receive the summaries.
        """
        if user_id not in self._subscriptions:
            self._subscriptions[user_id] = ScheduledTaskSubscriptionEntry(
                user_id=user_id,
                thread_id=thread_id
            )
        else:
            self._subscriptions[user_id].thread_id = thread_id
            
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
        # Add a job that runs every minute
        self._scheduler.add_job(
            self._run_scheduled_tasks,
            'cron',
            minute='*',  # every minute
            id='scheduled_agent_tasks',
            replace_existing=True
        )
        self._scheduler.start()
        print("ScheduledTaskService scheduler started successfully!")

    def stop(self) -> None:
        """Stop the APScheduler."""
        logger.info("Stopping ScheduledTaskService scheduler...")
        print("Stopping ScheduledTaskService scheduler...")
        self._scheduler.shutdown()

    @ls.traceable(name="run_scheduled_tasks")
    async def _run_scheduled_tasks(self) -> None:
        """
        Scheduled job that triggers the tasks for all subscribed users.
        """
        print("APScheduler cron triggered: _run_scheduled_tasks")
        if not self._subscriptions:
            print("No active subscriptions for scheduled tasks. Skipping.")
            return
            
        logger.info("Running scheduled tasks for %d users...", len(self._subscriptions))
        print(f"Running scheduled tasks for {len(self._subscriptions)} users...")
        
        # Run agent invocations concurrently
        tasks = []
        for entry in self._subscriptions.values():
            tasks.append(self._invoke_agent_task(entry))
            
        await asyncio.gather(*tasks, return_exceptions=True)

    @ls.traceable(name="invoke_scheduled_agent_task")
    async def _invoke_agent_task(self, entry: ScheduledTaskSubscriptionEntry) -> None:
        """Invoke the agent to perform the scheduled task."""
        print(f"Invoking agent task for user={entry.user_id} on thread={entry.thread_id}...")
        agent_executor = _get_agent_executor()
        prompt = SCHEDULED_TASK_PROMPT
        
        config = {
            "configurable": {
                "thread_id": entry.thread_id,
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
                "task": "Latest AI News",
                "summary": summary,
            })
            logger.info("Scheduled task queued for user=%s", entry.user_id)
            print(f"Scheduled task successfully queued for user={entry.user_id}")

        except Exception as exc:
            logger.error("Scheduled task failed for user=%s: %s", entry.user_id, exc)
            print(f"Scheduled task FAILED for user={entry.user_id}: {exc}")
            await entry.queue.put({
                "type": "error",
                "task": "Latest AI News",
                "message": str(exc),
            })

# Module-level singleton
scheduled_task_service = ScheduledTaskService()
