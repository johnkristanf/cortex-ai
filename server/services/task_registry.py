import json
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class TaskRegistry:
    """
    Registry for loading and serving dynamic scheduled tasks configurations.
    """
    def __init__(self):
        self._tasks: Dict[str, dict] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Loads the scheduled tasks registry from the JSON configuration."""
        registry_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "scheduled_tasks.json"
        )
        try:
            with open(registry_path, "r") as f:
                self._tasks = json.load(f)
            logger.info(f"Loaded {len(self._tasks)} tasks from registry.")
        except Exception as e:
            logger.error(f"Failed to load task registry: {e}")
            self._tasks = {}

    def get_all_tasks(self) -> Dict[str, dict]:
        """Return all registered tasks."""
        return self._tasks

    def get_task_details(self, task_type: str, custom_prompt: str = "") -> Tuple[str, str]:
        """
        Returns the (prompt, task_title) for a given task type.
        If task_type is 'custom', it uses the provided custom_prompt.
        """
        if task_type == "custom":
            prompt = custom_prompt or "Search the web and provide a detailed summary."
            task_title = "Custom Scheduled Task"
        else:
            task_info = self._tasks.get(task_type)
            if not task_info:
                prompt = custom_prompt or "Execute the scheduled task."
                task_title = f"Scheduled Task ({task_type})"
                return prompt, task_title

            task_title = task_info.get("title", f"Scheduled Task ({task_type})")
            prompt_subpath = task_info.get("prompt_file")
            fallback_prompt = task_info.get("fallback_prompt", "Execute the task.")

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

        # Inject datetime values
        us_eastern_date = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")
        prompt = prompt.replace("{date_us_eastern}", us_eastern_date)

        return prompt, task_title

# Singleton instance
task_registry = TaskRegistry()
