from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tools import TOOLS

# Initialize the LLM
# This expects OPENAI_API_KEY to be set in the environment
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Create the React agent using LangGraph's prebuilt function
agent_executor = create_react_agent(llm, TOOLS)
