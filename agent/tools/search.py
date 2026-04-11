import asyncio

from tavily import TavilyClient

from core.config import settings

# Initialize Tavily client
client = TavilyClient(api_key=getattr(settings, "TAVILY_API_KEY", None))


async def search_tavily(query: str, max_results: int = 5, depth: str = "advanced"):
    """
    Perform an asynchronous web search using Tavily API with retry logic.

    Args:
        query (str): The search query string.
        max_results (int): Maximum number of results to return (default=5).
        depth (str): Search depth, "basic" or "advanced" (default="advanced").

    Returns:
        dict: Tavily API response containing search results, or empty dict on failure.
    """
    attempts = 0
    while attempts < 5:
        try:
            return await asyncio.to_thread(
                client.search,
                query=query,
                include_answer="advanced",
                search_depth=depth,
                max_results=max_results,
                include_favicon=True,
            )
        except Exception as e:
            attempts += 1
            print(f"Tavily search attempt {attempts} failed: {e}")
            if attempts >= 5:
                return {}
            await asyncio.sleep(1)
