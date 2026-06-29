import os
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from tools import TOOLS

# Read system prompt from markdown file
prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system.md")
with open(prompt_path, "r") as f:
    SYSTEM_PROMPT = f.read()

llm = ChatOpenAI(model="gpt-5.4-nano", temperature=0)

# Initialize memory
memory = MemorySaver()

# Create the React agent using LangGraph's prebuilt function
agent_executor = create_react_agent(
    llm, 
    TOOLS,
    prompt=SYSTEM_PROMPT,
    checkpointer=memory,
)
