from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.researcher.nodes import (
    researcher_agent_node,
    firecrawl_node,
    playwright_node,
    excel_builder_node,
)

# ── Proper TypedDict state ────────────────────────────────────────────────────

class ResearcherState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str | None
    search_urls: list[str]
    raw_texts: list[str]
    structured_products: list[dict]
    excel_filename: str | None
    download_ready: bool


# ── Memory ────────────────────────────────────────────────────────────────────

memory = MemorySaver()

# ── Build the graph ───────────────────────────────────────────────────────────

workflow = StateGraph(ResearcherState)

workflow.add_node("agent", researcher_agent_node)
workflow.add_node("firecrawl_search", firecrawl_node)
workflow.add_node("playwright_scrape", playwright_node)
workflow.add_node("excel_builder", excel_builder_node)

# Linear pipeline: agent → search → scrape → excel → END
workflow.add_edge(START, "agent")
workflow.add_edge("agent", "firecrawl_search")
workflow.add_edge("firecrawl_search", "playwright_scrape")
workflow.add_edge("playwright_scrape", "excel_builder")
workflow.add_edge("excel_builder", END)

researcher_executor = workflow.compile(checkpointer=memory)
