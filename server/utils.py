
import json

def sse_message(data: dict) -> str:
    """Formats a dictionary as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"