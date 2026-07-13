import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from agents.state import AgentState
from tools import TOOLS

# Read system prompt from markdown file
prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts", "system.md")
with open(prompt_path, "r") as f:
    SYSTEM_PROMPT = f.read()

model_name = os.environ.get("OPENAI_GP_MODEL", "gpt-4o-mini")

llm = ChatOpenAI(
    model=model_name,
    temperature=0,
    metadata={
        "ls_provider": "openai",
        "ls_model_name": model_name
    }
)
llm_with_tools = llm.bind_tools(TOOLS)

def agent_node(state: AgentState):
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
