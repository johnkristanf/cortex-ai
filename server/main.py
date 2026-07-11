import logging
import os
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

    print(f"user_text: {user_text}")

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
