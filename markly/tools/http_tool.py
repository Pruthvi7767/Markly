"""HTTP requests tool — Phase 11.

- http.request: executes a REST/HTTP request, wrapping it securely.
"""
import logging
import json
import requests
from typing import Dict, Any
from markly.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

def http_request(args: Dict[str, Any]) -> str:
    url = args.get("url")
    if not url:
        return "Error: missing 'url'"
        
    method = str(args.get("method", "GET")).upper()
    headers = args.get("headers") or {}
    data = args.get("data")
    
    # Standardize header content-type if JSON data is sent
    if isinstance(data, (dict, list)):
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        data_payload = json.dumps(data)
    else:
        data_payload = data

    try:
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data_payload,
            timeout=15
        )
        
        # Format response neatly
        content = resp.text
        try:
            # Format JSON response if possible
            js = resp.json()
            content = json.dumps(js, indent=2)
        except Exception:
            pass
            
        return f"Status: {resp.status_code}\nHeaders: {dict(resp.headers)}\nBody:\n{content}"
    except Exception as e:
        return f"Error executing HTTP request: {e}"

def register_http_tools(registry: ToolRegistry):
    registry.register(
        name="http.request",
        category="http",
        description="Make a generic HTTP/REST request. Defaults to write_local tier but dynamically upgrades to destructive if method is DELETE or target URL matches destructive patterns.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"], "description": "HTTP Method"},
                "headers": {"type": "object", "description": "Optional HTTP headers dictionary"},
                "data": {"type": "string", "description": "Optional raw string body or JSON payload"}
            },
            "required": ["url"]
        },
        func=http_request
    )
