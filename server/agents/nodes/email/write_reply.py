"""
write_reply.py

LangGraph node: write_reply_node
Iterates through unread_emails in state, generates a professional draft
reply for the current email via the LLM, and appends it to drafts_proposed.

Also exports: should_continue_writing — the conditional edge router.
"""

import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from agents.state import AgentState

logger = logging.getLogger(__name__)

# ── LLM ───────────────────────────────────────────────────────────────────────
_llm = ChatOpenAI(
    model="gpt-5.4-nano",
    temperature=0.4,
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-nano",
    },
)

_REPLY_SYSTEM_PROMPT = """You are a professional email assistant.
Given an email, write a concise, courteous, and professional reply.
- Keep the reply to 3-5 sentences unless the email requires more.
- Do NOT include subject lines or headers — only the plain body text.
- Do NOT add sign-offs like "Best regards" unless they fit the tone.
- Match the formality level of the original email."""


# ── Node ───────────────────────────────────────────────────────────────────────
def write_reply_node(state: AgentState) -> dict:
    """
    Generates a draft reply for the email at current_email_index,
    appends it to drafts_proposed, and increments the index.
    """
    emails: list[dict] = state.get("unread_emails", [])
    index: int = state.get("current_email_index", 0)
    existing_drafts: list[dict] = state.get("drafts_proposed", [])

    if index >= len(emails):
        # Safety guard — should not reach here via normal routing
        logger.warning("write_reply_node called but no email at index %d", index)
        return {"current_email_index": index}

    email = emails[index]
    logger.info("write_reply_node: drafting reply for email %d/%d", index + 1, len(emails))

    prompt = (
        f"Original email:\n"
        f"  From    : {email['sender']}\n"
        f"  Subject : {email['subject']}\n"
        f"  Message : {email['snippet']}\n\n"
        "Write a professional reply to this email."
    )

    response = _llm.invoke([
        SystemMessage(content=_REPLY_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    new_draft = {
        "to":             email["reply_to"],
        "subject":        f"Re: {email['subject']}",
        "body":           response.content.strip(),
        "gmail_thread_id": email["thread_id"],
    }

    return {
        "drafts_proposed":    existing_drafts + [new_draft],
        "current_email_index": index + 1,
    }

