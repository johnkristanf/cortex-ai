from langchain_core.tools import tool

@tool
def check_email() -> str:
    """Check the user's email inbox for recent unread messages."""
    # Mock email implementation
    emails = [
        {"from": "boss@company.com", "subject": "Urgent: Project Update", "snippet": "Please send the latest status report by EOD."},
        {"from": "newsletter@techdaily.com", "subject": "Top 10 AI Frameworks in 2026", "snippet": "Check out the latest tools for building AI agents..."},
        {"from": "noreply@github.com", "subject": "[GitHub] Please review PR #42", "snippet": "Alice has requested your review on the cortex-ai repository."},
    ]
    
    response = "You have 3 unread emails:\n\n"
    for idx, email in enumerate(emails, 1):
        response += f"{idx}. From: {email['from']}\n   Subject: {email['subject']}\n   Preview: {email['snippet']}\n\n"
        
    return response
