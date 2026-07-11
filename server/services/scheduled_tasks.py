"""
scheduled_tasks.py

Service that executes scheduled tasks using APScheduler and pushes
results to a user-specific SSE stream.
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import langsmith as ls

from services.telegram import TelegramService, telegram_service

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


class ScheduledTaskService:
    """
    Manages cron jobs and subscriptions for scheduled agent tasks.
    """

    def __init__(self, telegram_service: TelegramService | None = None):
        self._subscriptions: Dict[str, ScheduledTaskSubscriptionEntry] = {}
        self._scheduler = AsyncIOScheduler()
        self._dynamic_job_meta: Dict[str, dict] = {}
        self._telegram_service = telegram_service

    def start(self) -> None:
        """Start the APScheduler."""
        logger.info("Starting ScheduledTaskService scheduler...")
        self._scheduler.start()
        logger.info("ScheduledTaskService scheduler started successfully!")

    def stop(self) -> None:
        """Stop the APScheduler."""
        logger.info("Stopping ScheduledTaskService scheduler...")
        print("Stopping ScheduledTaskService scheduler...")
        try:
            self._scheduler.shutdown()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Dynamic job management (called by the schedule_task LangChain tool)
    # ------------------------------------------------------------------

    def add_dynamic_job(
        self,
        user_id: str,
        task_type: str,
        cron_expression: str,
        description: str,
        custom_prompt: str = "",
        timezone: str = "Asia/Manila",
    ) -> str:
        """
        Dynamically add a scheduled job from a natural-language-derived cron expression.

        Args:
            user_id: The user who owns this job.
            task_type: "email", "ai_news", "product_hunt", or "custom".
            cron_expression: A 5-field cron string, e.g. "0 8 * * *".
            description: Human-readable label for this schedule.
            custom_prompt: Required when task_type == "custom".
            timezone: IANA timezone string, e.g. "Asia/Manila".

        Returns:
            The unique job_id string.
        """
        from apscheduler.triggers.cron import CronTrigger

        # Parse the 5-field cron string
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{cron_expression}'. "
                "Expected 5 fields: minute hour day month weekday."
            )
        minute, hour, day, month, day_of_week = parts

        job_id = f"dynamic_{user_id}_{task_type}_{uuid.uuid4().hex[:6]}"

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=timezone,
        )

        kwargs = {"user_id": user_id}
        if task_type == "custom":
            kwargs["custom_prompt"] = custom_prompt

        self._scheduler.add_job(
            self._run_scheduled_tasks,
            trigger,
            id=job_id,
            replace_existing=True,
            args=[task_type],
            kwargs=kwargs,
        )
        print(f"Added job {job_id} for user {user_id}.")

        # Store metadata for list_jobs / remove_job
        self._dynamic_job_meta[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "task_type": task_type,
            "cron": cron_expression,
            "timezone": timezone,
            "description": description,
            "custom_prompt": custom_prompt,
        }

        logger.info(
            "Dynamic job registered: id=%s user=%s type=%s cron='%s' tz=%s",
            job_id, user_id, task_type, cron_expression, timezone,
        )
        return job_id

    def list_jobs(self, user_id: str) -> List[dict]:
        """
        Return metadata for all dynamic jobs belonging to user_id.
        Enriches each entry with the next scheduled run time from APScheduler.
        """
        result = []
        for job_id, meta in self._dynamic_job_meta.items():
            if meta["user_id"] != user_id:
                continue
            job = self._scheduler.get_job(job_id)
            next_run = (
                job.next_run_time.strftime("%Y-%m-%d %H:%M %Z")
                if job and job.next_run_time
                else "not scheduled"
            )
            result.append({**meta, "next_run": next_run})
        return result

    def remove_job(self, job_id: str) -> None:
        """
        Cancel and remove a dynamic job by its job_id.
        Raises ValueError if the job_id is not found.
        """
        if job_id not in self._dynamic_job_meta:
            raise ValueError(f"No dynamic job found with id '{job_id}'.")
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass  # Already removed or never started
        del self._dynamic_job_meta[job_id]
        logger.info("Dynamic job removed: id=%s", job_id)

    @ls.traceable(name="run_scheduled_tasks")
    async def _run_scheduled_tasks(self, task_type: str = "email", custom_prompt: str = "", user_id: str = None) -> None:
        """
        Scheduled job that triggers the tasks.
        """
        # If running for a specific user (dynamic jobs)
        if user_id:
            logger.info("Running dynamic %s task for user %s...", task_type, user_id)
            entry = ScheduledTaskSubscriptionEntry(user_id=user_id, thread_id=user_id)
            await self._invoke_agent_task(entry, task_type, custom_prompt=custom_prompt)
            return

        # Otherwise fan out to all subscribed users
        if not self._subscriptions:
            print(f"No active subscriptions for scheduled tasks ({task_type}). Skipping.")
            return
            
        logger.info("Running scheduled %s tasks for %d users...", task_type, len(self._subscriptions))
        
        # Run agent invocations concurrently
        tasks = []
        for entry in self._subscriptions.values():
            tasks.append(self._invoke_agent_task(entry, task_type, custom_prompt=custom_prompt))
            
        await asyncio.gather(*tasks, return_exceptions=True)

    def _get_task_details(self, task_type: str, custom_prompt: str = "") -> tuple[str, str]:
        """Return the prompt and task title for a given task type."""
        if task_type == "ai_news":
            prompt_subpath = os.path.join("search", "ai_news.md")
            task_title = "Daily AI News Summary"
            fallback_prompt = "Search the web for the latest AI news, tech developments, and new tools. Provide a detailed summary with headlines and source links."
        elif task_type == "product_hunt":
            prompt_subpath = os.path.join("search", "product_hunt.md")
            task_title = "Product Hunt Trending"
            fallback_prompt = "Search the web for the top 3 trending products on Product Hunt for today (daily), this week (weekly), and this month (monthly). Include product names, descriptions, and links."
        elif task_type == "email":
            prompt_subpath = "email_check.md"
            task_title = "Email Check & Draft Replies"
            fallback_prompt = "Check my email and draft replies for each unread message."
        else:
            # Free-form task defined by the user via natural language
            prompt = custom_prompt or "Search the web and provide a detailed summary."
            task_title = "Custom Scheduled Task"
            us_eastern_date = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
            prompt = prompt.replace("{date_us_eastern}", us_eastern_date)
            return prompt, task_title

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
    async def _invoke_agent_task(self, entry: ScheduledTaskSubscriptionEntry, task_type: str, custom_prompt: str = "") -> None:
        """Invoke the agent to perform the scheduled task."""
        print(f"Invoking agent task ({task_type}) for user={entry.user_id} on thread={entry.thread_id}...")
        agent_executor = _get_agent_executor()
        
        prompt, task_title = self._get_task_details(task_type, custom_prompt=custom_prompt)
        
        config = {
            "configurable": {
                "thread_id": entry.thread_id,
                "google_access_token": entry.google_access_token,
            },
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

            if entry.user_id.startswith("telegram-") and self._telegram_service:
                try:
                    chat_id = entry.user_id.replace("telegram-", "")
                    
                    message = f"🔔 **{task_title}**\n\n{summary}"
                    if drafts:
                        message += "\n\nDrafts proposed:\n" + "\n".join([f"- {d.get('subject', 'No subject')}" for d in drafts])
                        
                    await self._telegram_service.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
                    logger.info("Sent scheduled task result via Telegram to %s", chat_id)
                except Exception as tg_err:
                    logger.error("Failed to send telegram notification: %s", tg_err)
                    
            logger.info("Scheduled task (%s) processed for user=%s", task_type, entry.user_id)
            print(f"Scheduled task ({task_type}) successfully processed for user={entry.user_id}")

        except Exception as exc:
            logger.error("Scheduled task (%s) failed for user=%s: %s", task_type, entry.user_id, exc)
            print(f"Scheduled task ({task_type}) FAILED for user={entry.user_id}: {exc}")
            if entry.user_id.startswith("telegram-") and self._telegram_service:
                try:
                    chat_id = entry.user_id.replace("telegram-", "")
                    await self._telegram_service.send_message(chat_id=chat_id, text=f"❌ Scheduled task '{task_title}' failed: {exc}")
                except Exception:
                    pass

# Module-level singleton
scheduled_task_service = ScheduledTaskService(telegram_service=telegram_service)
