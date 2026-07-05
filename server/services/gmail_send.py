"""
gmail_send.py

Helper to send an email via the Gmail API using a provider access token.
"""

import base64
import logging
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def send_gmail_message(
    google_access_token: str,
    to: str,
    subject: str,
    body: str,
    gmail_thread_id: str | None = None,
) -> dict:
    """
    Send an email via the Gmail API.

    Returns a dict with 'status' and 'message_id' on success,
    or raises an exception on failure.
    """
    creds = Credentials(token=google_access_token)
    service = build("gmail", "v1", credentials=creds)

    mime_message = MIMEText(body)
    mime_message["to"] = to
    mime_message["subject"] = subject

    raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()
    message_body: dict = {"raw": raw}

    if gmail_thread_id:
        message_body["threadId"] = gmail_thread_id

    sent = service.users().messages().send(userId="me", body=message_body).execute()
    msg_id = sent.get("id", "unknown")

    logger.info("Email sent via Gmail API: message_id=%s to=%s", msg_id, to)
    return {"status": "sent", "message_id": msg_id}
