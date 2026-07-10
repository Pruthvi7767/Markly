from typing import Dict, Any
import requests
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
from markly.tools.registry import ToolRegistry

from markly.utils.retry import retry_with_backoff

def register_web_tools(registry: ToolRegistry):
    
    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def _do_ddg_search(query: str) -> list[str]:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
        return results

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def _do_http_fetch(url: str) -> str:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.text

    def web_search(args: Dict[str, Any]) -> str:
        query = args.get("query")
        if not query:
            return "Error: missing 'query'"
        try:
            results = _do_ddg_search(query)
            if not results:
                return "No results found."
            return "\n".join(results)
        except Exception as e:
            return f"Error searching web: {e}"

    def web_fetch(args: Dict[str, Any]) -> str:
        url = args.get("url")
        if not url:
            return "Error: missing 'url'"
        try:
            html_text = _do_http_fetch(url)
            soup = BeautifulSoup(html_text, "html.parser")
            # Extract readable text
            text = soup.get_text(separator="\n", strip=True)
            # Truncate to avoid context window explosion
            return text[:10000]
        except Exception as e:
            return f"Error fetching url: {e}"

    registry.register(
        name="web.search",
        category="web",
        description="Search the web using DuckDuckGo for information.",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        },
        func=web_search
    )
    
    registry.register(
        name="web.fetch",
        category="web",
        description="Fetch a URL and extract text content.",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"]
        },
        func=web_fetch
    )
