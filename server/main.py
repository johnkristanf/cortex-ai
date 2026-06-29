from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from agent import agent_executor
import uvicorn
import json

app = FastAPI(title="Cortex AI Agent Server")

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat with the AI agent. Returns a JSON response.
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await agent_executor.ainvoke({"messages": [("user", request.message)]}, config)
    
    # The result contains the full state. The last message is the agent's response.
    final_message = result["messages"][-1].content
    
    return {"response": final_message}

if __name__ == "__main__":
    # For local development
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
