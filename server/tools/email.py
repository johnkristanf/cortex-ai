import logging
from langchain_core.tools import tool
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.runnables import RunnableConfig
from email.message import EmailMessage
import base64

logger = logging.getLogger(__name__)

@tool("get_unread_emails")
def get_unread_emails(
    config: RunnableConfig, 
    search_query: str = None,
    label_ids: list[str] = None,
    max_results: int = None, 
) -> str | list[dict]:
    """
    Fetches emails from Gmail.
    Args:
        search_query: Optional. A specific query to search for (e.g., "Virtual Coffee"). If provided, it searches across all emails and you DO NOT need to ask for category/quantity.
        label_ids: List of Gmail label IDs. REQUIRED if search_query is NOT provided. 
                   If the user just asked to check emails generally, DO NOT GUESS. You MUST ask which category to check.
                   Use Gmail category labels: CATEGORY_PERSONAL (Primary), CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, CATEGORY_UPDATES.
                   Combine with "UNREAD" to get unread emails (e.g., ["CATEGORY_PERSONAL", "UNREAD"]).
        max_results: Maximum number of emails to fetch (max 20). REQUIRED if search_query is NOT provided.
    """
    if not search_query and (not label_ids or not max_results):
        return "Error: You must provide a 'search_query' OR both 'label_ids' and 'max_results'. Please ask the user for the inbox category and quantity to pull."

    google_access_token = config.get("configurable", {}).get("google_access_token")
    if not google_access_token:
        return "Error: No Google Access Token provided. Cannot fetch emails."

    try:
        creds = Credentials(token=google_access_token)
        service = build("gmail", "v1", credentials=creds)

        # Build request parameters
        req_params = {
            "userId": "me",
            "maxResults": min(max_results, 20) if max_results else 5,
        }
        if search_query:
            req_params["q"] = search_query
        if label_ids:
            req_params["labelIds"] = label_ids

        results = service.users().messages().list(**req_params).execute()

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

            # Mark as read only if we specifically fetched UNREAD messages
            if label_ids and "UNREAD" in label_ids:
                service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()

        return emails

    except HttpError as e:
        logger.error("Gmail API error: %s", e)
        return f"Gmail API error while reading emails: {e}"
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return f"Unexpected error while reading emails: {e}"


@tool("save_email_draft")
def save_email_draft(config: RunnableConfig, to: str, subject: str, body: str, gmail_thread_id: str) -> str:
    """
    Creates a draft email in the user's Gmail account.
    Call this tool when you have drafted a reply to an email.
    """
    google_access_token = config.get("configurable", {}).get("google_access_token")
    if not google_access_token:
        return "Error: No Google Access Token provided. Cannot create draft."

    try:
        creds = Credentials(token=google_access_token)
        service = build("gmail", "v1", credentials=creds)

        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        message["Subject"] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {
            "message": {
                "raw": encoded_message,
                "threadId": gmail_thread_id
            }
        }
        
        draft = service.users().drafts().create(userId="me", body=create_message).execute()
        return f"Draft created successfully in Gmail (ID: {draft['id']})."
    except HttpError as e:
        return f"Error creating draft: {e}"
