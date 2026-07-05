from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from agents import agent_executor
from services.scheduled_tasks import scheduled_task_service
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
import langsmith as ls


# ------------------------------------------------------------------
# App lifecycle – start/stop the Drive event service
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduled_task_service.start()
    yield
    scheduled_task_service.stop()


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





class ScheduledTaskSubscriptionRequest(BaseModel):
    user_id: str
    thread_id: str = "default"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.post("/chat")
@ls.traceable(name="chat_endpoint")
async def chat_endpoint(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "google_access_token": request.google_access_token,
        },
        # Bubble user metadata into every child LLM trace in LangSmith
        "tags": ["chat", "cortex-ai"],
        "metadata": {
            "thread_id": request.thread_id,
            "source": "chat_endpoint",
            "ls_provider": "openai",
            "ls_model_name": "gpt-5.4-nano",
        },
    }

    logger = logging.getLogger("chat_endpoint")

    async def event_generator():
        last_usage: dict | None = None
        try:
            with ls.tracing_context(
                project_name="cortex-ai",
                tags=["chat", "cortex-ai"],
                metadata={
                    "thread_id": request.thread_id,
                    "source": "chat_endpoint",
                    "ls_provider": "openai",
                    "ls_model_name": "gpt-5.4-nano",
                },
            ):
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

                    # Capture usage_metadata from the final chunk (set by OpenAI at stream end)
                    if getattr(token, "usage_metadata", None):
                        last_usage = token.usage_metadata

            # ── LLM cost logging ──────────────────────────────────────────
            if last_usage:
                logger.info(
                    "[LLM usage] thread=%s input_tokens=%d output_tokens=%d total_tokens=%d",
                    request.thread_id,
                    last_usage.get("input_tokens", 0),
                    last_usage.get("output_tokens", 0),
                    last_usage.get("total_tokens", 0),
                )
                yield f"data: {json.dumps({'usage': last_usage})}\n\n"
            # ─────────────────────────────────────────────────────────────

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")




@app.post("/scheduled/subscribe")
@ls.traceable(name="scheduled_subscribe")
async def scheduled_subscribe_endpoint(request: ScheduledTaskSubscriptionRequest):
    """
    Subscribe a user to scheduled web search notifications.
    """
    scheduled_task_service.register(
        user_id=request.user_id,
        thread_id=request.thread_id,
    )
    return {
        "status": "subscribed",
        "user_id": request.user_id,
    }


@app.get("/scheduled/notifications/{user_id}")
async def scheduled_notifications_endpoint(user_id: str):
    """
    SSE stream that delivers scheduled search summaries to the mobile client.
    """
    queue = scheduled_task_service.get_queue(user_id)
    if queue is None:
        raise HTTPException(
            status_code=404,
            detail="No scheduled task subscription found for this user. Call POST /scheduled/subscribe first.",
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
