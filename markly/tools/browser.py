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
