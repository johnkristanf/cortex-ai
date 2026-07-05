from pydantic import BaseModel

class SendEmailRequest(BaseModel):
    google_access_token: str
    to: str
    subject: str
    body: str
    gmail_thread_id: str | None = None
