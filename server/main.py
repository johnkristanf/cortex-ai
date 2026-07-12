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
from fastapi.responses import StreamingResponse
from schemas.chat import ChatRequest
from schemas.scheduled_tasks import ScheduledTaskSubscriptionRequest
from schemas.email import SendEmailRequest
from dotenv import load_dotenv
load_dotenv()


from agents import agent_executor
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
        },
        "tags": ["mobile", "cortex-ai"],
        "metadata": {
            "thread_id": thread_id,
            "source": "mobile_chat",
            "ls_provider": "openai",
            "ls_model_name": "gpt-5.4-nano",
        },
    }

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
                    kind = event["event"]

                    # Stream LLM tokens as they arrive
                    if kind == "on_chat_model_stream":
                        token = event["data"]["chunk"].content
                        if token:
                            yield sse_message({"text": token})

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
# Telegram Bot Webhook
# ------------------------------------------------------------------

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram Bot webhook endpoint.
    Telegram calls this URL for every update. Each text message is forwarded
    to the agent; the streamed response is collected and sent back to the chat.
    """
    data = await request.json()
    update = Update.de_json(data, await telegram_service.get_bot())

    # Only handle plain text messages
    if not (update.message and update.message.text):
        return {"ok": True}

    chat_id = update.message.chat_id
    user_text = update.message.text
    thread_id = f"telegram-{chat_id}"

    config = {
        "configurable": {
            "thread_id": thread_id,
            "google_access_token": None,
            "latitude": None,
            "longitude": None,
        },
        "tags": ["telegram", "cortex-ai"],
        "metadata": {
            "thread_id": thread_id,
            "source": "telegram_webhook",
            "ls_provider": "openai",
            "ls_model_name": "gpt-4o-mini",
        },
    }

    reply_text = "I'm not sure how to respond to that."
    try:
        with ls.tracing_context(
            project_name="cortex-ai",
            tags=["telegram", "cortex-ai"],
            metadata=config["metadata"],
        ):
            result = await agent_executor.ainvoke(
                {"messages": [("user", user_text)]},
                config,
            )
            # The last message in the list is the agent's final reply
            last_msg = result["messages"][-1]
            if hasattr(last_msg, "content") and last_msg.content:
                reply_text = last_msg.content
    except Exception as exc:
        logging.exception("Error running agent for Telegram update")
        reply_text = f"Sorry, something went wrong: {exc}"

    await telegram_service.send_message(chat_id=chat_id, text=reply_text)

    return {"ok": True}


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
        # logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------
# Server entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
