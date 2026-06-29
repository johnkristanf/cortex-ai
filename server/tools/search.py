import os
from langchain_core.tools import tool
from firecrawl import Firecrawl

@tool
def web_search(query: str) -> str:
    """Search the web for current information. Searches for relevant URLs,
    then scrapes each page to retrieve the full content.
    
    Args:
        query: The search query to look up on the web.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return "Error: FIRECRAWL_API_KEY environment variable is not set."
        
    try:
        firecrawl = Firecrawl(api_key=api_key)
        
        # Step 1: Search — returns a SearchData object with a .web attribute
        search_response = firecrawl.search(query, limit=3)
        print("search_response: ", search_response)
        web_results = search_response.web or []
        
        if not web_results:
            return f"No search results found for query: {query}"
        
        formatted_results = f"Search Results for '{query}':\n\n"
        
        for idx, result in enumerate(web_results, 1):
            url = result.url or ""
            title = result.title or url
            
            if not url:
                continue
            
            # Step 2: Scrape each URL for full content
            try:
                scraped = firecrawl.scrape(url, formats=["markdown"])
                content = scraped.markdown if hasattr(scraped, "markdown") else scraped.get("markdown", "")
                
                content_preview = content[:1500].strip() if content else "No content retrieved."
            except Exception as scrape_err:
                content_preview = f"Failed to scrape: {scrape_err}"
            
            formatted_results += (
                f"{idx}. **{title}**\n"
                f"   URL: {url}\n"
                f"   Content:\n{content_preview}\n\n"
                f"{'—' * 40}\n\n"
            )
        
        return formatted_results
        
    except Exception as e:
        return f"An error occurred while searching the web: {str(e)}"
