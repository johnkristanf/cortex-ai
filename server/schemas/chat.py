from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    google_access_token: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    user_id: str | None = None
    file_name: str | None = None
    file_base64: str | None = None
