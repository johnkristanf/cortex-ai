from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

@tool
def check_email(config: RunnableConfig) -> str:
    """Check the user's Gmail inbox for recent unread messages and mark them as read."""
    
    # Read the Google access token passed through the agent's configurable context
    google_access_token = config.get("configurable", {}).get("google_access_token")

    if not google_access_token:
        return (
            "I cannot check your email because no Google access token was provided. "
            "Please make sure you signed in with Google (not email/password) so I can access Gmail on your behalf."
        )

    try:
        # Build credentials directly from the provider token — no local file needed
        creds = Credentials(token=google_access_token)
        service = build('gmail', 'v1', credentials=creds)

        # Fetch up to 5 UNREAD messages from INBOX
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            maxResults=5,
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            return "You have 0 unread emails in your inbox."

        response = f"You have {len(messages)} unread email(s):\n\n"

        for idx, msg in enumerate(messages, 1):
            msg_id = msg['id']
            msg_data = service.users().messages().get(
                userId='me', id=msg_id, format='full'
            ).execute()

            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender  = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            snippet = msg_data.get('snippet', '')

            response += (
                f"{idx}. From: {sender}\n"
                f"   Subject: {subject}\n"
                f"   Preview: {snippet}\n\n"
            )

            # Mark the email as read by removing the UNREAD label
            service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']},
            ).execute()

        return response

    except HttpError as error:
        return f"A Gmail API error occurred: {error}"
    except Exception as e:
        return f"An unexpected error occurred while checking email: {str(e)}"
