import operator
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The state of the agent.

    Attributes:
        messages: A list of messages in the conversation.
                  The `add_messages` reducer appends new messages to the existing list.
        file_content: The content of a file read from Google Drive.
        file_summary: The summary of the file content.
        drafts_proposed: Email drafts proposed by the agent.

    Job Application workflow:
        resume_profile: Structured extraction of the user's resume
                        (summary, skills, experiences, education, target_role).
        resume_requested: True while we're waiting for the user to paste their resume.
        job_preferences: Structured dict of the user's job search preferences
                         (target_roles, work_arrangement, location, salary).
        job_preferences_requested: True while we're waiting for the user to
                                   supply their job search preferences.
        job_results: The last formatted job-listing markdown returned to chat.
        workflow: Name of the active subgraph workflow (e.g. "job_application").
    """
    messages: Annotated[list[BaseMessage], add_messages]
    file_content: str | None
    file_summary: str | None

    # Email processing state
    drafts_proposed: Annotated[list[dict], operator.add]

    # Job Application workflow state
    resume_profile: dict | None
    resume_requested: bool
    job_preferences: dict | None
    job_preferences_requested: bool
    job_results: str | None
    workflow: str | None
