"""
read.py

LangGraph node: read_email_node
Fetches unread Gmail messages, marks them as read, and stores
the structured list in AgentState for the write_reply node to iterate over.
"""

import logging
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from agents.state import AgentState

logger = logging.getLogger(__name__)


# ── Helper ─────────────────────────────────────────────────────────────────────
def _fetch_unread_emails(google_access_token: str) -> list[dict]:
    """Fetch up to 5 unread emails and mark them as read. Returns structured email dicts."""
    creds = Credentials(token=google_access_token)
    service = build("gmail", "v1", credentials=creds)

    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=5,
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_id = msg["id"]
        msg_data = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        headers = msg_data["payload"]["headers"]
        subject  = next((h["value"] for h in headers if h["name"] == "Subject"),  "No Subject")
        sender   = next((h["value"] for h in headers if h["name"] == "From"),     "Unknown Sender")
        reply_to = next((h["value"] for h in headers if h["name"] == "Reply-To"), sender)
        snippet  = msg_data.get("snippet", "")
        thread_id = msg_data.get("threadId", "")

        emails.append({
            "sender":    sender,
            "reply_to":  reply_to,
            "subject":   subject,
            "snippet":   snippet,
            "thread_id": thread_id,
        })

        # Mark as read
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    return emails


# ── Node ───────────────────────────────────────────────────────────────────────
def read_email_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Fetches unread emails from Gmail and stores them in state.
    Resets the iteration index to 0 so write_reply_node starts from the first email.
    """
    google_access_token = config.get("configurable", {}).get("google_access_token")

    if not google_access_token:
        logger.warning("read_email_node: no google_access_token in config")
        return {
            "unread_emails": [],
            "current_email_index": 0,
            "drafts_proposed": [],
            "messages": [HumanMessage(
                content="I couldn't check your email — no Google access token was provided."
            )],
        }

    try:
        emails = _fetch_unread_emails(google_access_token)
        logger.info("read_email_node: fetched %d unread email(s)", len(emails))

        count = len(emails)
        info_msg = (
            f"Fetched {count} unread email(s). Generating draft replies…"
            if count > 0
            else "You have no unread emails right now."
        )
        return {
            "unread_emails": emails,
            "current_email_index": 0,
            "drafts_proposed": [],
            "messages": [HumanMessage(content=info_msg)],
        }

    except HttpError as e:
        logger.error("read_email_node: Gmail API error: %s", e)
        return {
            "unread_emails": [],
            "current_email_index": 0,
            "drafts_proposed": [],
            "messages": [HumanMessage(content=f"Gmail API error while reading emails: {e}")],
        }
    except Exception as e:
        logger.error("read_email_node: unexpected error: %s", e)
        return {
            "unread_emails": [],
            "current_email_index": 0,
            "drafts_proposed": [],
            "messages": [HumanMessage(content=f"Unexpected error while reading emails: {e}")],
        }
