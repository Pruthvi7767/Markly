from typing import Dict, Any
from markly.tools.registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)

# Lazy initialization for Playwright to avoid thread/event loop issues on import
_playwright = None
_browser = None
_page = None

def _get_page():
    global _playwright, _browser, _page
    if _page is None:
        from playwright.sync_api import sync_playwright
        logger.info("Starting Playwright browser...")
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        _page = _browser.new_page()
    return _page

def register_browser_tools(registry: ToolRegistry):
    
    def browser_navigate(args: Dict[str, Any]) -> str:
        url = args.get("url")
        if not url: return "Error: missing 'url'"
        page = _get_page()
        page.goto(url)
        return f"Navigated to {page.url}"

    def browser_extract(args: Dict[str, Any]) -> str:
        selector = args.get("selector", "body")
        page = _get_page()
        try:
            elements = page.query_selector_all(selector)
            if not elements: return f"No elements found for '{selector}'"
            texts = [el.inner_text() for el in elements[:10]]
            return "\n---\n".join(texts)
        except Exception as e:
            return f"Extract error: {e}"

    def browser_click(args: Dict[str, Any]) -> str:
        selector = args.get("selector")
        if not selector: return "Error: missing 'selector'"
        page = _get_page()
        try:
            page.click(selector, timeout=5000)
            return f"Clicked on {selector}"
        except Exception as e:
            return f"Click error: {e}"

    def browser_fill_form(args: Dict[str, Any]) -> str:
        selector = args.get("selector")
        value = args.get("value")
        if not selector or value is None: return "Error: missing 'selector' or 'value'"
        page = _get_page()
        try:
            page.fill(selector, value, timeout=5000)
            return f"Filled {selector} with value"
        except Exception as e:
            return f"Fill error: {e}"

    def browser_scroll(args: Dict[str, Any]) -> str:
        direction = args.get("direction", "down")
        page = _get_page()
        try:
            if direction == "down":
                page.mouse.wheel(0, 1000)
            else:
                page.mouse.wheel(0, -1000)
            return f"Scrolled {direction}"
        except Exception as e:
            return f"Scroll error: {e}"

    def browser_screenshot(args: Dict[str, Any]) -> str:
        from pathlib import Path
        import os
        path = args.get("path", "screenshot.png")
        page = _get_page()
        try:
            workspace_dir = Path(os.getcwd()) / "workspace"
            target = (workspace_dir / path).resolve()
            if not str(target).startswith(str(workspace_dir.resolve())):
                target = workspace_dir / Path(path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target))
            return f"Screenshot successfully saved to {path} in workspace."
        except Exception as e:
            return f"Screenshot error: {e}"

    def browser_download(args: Dict[str, Any]) -> str:
        from pathlib import Path
        import os
        selector = args.get("selector")
        path = args.get("path", "downloaded_file")
        page = _get_page()
        try:
            workspace_dir = Path(os.getcwd()) / "workspace"
            target = (workspace_dir / path).resolve()
            if not str(target).startswith(str(workspace_dir.resolve())):
                target = workspace_dir / Path(path).name
            target.parent.mkdir(parents=True, exist_ok=True)
            
            if selector:
                with page.expect_download() as download_info:
                    page.click(selector)
                download = download_info.value
                download.save_as(str(target))
                return f"File downloaded and saved to {path}"
            else:
                return "Error: missing 'selector' to trigger download."
        except Exception as e:
            return f"Download error: {e}"

    def browser_search(args: Dict[str, Any]) -> str:
        import urllib.parse
        query = args.get("query")
        if not query: return "Error: missing 'query'"
        page = _get_page()
        try:
            quoted = urllib.parse.quote(query)
            page.goto(f"https://html.duckduckgo.com/html/?q={quoted}")
            links = page.query_selector_all(".result__a")
            results = []
            for link in links[:5]:
                results.append(f"Title: {link.inner_text()}\nURL: {link.get_attribute('href')}\n")
            if not results:
                return "No search results found via browser."
            return "\n".join(results)
        except Exception as e:
            return f"Browser search error: {e}"

    registry.register(
        name="browser.navigate",
        category="browser",
        description="Navigate the browser to a URL.",
        tier="read_only",
        schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
        func=browser_navigate
    )
    
    registry.register(
        name="browser.extract",
        category="browser",
        description="Extract text from elements matching a CSS selector.",
        tier="read_only",
        schema={"type": "object", "properties": {"selector": {"type": "string"}}},
        func=browser_extract
    )
    
    registry.register(
        name="browser.click",
        category="browser",
        description="Click an element matching a CSS selector.",
        tier="write_local",
        schema={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
        func=browser_click
    )
    
    registry.register(
        name="browser.fill_form",
        category="browser",
        description="Fill a form input matching a CSS selector with a value.",
        tier="write_local",
        schema={"type": "object", "properties": {"selector": {"type": "string"}, "value": {"type": "string"}}, "required": ["selector", "value"]},
        func=browser_fill_form
    )
    
    registry.register(
        name="browser.scroll",
        category="browser",
        description="Scroll the page up or down.",
        tier="read_only",
        schema={"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]}}},
        func=browser_scroll
    )

    registry.register(
        name="browser.screenshot",
        category="browser",
        description="Take a screenshot of the current page and save it.",
        tier="write_local",
        schema={"type": "object", "properties": {"path": {"type": "string", "description": "Relative path where to save screenshot inside workspace"}}},
        func=browser_screenshot
    )

    registry.register(
        name="browser.download",
        category="browser",
        description="Click an element to trigger a download and save the file.",
        tier="write_local",
        schema={"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector for link/button to click"}, "path": {"type": "string", "description": "Relative path where to save the file inside workspace"}}, "required": ["selector"]},
        func=browser_download
    )

    registry.register(
        name="browser.search",
        category="browser",
        description="Search DuckDuckGo via browser and retrieve result list.",
        tier="read_only",
        schema={"type": "object", "properties": {"query": {"type": "string", "description": "The search query"}}, "required": ["query"]},
        func=browser_search
    )
