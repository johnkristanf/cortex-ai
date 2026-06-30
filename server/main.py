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

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await agent_executor.ainvoke({"messages": [("user", request.message)]}, config)
    
    # The result contains the full state. The last message is the agent's response.
    final_message = result["messages"][-1].content
    
    return {"response": final_message}

# Start the server
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
