import os
import logging
from firecrawl import Firecrawl
from langchain_core.messages import AIMessage
from agents.researcher.state import ResearcherState

logger = logging.getLogger(__name__)

MAX_URLS = 5


def firecrawl_node(state: ResearcherState) -> dict:
    """
    Searches the web via Firecrawl using state['query'] and
    collects up to MAX_URLS product page URLs.
    """
    query = state.get("query") or ""
    if not query:
        return {
            "messages": [AIMessage(content="⚠️ No search query found. Please tell me what product you're looking for.")],
            "search_urls": [],
        }

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return {
            "messages": [AIMessage(content="⚠️ Product search unavailable: Firecrawl API key not configured.")],
            "search_urls": [],
        }

    try:
        app = Firecrawl(api_key=api_key)
        search_query = f"{query} buy price specs site:*.com OR site:*.net"
        logger.info(f"firecrawl_node: searching for {search_query!r}")

        results = app.search(search_query, limit=MAX_URLS)
        web_results = results.web or []

        urls = [r.url for r in web_results if r.url][:MAX_URLS]

        if not urls:
            return {
                "messages": [AIMessage(content=f"🔍 I searched for **{query}** but found no product pages. Try a more specific query.")],
                "search_urls": [],
            }

        url_list = "\n".join(f"- {u}" for u in urls)
        logger.info(f"firecrawl_node: found {len(urls)} URLs")

        return {
            "messages": [AIMessage(content=f"🔍 Found **{len(urls)}** product pages to analyze:\n{url_list}\n\nNow scraping each page for product details…")],
            "search_urls": urls,
        }

    except Exception as e:
        logger.exception("firecrawl_node: error during search")
        return {
            "messages": [AIMessage(content=f"⚠️ Search failed: {e}")],
            "search_urls": [],
        }
