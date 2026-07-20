import os
import asyncio
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from agents.researcher.state import ResearcherState

logger = logging.getLogger(__name__)

model_name = os.environ.get("OPENAI_GP_MODEL", "gpt-4o-mini")

_llm = ChatOpenAI(model=model_name, temperature=0)

_EXTRACT_PROMPT = """You are a product data extractor.
Given raw text scraped from a product webpage and the user's search query,
extract ONE primary product that best matches the query.

Return a JSON object ONLY (no markdown, no explanation) in this exact format:
{{"name": "Product Name", "source": "https://exact-page-url.com", "price": "$X,XXX"}}

Rules:
- "name": The specific product model/name. Never generic names like "Product".
- "source": Use the exact URL provided, do not invent URLs.
- "price": The listed price. Use "N/A" if not found.
- If no relevant product is found on the page, return: {{"name": null, "source": null, "price": null}}
"""


async def _scrape_url(browser, url: str, query: str) -> dict | None:
    """Open a URL in a Playwright page, extract text, and call the LLM to structure it."""
    page = await browser.new_page()
    try:
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        # Extract visible text, limit to 4000 chars to stay within token budget
        raw_text = await page.evaluate("() => document.body.innerText")
        raw_text = (raw_text or "")[:4000].strip()

        if not raw_text:
            return None

        prompt_messages = [
            SystemMessage(content=_EXTRACT_PROMPT),
            HumanMessage(content=f"Search query: {query}\nPage URL: {url}\n\nPage text:\n{raw_text}"),
        ]
        response = _llm.invoke(prompt_messages)
        content = response.content.strip()

        import json
        try:
            product = json.loads(content)
            # Skip if LLM found nothing useful
            if not product.get("name"):
                return None
            # Ensure source is set to the actual URL
            product["source"] = url
            return product
        except json.JSONDecodeError:
            logger.warning(f"playwright_node: LLM returned non-JSON for {url}: {content[:100]}")
            return None

    except Exception as e:
        logger.warning(f"playwright_node: failed to scrape {url}: {e}")
        return None
    finally:
        await page.close()


async def _run_scraping(urls: list[str], query: str) -> list[dict]:
    """Launch Playwright and scrape all URLs concurrently."""
    from playwright.async_api import async_playwright

    products: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            tasks = [_scrape_url(browser, url, query) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    products.append(r)
        finally:
            await browser.close()
    return products


def playwright_node(state: ResearcherState) -> dict:
    """
    Iterates search_urls with Playwright, scrapes each page, and uses
    an LLM to extract structured product data: {name, source, price}.
    """
    urls: list[str] = state.get("search_urls") or []
    query: str = state.get("query") or "product"

    if not urls:
        return {
            "messages": [AIMessage(content="⚠️ No URLs to scrape. Skipping product extraction.")],
            "structured_products": [],
        }

    logger.info(f"playwright_node: scraping {len(urls)} URLs for query={query!r}")

    try:
        products = asyncio.run(_run_scraping(urls, query))
    except RuntimeError:
        # Already in an event loop (e.g. uvicorn) — use a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _run_scraping(urls, query))
            products = future.result(timeout=120)

    if not products:
        return {
            "messages": [AIMessage(content="⚠️ Could not extract structured product data from the scraped pages.")],
            "structured_products": [],
        }

    logger.info(f"playwright_node: extracted {len(products)} products")

    # Build a quick markdown preview
    preview_lines = [f"| Name | Source | Price |", "| --- | --- | --- |"]
    for p in products:
        name = p.get("name", "Unknown")
        src = p.get("source", "")
        price = p.get("price", "N/A")
        short_src = src.split("//")[-1][:40] if src else ""
        preview_lines.append(f"| {name} | {short_src} | {price} |")

    preview = "\n".join(preview_lines)

    return {
        "messages": [AIMessage(content=f"✅ Extracted **{len(products)}** products:\n\n{preview}\n\nBuilding your Excel file…")],
        "structured_products": products,
    }
