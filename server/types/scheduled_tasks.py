from pydantic import BaseModel

class ScheduledTaskSubscriptionRequest(BaseModel):
    user_id: str
    thread_id: str = "default"
    google_access_token: str | None = None
