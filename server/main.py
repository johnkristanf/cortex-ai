from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import agent_executor
from dotenv import load_dotenv
import uvicorn
import json
from typing import AsyncGenerator

load_dotenv()

app = FastAPI(title="Cortex AI Agent Server")

class ChatRequest(BaseModel):
    message: str

async def generate_chat_stream(message: str) -> AsyncGenerator[str, None]:
    """Streams the response from the LangGraph agent."""
    
    # We use stream_mode="messages" to get token-by-token streaming of the agent's response
    # We also include other messages so we can see tool calls if desired, but here we just stream the final text.
    async for msg, metadata in agent_executor.astream(
        {"messages": [("user", message)]}, 
        stream_mode="messages"
    ):
        # We only want to stream back the content from the assistant's final response,
        # or we could stream tool call logs. Let's stream content chunks from the AI model.
        if msg.content and metadata.get("langgraph_node") == "agent":
            # msg is a BaseMessageChunk, so msg.content contains the next piece of text
            yield msg.content

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat with the AI agent. Returns a streaming response.
    """
    return StreamingResponse(
        generate_chat_stream(request.message), 
        media_type="text/plain"
    )

if __name__ == "__main__":
    # For local development
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
