from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from agent import agent_executor
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Cortex AI Agent Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (you can restrict this in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (POST, GET, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    google_access_token: str | None = None

from fastapi.responses import StreamingResponse
import json

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "google_access_token": request.google_access_token,
        }
    }
    
    async def event_generator():
        try:
            async for chunk in agent_executor.astream(
                {"messages": [("user", request.message)]}, 
                config,
                stream_mode="messages"
            ):
                token, metadata = chunk
                # Only stream tokens from the assistant (not tools or human)
                # Ensure the token has a content attribute and it's a string
                if hasattr(token, "content") and isinstance(token.content, str) and token.content:
                    # In LangGraph, message chunks have an 'id' and 'content'
                    token_type = getattr(token, "type", "")
                    if token_type in ("ai", "AIMessageChunk"):
                        # Yield the content chunk as Server-Sent Events
                        yield f"data: {json.dumps({'text': token.content})}\n\n"
            
            # Send a specific end event when done
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Start the server
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
