"""UI verification layer.

For every task with ui_assertions, boots a local HTTP server, navigates
Playwright to it, and runs deterministic browser checks.  Only falls back
to a Verifier LLM call for explicitly subjective assertions.

Failed assertions route back through the Critic→retry path (same caps).
"""
from __future__ import annotations
import logging
import socketserver
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Portable free-port finder ─────────────────────────────────────────────

def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── Tiny static HTTP server (stdlib only) ────────────────────────────────

class _SilentHandler(socketserver.StreamRequestHandler):
    """HTTP/1.0 handler that serves static files without log noise."""
    def handle(self):
        import http.server
        import os
        try:
            line = self.rfile.readline().decode("latin-1").strip()
            if not line:
                return
            parts = line.split()
            if len(parts) < 2:
                return
            path = parts[1].lstrip("/") or "index.html"
            full = self.server.base_dir / path
            if not full.exists():
                self.wfile.write(b"HTTP/1.0 404 Not Found\r\n\r\n")
                return
            data = full.read_bytes()
            ext = full.suffix.lower()
            mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(ext, "application/octet-stream")
            self.wfile.write(f"HTTP/1.0 200 OK\r\nContent-Type: {mime}\r\nContent-Length: {len(data)}\r\n\r\n".encode())
            self.wfile.write(data)
        except Exception:
            pass


class _StaticServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, port: int, base_dir: Path):
        self.base_dir = base_dir
        super().__init__(("127.0.0.1", port), _SilentHandler)


def _start_server(port: int, base_dir: Path) -> _StaticServer:
    server = _StaticServer(port, base_dir)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)  # brief settle
    return server


# ── Assertion runner ──────────────────────────────────────────────────────

def run_ui_assertions(
    task_dir: Path,
    assertions: list[dict],
    task_id: str,
    screenshot_path: Path | None = None,
) -> tuple[list[dict], str | None]:
    """
    Run browser assertions against a static HTML file served locally.

    Returns:
        (results, screenshot_path_str_or_None)
        results: list of {"assertion": dict, "passed": bool, "detail": str}
    """
    if not assertions:
        return [], None

    port = _free_port()
    server = _start_server(port, task_dir)
    base_url = f"http://127.0.0.1:{port}"

    results: list[dict] = []
    screenshot_taken: str | None = None

    try:
        from playwright.sync_api import sync_playwright
        from markly.tools.verify import check_output
        import json

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{base_url}/index.html", timeout=10000)

            for assertion in assertions:
                atype = assertion.get("type")
                passed = False
                detail = ""

                try:
                    if atype == "element_exists":
                        sel = assertion["selector"]
                        res_json = check_output({
                            "check_type": "dom_element_present",
                            "args": {"url": f"{base_url}/index.html", "selector": sel}
                        })
                        res = json.loads(res_json)
                        passed = res.get("passed", False)
                        detail = res.get("detail", "")

                    elif atype == "text_contains":
                        sel = assertion["selector"]
                        expected = assertion.get("text", "")
                        res_json = check_output({
                            "check_type": "dom_element_present",
                            "args": {"url": f"{base_url}/index.html", "selector": sel, "text_contains": expected}
                        })
                        res = json.loads(res_json)
                        passed = res.get("passed", False)
                        detail = res.get("detail", "")

                    elif atype == "url_contains":
                        expected = assertion.get("text", "")
                        res_json = check_output({
                            "check_type": "url_contains",
                            "args": {"url": f"{base_url}/index.html", "expected": expected}
                        })
                        res = json.loads(res_json)
                        passed = res.get("passed", False)
                        detail = res.get("detail", "")

                    elif atype == "no_console_errors":
                        res_json = check_output({
                            "check_type": "no_console_errors",
                            "args": {"url": f"{base_url}/index.html"}
                        })
                        res = json.loads(res_json)
                        passed = res.get("passed", False)
                        detail = res.get("detail", "")

                    elif atype == "click_then_text":
                        click_sel = assertion["click_selector"]
                        text_sel = assertion.get("text_selector", "body")
                        expected = assertion.get("expected_text", "")
                        res_json = check_output({
                            "check_type": "click_then_text",
                            "args": {
                                "url": f"{base_url}/index.html",
                                "click_selector": click_sel,
                                "text_selector": text_sel,
                                "expected_text": expected
                            }
                        })
                        res = json.loads(res_json)
                        passed = res.get("passed", False)
                        detail = res.get("detail", "")

                    else:
                        detail = f"Unknown assertion type: {atype}"
                        passed = False

                except Exception as e:
                    passed = False
                    detail = f"Error running assertion: {e}"

                logger.info(
                    "UI_VERIFY [%s] %s → %s | %s",
                    task_id, atype, "PASS" if passed else "FAIL", detail
                )
                results.append({"assertion": assertion, "passed": passed, "detail": detail})

            # Screenshot after all checks
            if screenshot_path:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path))
                screenshot_taken = str(screenshot_path)
                logger.info("UI_VERIFY screenshot saved: %s", screenshot_taken)

            browser.close()

    except Exception as e:
        logger.error("UI verification failed: %s", e)
    finally:
        server.shutdown()

    return results, screenshot_taken
