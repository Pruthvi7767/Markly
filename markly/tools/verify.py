"""Deterministic verification tool — Phase 11.

- verify.check_output: standalone deterministic-check tool.
"""
import logging
import requests
from typing import Dict, Any
from markly.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

def get_sandbox():
    from markly.engine import get_current_sandbox
    return get_current_sandbox()

def check_output(args: Dict[str, Any]) -> str:
    check_type = args.get("check_type")
    check_args = args.get("args") or {}
    if not check_type:
        return "Error: missing 'check_type'"
        
    sb = get_sandbox()
    
    passed = False
    detail = ""
    
    try:
        if check_type == "file_exists":
            path = check_args.get("path")
            if not path:
                return "Error: missing 'path' in check args"
            # run [ -e path ] inside container
            code, out = sb.execute(f"[ -e {shlex_quote_if_needed(path)} ]")
            passed = (code == 0)
            detail = f"File {path} {'exists' if passed else 'does not exist'} in sandbox."
            
        elif check_type == "url_reachable":
            url = check_args.get("url")
            if not url:
                return "Error: missing 'url' in check args"
            # Try to fetch URL from the host first
            try:
                resp = requests.head(url, timeout=5)
                passed = resp.status_code < 400
                detail = f"URL {url} reachable, status code: {resp.status_code}"
            except Exception as e:
                # Try curl in the container
                code, out = sb.execute(f"curl -s -I -o /dev/null -w '%{{http_code}}' {shlex_quote_if_needed(url)}")
                if code == 0 and out.strip().isdigit() and int(out.strip()) < 400:
                    passed = True
                    detail = f"URL {url} reachable inside container, status code: {out.strip()}"
                else:
                    passed = False
                    detail = f"URL {url} unreachable. Error/Status: {out.strip() or str(e)}"
                    
        elif check_type == "process_running":
            pattern = check_args.get("pattern")
            if not pattern:
                return "Error: missing 'pattern' in check args"
            # Check container processes
            code, out = sb.execute(f"ps aux | grep {shlex_quote_if_needed(pattern)} | grep -v grep")
            passed = (code == 0 and bool(out.strip()))
            detail = f"Process pattern '{pattern}' {'is running' if passed else 'is NOT running'} inside container. Output:\n{out}"
            
        elif check_type == "exit_code":
            command = check_args.get("command")
            expected = int(check_args.get("expected", 0))
            if not command:
                return "Error: missing 'command' in check args"
            code, out = sb.execute(command)
            passed = (code == expected)
            detail = f"Command exit code: {code} (expected {expected}). Output:\n{out}"
            
        elif check_type == "dom_element_present":
            url = check_args.get("url")
            selector = check_args.get("selector")
            text_contains = check_args.get("text_contains")
            if not url or not selector:
                return "Error: missing 'url' or 'selector' in check args"
                
            # Run a small Playwright check inside the container
            script = f"""
import sys
import subprocess
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "playwright"])
    subprocess.run(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto({repr(url)}, timeout=10000)
        el = page.query_selector({repr(selector)})
        if el is None:
            print("Element NOT found")
            sys.exit(1)
        if {repr(text_contains)}:
            inner = el.inner_text() or ""
            if {repr(text_contains)}.lower() not in inner.lower():
                print(f"Text check failed. Content: {{inner}}")
                sys.exit(2)
        print("Element found")
        sys.exit(0)
except Exception as e:
    print(f"Error checking DOM: {{e}}")
    sys.exit(3)
"""
            sb.write_file(".tmp_dom_check.py", script)
            code, out = sb.execute("python .tmp_dom_check.py")
            sb.execute("rm -f .tmp_dom_check.py")
            passed = (code == 0)
            detail = f"DOM Check result: {'PASS' if passed else 'FAIL'}. Log: {out.strip()}"

        elif check_type == "url_contains":
            url = check_args.get("url")
            expected = check_args.get("expected", "")
            if not url:
                return "Error: missing 'url' in check args"
            script = f"""
import sys
import subprocess
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "playwright"])
    subprocess.run(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto({repr(url)}, timeout=10000)
        final_url = page.url
        if {repr(expected)}.lower() in final_url.lower():
            sys.exit(0)
        else:
            print(f"Final URL: {{final_url}} does not contain {{repr(expected)}}")
            sys.exit(1)
except Exception as e:
    print(f"Error checking URL: {{e}}")
    sys.exit(2)
"""
            sb.write_file(".tmp_url_check.py", script)
            code, out = sb.execute("python .tmp_url_check.py")
            sb.execute("rm -f .tmp_url_check.py")
            passed = (code == 0)
            detail = f"URL Contains result: {'PASS' if passed else 'FAIL'}. Log: {out.strip()}"

        elif check_type == "no_console_errors":
            url = check_args.get("url")
            if not url:
                return "Error: missing 'url' in check args"
            script = f"""
import sys
import subprocess
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "playwright"])
    subprocess.run(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(err.message))
        page.goto({repr(url)}, timeout=10000)
        if errors:
            print(f"Console errors: {{errors}}")
            sys.exit(1)
        sys.exit(0)
except Exception as e:
    sys.exit(2)
"""
            sb.write_file(".tmp_console_check.py", script)
            code, out = sb.execute("python .tmp_console_check.py")
            sb.execute("rm -f .tmp_console_check.py")
            passed = (code == 0)
            detail = f"No Console Errors result: {'PASS' if passed else 'FAIL'}. Log: {out.strip()}"

        elif check_type == "click_then_text":
            url = check_args.get("url")
            click_selector = check_args.get("click_selector")
            text_selector = check_args.get("text_selector", "body")
            expected_text = check_args.get("expected_text", "")
            if not url or not click_selector:
                return "Error: missing 'url' or 'click_selector' in check args"
            script = f"""
import sys
import subprocess
import time
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "playwright"])
    subprocess.run(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto({repr(url)}, timeout=10000)
        page.click({repr(click_selector)}, timeout=5000)
        time.sleep(0.5)
        el = page.query_selector({repr(text_selector)})
        content = el.inner_text() if el else ""
        if {repr(expected_text)}.lower() in content.lower():
            sys.exit(0)
        else:
            print(f"Content: {{content}} did not contain {{repr(expected_text)}}")
            sys.exit(1)
except Exception as e:
    print(f"Error checking click_then_text: {{e}}")
    sys.exit(2)
"""
            sb.write_file(".tmp_click_check.py", script)
            code, out = sb.execute("python .tmp_click_check.py")
            sb.execute("rm -f .tmp_click_check.py")
            passed = (code == 0)
            detail = f"Click then Text result: {'PASS' if passed else 'FAIL'}. Log: {out.strip()}"

        else:
            return f"Error: Unknown check type '{check_type}'."
            
    except Exception as e:
        passed = False
        detail = f"Error running verification check: {e}"

    res = {
        "passed": passed,
        "detail": detail
    }
    import json
    return json.dumps(res)

def shlex_quote_if_needed(s: str) -> str:
    import shlex
    return shlex.quote(s)

def register_verify_tools(registry: ToolRegistry):
    registry.register(
        name="verify.check_output",
        category="verify",
        description="Verify output/state using a deterministic non-LLM check (e.g. file_exists, url_reachable, process_running, exit_code, dom_element_present).",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "check_type": {
                    "type": "string",
                    "enum": ["file_exists", "url_reachable", "process_running", "exit_code", "dom_element_present"],
                    "description": "The type of check to perform."
                },
                "args": {
                    "type": "object",
                    "description": "Arguments dictionary for the check. file_exists needs {'path'}; url_reachable needs {'url'}; process_running needs {'pattern'}; exit_code needs {'command', 'expected' (optional)}; dom_element_present needs {'url', 'selector', 'text_contains' (optional)}."
                }
            },
            "required": ["check_type", "args"]
        },
        func=check_output
    )
