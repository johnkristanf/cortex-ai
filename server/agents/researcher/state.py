import operator
from typing import Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ResearcherState(dict):
    """
    State for the Product Researcher agent.

    Attributes:
        messages:            Conversation messages (streamed to mobile).
        query:               Raw product search query extracted from the user message.
        search_urls:         List of URLs returned by Firecrawl search.
        raw_texts:           Scraped inner-text from each URL (parallel to search_urls).
        structured_products: LLM-structured product records [{name, source, price}].
        excel_filename:      Basename of the generated .xlsx file (stored in /tmp).
        download_ready:      True once the Excel file has been written.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    query: str | None
    search_urls: list[str]
    raw_texts: list[str]
    structured_products: list[dict]
    excel_filename: str | None
    download_ready: bool
