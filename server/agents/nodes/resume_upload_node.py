import base64
import io
import logging
import pypdf

from langchain_core.messages import AIMessage, HumanMessage
from agents.state import AgentState
from agents.nodes.resume_check_node import extract_resume_profile
from lib.supabase import get_supabase

logger = logging.getLogger(__name__)

_ASK_FOR_RESUME_MSG = (
    "To help you find the best job matches, I need your resume. 📄\n\n"
    "Please upload your resume file (PDF, TXT, DOCX) or paste it directly in the chat. "
    "I'll analyze it and search for the most relevant opportunities for you!"
)


def _upload_resume(user_id: str, resume_text: str) -> None:
    sb = get_supabase()
    sb.storage.from_("resumes").upload(
        path=f"{user_id}/resume.txt",
        file=resume_text.encode("utf-8"),
        file_options={"content-type": "text/plain", "upsert": "true"},
    )
    logger.info(f"resume_upload_node: uploaded resume for user {user_id}")


def _get_latest_user_text(state: AgentState) -> str | None:
    """Return the content of the most recent HumanMessage."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return None


def resume_upload_node(state: AgentState, config) -> dict:
    """
    If no resume has been requested yet, ask the user for one and wait.
    If we already asked, treat the latest user message as the resume,
    upload it to Supabase, and extract the profile.
    """
    user_id = config.get("configurable", {}).get("user_id")
    file_name = config.get("configurable", {}).get("file_name")
    file_base64 = config.get("configurable", {}).get("file_base64")
    resume_requested = state.get("resume_requested", False)

    if not resume_requested:
        # First visit — ask the user for their resume
        return {
            "messages": [AIMessage(content=_ASK_FOR_RESUME_MSG)],
            "resume_requested": True,
        }

    resume_text = None
    if file_base64 and file_name:
        
        try:
            file_bytes = base64.b64decode(file_base64)
            # Upload original file to Supabase
            if user_id:
                sb = get_supabase()
                ext = file_name.split(".")[-1].lower() if "." in file_name else "txt"
                content_type = "application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx" else "text/plain"
                sb.storage.from_("resumes").upload(
                    path=f"{user_id}/resume.{ext}",
                    file=file_bytes,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
                logger.info(f"resume_upload_node: uploaded file {file_name} for user {user_id}")

            # Extract text from file_bytes
            if file_name.lower().endswith(".pdf"):
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                resume_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            elif file_name.lower().endswith(".docx"):
                import docx
                doc = docx.Document(io.BytesIO(file_bytes))
                resume_text = "\n".join([p.text for p in doc.paragraphs])
            else:
                resume_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"resume_upload_node: failed to process file — {e}")

    if not resume_text:
        # Second visit — the latest user message should contain the resume
        resume_text = _get_latest_user_text(state)

        if not resume_text or len(resume_text.strip()) < 100:
            return {
                "messages": [AIMessage(
                    content="I didn't receive enough text to parse as a resume. "
                            "Please upload your resume file or paste your full resume text and I'll get right on it!"
                )],
            }

        # Upload to Supabase Storage
        if user_id:
            try:
                _upload_resume(user_id, resume_text)
            except Exception as e:
                logger.warning(f"resume_upload_node: failed to upload — {e}")

    # Extract structured profile
    profile = extract_resume_profile(resume_text)

    return {
        "resume_profile": profile,
        "resume_requested": False,
    }
