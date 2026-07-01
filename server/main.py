from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from agents import agent_executor
from services.drive_events import drive_event_service
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio


# ------------------------------------------------------------------
# App lifecycle – start/stop the Drive event service
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await drive_event_service.start()
    yield
    await drive_event_service.stop()


app = FastAPI(title="Cortex AI Agent Server", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    google_access_token: str | None = None


class DriveSubscriptionRequest(BaseModel):
    user_id: str
    folder_id: str
    google_access_token: str
    thread_id: str = "default"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "google_access_token": request.google_access_token,
        }
    }
    
    async def event_generator():
        try:
            async for chunk in agent_executor.astream(
                {"messages": [("user", request.message)]}, 
                config,
                stream_mode="messages"
            ):
                token, metadata = chunk
                if hasattr(token, "content") and isinstance(token.content, str) and token.content:
                    token_type = getattr(token, "type", "")
                    if token_type in ("ai", "AIMessageChunk"):
                        yield f"data: {json.dumps({'text': token.content})}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/drive/subscribe")
async def drive_subscribe_endpoint(request: DriveSubscriptionRequest):
    """
    Register a Google Drive folder for event-driven monitoring via Push Notifications.

    The service will register a webhook channel with the Drive API. Google will call
    POST /drive/webhook whenever a file is created or modified in the user's Drive,
    at which point the server fetches only the delta and invokes the agent to summarise
    any new files in the watched folder.

    The mobile client should call this endpoint once after login.
    """
    drive_event_service.register(
        user_id=request.user_id,
        folder_id=request.folder_id,
        google_access_token=request.google_access_token,
        thread_id=request.thread_id,
    )
    return {
        "status": "subscribed",
        "user_id": request.user_id,
        "folder_id": request.folder_id,
    }


@app.post("/drive/webhook")
async def drive_webhook_endpoint(request: Request):
    """
    Receives Google Drive Push Notifications.

    Google POSTs here whenever anything changes in a subscribed Drive.
    We return 200 immediately (required within 10 s) and dispatch processing
    as a background task so the response is never delayed by agent work.
    """
    headers = dict(request.headers)
    # handle_webhook schedules its own asyncio.create_task internally
    await drive_event_service.handle_webhook(headers)
    return {"status": "ok"}


@app.get("/notifications/{user_id}")
async def notifications_endpoint(user_id: str):
    """
    SSE stream that delivers proactive Drive summaries to the mobile client.
    The client should open a persistent connection to this endpoint after login.
    """
    queue = drive_event_service.get_queue(user_id)
    if queue is None:
        raise HTTPException(
            status_code=404,
            detail="No Drive subscription found for this user. Call POST /drive/subscribe first.",
        )

    async def event_generator():
        # Send an initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"
        
        while True:
            try:
                # Wait up to 20s for a notification, then send a heartbeat
                notification = await asyncio.wait_for(queue.get(), timeout=20.0)
                yield f"data: {json.dumps(notification)}\n\n"
            except asyncio.TimeoutError:
                # Heartbeat keeps the connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ------------------------------------------------------------------
# Server entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
