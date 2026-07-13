from langchain_core.tools import tool


@tool
def start_job_application() -> str:
    """Call this tool IMMEDIATELY when the user wants to:
    - Find a job or full-time role
    - Get help with job applications
    - Search for job openings that match their skills and experience

    This triggers the automated Job Application workflow which will:
    1. Retrieve the user's resume from storage (or ask for one)
    2. Extract their key skills and target role
    3. Search for matching job openings
    """
    return "job_application_triggered"
