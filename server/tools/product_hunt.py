import os
from langchain_core.tools import tool
from firecrawl import FirecrawlApp

PRODUCT_HUNT_URL = "https://www.producthunt.com/"


@tool
def product_hunt_search() -> str:
    """Scrape the Product Hunt homepage to retrieve today's top trending products,
    as well as the top products from yesterday, last week, and last month.

    Returns a formatted Markdown summary with product names, taglines, upvote counts,
    and direct Product Hunt links, organised by time period.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return "Error: FIRECRAWL_API_KEY environment variable is not set."

    try:
        app = FirecrawlApp(api_key=api_key)

        result = app.scrape_url(
            PRODUCT_HUNT_URL,
            formats=["markdown"],
            only_main_content=True,
        )

        # The Python SDK returns a ScrapeResponse object; access markdown via attribute
        if hasattr(result, "markdown") and result.markdown:
            content = result.markdown
        elif isinstance(result, dict):
            content = result.get("markdown", "")
        else:
            content = str(result)

        if not content:
            return "No content retrieved from Product Hunt."

        print(f"content: {content}")

        return (
            "## Product Hunt Trending Products\n\n"
            "*(Scraped directly from producthunt.com)*\n\n"
            + content
        )

    except Exception as exc:
        return f"An error occurred while scraping Product Hunt: {exc}"
