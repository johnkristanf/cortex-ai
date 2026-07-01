"""
drive_events.py

Event-driven service that reacts to Google Drive file uploads via Push Notifications
(webhooks) instead of polling. When a new file appears in a watched folder, Google
calls POST /drive/webhook and this service fetches only the delta via changes.list,
then invokes the agent to summarise the new file.

Prerequisites
-------------
* A public HTTPS URL reachable by Google (set WEBHOOK_BASE_URL in .env, e.g. via ngrok).
* The google_access_token passed on registration must have at least:
    - drive.readonly  (read files / list changes)
    - drive.metadata.readonly is sufficient for changes.list
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module load time
def _get_agent_executor():
    from agents import agent_executor
    return agent_executor


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------

@dataclass
class SubscriptionEntry:
    """All state for one user's Drive push subscription."""
    user_id: str
    folder_id: str
    google_access_token: str
    thread_id: str
    # Drive changes API bookmark
    page_token: str = ""
    # Push channel metadata
    channel_id: str = ""
    resource_id: str = ""
    channel_expiration_ms: int = 0  # Unix ms when channel expires
    # SSE delivery queue
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DriveEventService:
    """
    Singleton that manages Google Drive Push Notification channels.

    Lifecycle
    ---------
    await drive_event_service.start()   # on FastAPI startup
    drive_event_service.register(...)   # once per authenticated user
    drive_event_service.handle_webhook(headers)  # called from POST /drive/webhook
    await drive_event_service.stop()    # on FastAPI shutdown
    """

    # Renew the push channel this many seconds before it expires.
    RENEW_BEFORE_EXPIRY_S = 3_600          # 1 hour
    # Maximum TTL Google allows for a push channel (7 days).
    CHANNEL_TTL_S = 7 * 24 * 3_600        # 604 800 s

    def __init__(self):
        self._subscriptions: Dict[str, SubscriptionEntry] = {}   # user_id → entry
        self._channel_to_user: Dict[str, str] = {}               # channel_id → user_id
        self._renewal_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        user_id: str,
        folder_id: str,
        google_access_token: str,
        thread_id: str,
    ) -> asyncio.Queue:
        """
        Subscribe a user's Drive folder to push notifications.

        Returns the asyncio.Queue that will receive summaries (for the SSE stream).
        If already registered, refreshes the token and re-subscribes.
        """
        if user_id in self._subscriptions:
            entry = self._subscriptions[user_id]
            entry.folder_id = folder_id
            entry.google_access_token = google_access_token
            entry.thread_id = thread_id
            logger.info("Refreshing Drive subscription for user=%s", user_id)
            # Re-subscribe asynchronously (fire-and-forget).
            asyncio.create_task(self._subscribe(entry))
            return entry.queue

        entry = SubscriptionEntry(
            user_id=user_id,
            folder_id=folder_id,
            google_access_token=google_access_token,
            thread_id=thread_id,
        )
        self._subscriptions[user_id] = entry
        asyncio.create_task(self._subscribe(entry))
        return entry.queue

    def get_queue(self, user_id: str) -> asyncio.Queue | None:
        """Return the notification queue for a user, or None if not subscribed."""
        entry = self._subscriptions.get(user_id)
        return entry.queue if entry else None

    async def handle_webhook(self, headers: dict) -> None:
        """
        Called when Google POSTs to /drive/webhook.

        Google sends a thin notification; we use X-Goog-Channel-ID to identify
        the user, then call changes.list to find what actually changed.
        """
        channel_id = headers.get("x-goog-channel-id") or headers.get("X-Goog-Channel-ID", "")
        resource_state = headers.get("x-goog-resource-state") or headers.get("X-Goog-Resource-State", "")

        logger.info("Webhook received: channel=%s state=%s", channel_id, resource_state)

        # "sync" is the initial handshake notification – nothing to do.
        if resource_state == "sync":
            return

        user_id = self._channel_to_user.get(channel_id)
        if not user_id:
            logger.warning("Unknown channel_id=%s — ignoring", channel_id)
            return

        entry = self._subscriptions.get(user_id)
        if not entry:
            return

        # Run in a background task so the webhook endpoint returns instantly.
        asyncio.create_task(self._process_changes(entry))

    async def start(self) -> None:
        """Start the background channel-renewal loop."""
        logger.info("DriveEventService starting…")
        self._renewal_task = asyncio.create_task(
            self._renewal_loop(), name="drive-channel-renewal"
        )

    async def stop(self) -> None:
        """Stop the renewal loop and clean up."""
        if self._renewal_task:
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass
        logger.info("DriveEventService stopped.")

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def _subscribe(self, entry: SubscriptionEntry) -> None:
        """Register (or renew) a Drive push channel for the entry."""
        try:
            # Step 1: Get the current changes page token (our baseline).
            page_token = await asyncio.to_thread(self._get_start_page_token, entry)
            entry.page_token = page_token

            # Step 2: Register push channel with Drive API.
            channel_id = str(uuid.uuid4())
            webhook_url = os.environ["WEBHOOK_BASE_URL"].rstrip("/") + "/drive/webhook"
            expiration_ms = int(
                (__import__("time").time() + self.CHANNEL_TTL_S) * 1000
            )

            resource_id = await asyncio.to_thread(
                self._watch_drive_changes,
                entry,
                channel_id,
                webhook_url,
                expiration_ms,
            )

            # Unmap old channel if renewing.
            if entry.channel_id:
                self._channel_to_user.pop(entry.channel_id, None)

            entry.channel_id = channel_id
            entry.resource_id = resource_id
            entry.channel_expiration_ms = expiration_ms
            self._channel_to_user[channel_id] = entry.user_id

            logger.info(
                "Drive push channel registered: user=%s channel=%s expires_in=%dh",
                entry.user_id,
                channel_id,
                self.CHANNEL_TTL_S // 3600,
            )
        except Exception as exc:
            logger.error("Failed to subscribe Drive push for user=%s: %s", entry.user_id, exc)

    @staticmethod
    def _get_start_page_token(entry: SubscriptionEntry) -> str:
        creds = Credentials(token=entry.google_access_token)
        service = build("drive", "v3", credentials=creds)
        resp = service.changes().getStartPageToken().execute()
        return resp["startPageToken"]

    @staticmethod
    def _watch_drive_changes(
        entry: SubscriptionEntry,
        channel_id: str,
        webhook_url: str,
        expiration_ms: int,
    ) -> str:
        """Call changes.watch() and return the resource_id."""
        creds = Credentials(token=entry.google_access_token)
        service = build("drive", "v3", credentials=creds)
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
            "expiration": str(expiration_ms),
        }
        resp = service.changes().watch(pageToken=entry.page_token, body=body).execute()
        return resp.get("resourceId", "")

    # ------------------------------------------------------------------
    # Change processing
    # ------------------------------------------------------------------

    async def _process_changes(self, entry: SubscriptionEntry) -> None:
        """Fetch delta via changes.list, filter to new files in folder, invoke agent."""
        try:
            changes, new_token = await asyncio.to_thread(
                self._list_changes, entry
            )
            entry.page_token = new_token  # advance the bookmark

            for change in changes:
                file_obj = change.get("file", {})
                mime_type = file_obj.get("mimeType", "")

                # Skip folders and anything that isn't a file.
                if mime_type == "application/vnd.google-apps.folder":
                    continue
                if change.get("removed"):
                    continue

                # Check if the file belongs to the watched folder.
                parents = file_obj.get("parents", [])
                if entry.folder_id not in parents:
                    continue

                file_name = file_obj.get("name", "Unknown file")
                logger.info("New file detected: user=%s file=%s", entry.user_id, file_name)
                await self._invoke_agent_for_file(entry, file_name)

        except Exception as exc:
            logger.error("Error processing Drive changes for user=%s: %s", entry.user_id, exc)

    @staticmethod
    def _list_changes(entry: SubscriptionEntry) -> tuple[list[dict], str]:
        """Synchronous changes.list call — run via asyncio.to_thread."""
        creds = Credentials(token=entry.google_access_token)
        service = build("drive", "v3", credentials=creds)
        all_changes = []
        page_token = entry.page_token

        while True:
            resp = service.changes().list(
                pageToken=page_token,
                spaces="drive",
                fields="nextPageToken,newStartPageToken,changes(removed,file(id,name,mimeType,parents))",
                includeItemsFromAllDrives=False,
            ).execute()
            all_changes.extend(resp.get("changes", []))
            if "nextPageToken" in resp:
                page_token = resp["nextPageToken"]
            else:
                new_token = resp.get("newStartPageToken", page_token)
                return all_changes, new_token

    # ------------------------------------------------------------------
    # Agent invocation (unchanged from drive_watcher.py)
    # ------------------------------------------------------------------

    async def _invoke_agent_for_file(self, entry: SubscriptionEntry, file_name: str) -> None:
        """Invoke the agent to read and summarise a newly uploaded file."""
        agent_executor = _get_agent_executor()
        prompt = (
            f"A new file named '{file_name}' was just uploaded to your watched Google Drive folder. "
            "Please read it and provide a concise summary of its contents."
        )
        config = {
            "configurable": {
                "thread_id": entry.thread_id,
                "google_access_token": entry.google_access_token,
            }
        }

        collected_tokens: list[str] = []
        try:
            async for chunk in agent_executor.astream(
                {"messages": [("user", prompt)]},
                config,
                stream_mode="messages",
            ):
                token, _ = chunk
                if (
                    hasattr(token, "content")
                    and isinstance(token.content, str)
                    and token.content
                    and getattr(token, "type", "") in ("ai", "AIMessageChunk")
                ):
                    collected_tokens.append(token.content)

            summary = "".join(collected_tokens)
            await entry.queue.put({
                "type": "drive_summary",
                "file_name": file_name,
                "summary": summary,
            })
            logger.info("Summary for '%s' queued for user=%s", file_name, entry.user_id)

        except Exception as exc:
            logger.error("Agent invocation failed for file '%s': %s", file_name, exc)
            await entry.queue.put({
                "type": "error",
                "file_name": file_name,
                "message": str(exc),
            })

    # ------------------------------------------------------------------
    # Channel renewal loop
    # ------------------------------------------------------------------

    async def _renewal_loop(self) -> None:
        """
        Every 30 minutes check if any channel is about to expire.
        If expiring within RENEW_BEFORE_EXPIRY_S, renew it.
        """
        import time
        while True:
            await asyncio.sleep(30 * 60)  # check every 30 minutes
            now_ms = int(time.time() * 1000)
            renew_threshold_ms = now_ms + self.RENEW_BEFORE_EXPIRY_S * 1000

            for user_id, entry in list(self._subscriptions.items()):
                if entry.channel_expiration_ms and entry.channel_expiration_ms <= renew_threshold_ms:
                    logger.info(
                        "Renewing Drive push channel for user=%s (expires in ≤%dh)",
                        user_id,
                        self.RENEW_BEFORE_EXPIRY_S // 3600,
                    )
                    await self._subscribe(entry)


# Module-level singleton
drive_event_service = DriveEventService()
