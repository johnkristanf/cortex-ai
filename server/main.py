import os
import logging
import asyncio
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


from utils import sse_message
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from telegram import Update, Bot
from telegram.ext import Application
from fastapi.responses import StreamingResponse, FileResponse
from schemas.chat import ChatRequest
from schemas.scheduled_tasks import ScheduledTaskSubscriptionRequest
from schemas.email import SendEmailRequest
from dotenv import load_dotenv
load_dotenv()


from agents import agent_executor
from agents.researcher import researcher_executor
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import langsmith as ls

from services.telegram import telegram_service
from services.gmail_send import send_gmail_message
from services.scheduled_tasks import scheduled_task_service

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
# Chat Agent – SSE streaming endpoint (used by the mobile app)
# ------------------------------------------------------------------

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id or "default"

    config = {
        "configurable": {
            "thread_id": thread_id,
            "google_access_token": request.google_access_token,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "user_id": request.user_id,
            "file_name": request.file_name,
            "file_base64": request.file_base64,
        },
        "tags": ["mobile", "cortex-ai"],
        "metadata": {
            "thread_id": thread_id,
            "source": "mobile_chat",
            "ls_provider": "openai",
            "ls_model_name": "gpt-5.4-nano",
        },
    }

    # Nodes that may produce an AIMessage directly (no LLM involved).
    _DIRECT_MESSAGE_NODES = {"resume_upload", "find_jobs"}

    async def generate():
        try:
            with ls.tracing_context(
                project_name="cortex-ai",
                tags=["mobile", "cortex-ai"],
                metadata=config["metadata"],
            ):
                async for event in agent_executor.astream_events(
                    {"messages": [("user", request.message)]},
                    config,
                    version="v2",
                ):
                    event_type = event["event"]

                    # Stream LLM tokens as they arrive
                    if event_type == "on_chat_model_stream":
                        token = event["data"]["chunk"].content
                        if token:
                            yield sse_message({"text": token})

                    # Stream AIMessages produced directly by non-LLM nodes
                    elif event_type == "on_chain_end":
                        node_name = event.get("name", "")
                        if node_name in _DIRECT_MESSAGE_NODES:
                            output = event["data"].get("output") or {}
                            msgs = output.get("messages", [])
                            for msg in msgs:
                                content = getattr(msg, "content", None)
                                if content:
                                    yield sse_message({"text": content})

        except Exception as exc:
            logging.exception("Error in /chat endpoint")
            yield sse_message({"error": str(exc)})

        yield sse_message({"done": True})


    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------
# ------------------------------------------------------------------
# Scheduled Tasks – SSE stream for mobile
# ------------------------------------------------------------------

@app.post("/scheduled/subscribe")
async def subscribe_scheduled(request: ScheduledTaskSubscriptionRequest):
    """
    Registers a mobile client for scheduled tasks.
    Currently, this acts as a handshake. The actual SSE queue is created
    in the GET /scheduled/notifications endpoint.
    """
    return {"status": "ok", "message": "Subscribed successfully"}

@app.get("/scheduled/notifications/{user_id}")
async def scheduled_notifications(user_id: str, request: Request):
    """
    SSE endpoint for the mobile app to receive scheduled task outputs.
    """
    queue = scheduled_task_service.get_queue(user_id)

    async def event_generator():
        try:
            while True:
                # If client disconnected, request.is_disconnected() might be true
                if await request.is_disconnected():
                    break

                # Wait for the next notification payload
                payload = await queue.get()
                yield sse_message(payload)
                queue.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            scheduled_task_service.remove_queue(user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------
# Product Researcher Agent – SSE streaming endpoint
# ------------------------------------------------------------------

@app.post("/researcher/chat")
async def researcher_chat_endpoint(request: ChatRequest):
    """
    Streams the 4-node product researcher pipeline.
    In addition to text chunks, emits a JSON SSE event with a `download_url`
    once the Excel file is ready.
    """
    thread_id = request.thread_id or "default"

    config = {
        "configurable": {"thread_id": f"researcher-{thread_id}"},
        "tags": ["researcher", "cortex-ai"],
        "metadata": {
            "thread_id": thread_id,
            "source": "researcher_chat",
        },
    }

    _RESEARCHER_STREAM_NODES = {"excel_builder"}

    async def generate():
        try:
            with ls.tracing_context(
                project_name="cortex-ai",
                tags=["researcher", "cortex-ai"],
                metadata=config["metadata"],
            ):
                async for event in researcher_executor.astream_events(
                    {"messages": [("user", request.message)]},
                    config,
                    version="v2",
                ):
                    event_type = event["event"]

                    # Stream LLM tokens
                    if event_type == "on_chat_model_stream":
                        token = event["data"]["chunk"].content
                        if token:
                            yield sse_message({"text": token})

                    # When excel_builder finishes, emit AIMessage text + download_url
                    elif event_type == "on_chain_end":
                        node_name = event.get("name", "")
                        if node_name in _RESEARCHER_STREAM_NODES:
                            output = event["data"].get("output") or {}
                            msgs = output.get("messages", [])
                            for msg in msgs:
                                content = getattr(msg, "content", None)
                                if content:
                                    yield sse_message({"text": content})
                            # Emit download_url if Excel was built
                            filename = output.get("excel_filename")
                            if filename and output.get("download_ready"):
                                yield sse_message({"download_url": f"/researcher/download/{filename}"})

        except Exception as exc:
            logging.exception("Error in /researcher/chat endpoint")
            yield sse_message({"error": str(exc)})

        yield sse_message({"done": True})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/email/send")
@ls.traceable(name="send_email")
async def send_email_endpoint(request: SendEmailRequest):
    try:
        result = send_gmail_message(
            google_access_token=request.google_access_token,
            to=request.to,
            subject=request.subject,
            body=request.body,
            gmail_thread_id=request.gmail_thread_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/researcher/download/{filename}")
async def researcher_download(filename: str):
    """
    Serves a generated Excel file from /tmp/.
    The filename must end with .xlsx and contain only safe characters.
    """
    import re
    if not re.match(r'^[\w\-]+\.xlsx$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    filepath = f"/tmp/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found or expired.")

    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


# ------------------------------------------------------------------
# Server entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
