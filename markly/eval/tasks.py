"""Eval task catalog — 18 curated tasks across 4 categories.

Each task has:
  id          — short identifier (T01–T18)
  goal        — the string sent verbatim to the Markly agent
  category    — scaffold | fix | research | ui
  success_fn  — pure Python callable(workspace_dir: Path) -> bool
  ui_assertions (optional) — list of browser check dicts for UI tasks
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable


def _file_exists(workspace: Path, rel: str) -> bool:
    return (workspace / rel).exists()


def _file_contains(workspace: Path, rel: str, pattern: str) -> bool:
    p = workspace / rel
    if not p.exists():
        return False
    return bool(re.search(pattern, p.read_text(encoding="utf-8", errors="ignore"), re.IGNORECASE))


def _file_min_len(workspace: Path, rel: str, min_chars: int) -> bool:
    p = workspace / rel
    if not p.exists():
        return False
    return len(p.read_text(encoding="utf-8", errors="ignore").strip()) >= min_chars


def _script_runs(workspace: Path, rel: str, expected_stdout_pattern: str = "") -> bool:
    p = workspace / rel
    if not p.exists():
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(p)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False
        if expected_stdout_pattern:
            return bool(re.search(expected_stdout_pattern, result.stdout))
        return True
    except Exception:
        return False


def _json_has_keys(workspace: Path, rel: str, keys: list[str]) -> bool:
    p = workspace / rel
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return all(k in data for k in keys)
    except Exception:
        return False


def _html_contains_elements(workspace: Path, rel: str, selectors: list[str]) -> bool:
    """Quick regex check for HTML elements — no browser needed."""
    p = workspace / rel
    if not p.exists():
        return False
    html = p.read_text(encoding="utf-8", errors="ignore").lower()
    for sel in selectors:
        if sel.startswith("<"):
            if sel.lower() not in html:
                return False
        else:
            if sel.lower() not in html:
                return False
    return True


def _bullet_count(workspace: Path, rel: str, min_bullets: int) -> bool:
    p = workspace / rel
    if not p.exists():
        return False
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    bullets = [l for l in lines if l.strip().startswith(("-", "*", "•"))]
    return len(bullets) >= min_bullets


# ── Task definitions ───────────────────────────────────────────────────────

TASKS: list[dict] = [
    # ── scaffold ────────────────────────────────────────────────────────────
    {
        "id": "T01",
        "category": "scaffold",
        "goal": "Create a Python file at workspace/hello.py that prints exactly: Hello, Markly!",
        "success_fn": lambda ws: _script_runs(ws, "hello.py", r"Hello, Markly!"),
        "ui_assertions": [],
    },
    {
        "id": "T02",
        "category": "scaffold",
        "goal": "Create workspace/app/index.html with an <h1> tag containing the text 'Markly'",
        "success_fn": lambda ws: _html_contains_elements(ws, "app/index.html", ["<h1", "markly"]),
        "ui_assertions": [
            {"type": "element_exists", "selector": "h1"},
            {"type": "text_contains", "selector": "h1", "text": "Markly"},
        ],
    },
    {
        "id": "T11",
        "category": "scaffold",
        "goal": "Create workspace/fibonacci.py that prints the first 10 Fibonacci numbers separated by spaces on one line",
        "success_fn": lambda ws: _script_runs(ws, "fibonacci.py", r"0\s+1\s+1\s+2\s+3\s+5\s+8\s+13\s+21\s+34"),
        "ui_assertions": [],
    },
    {
        "id": "T14",
        "category": "scaffold",
        "goal": "Create workspace/config.json containing a JSON object with keys: name, version, debug",
        "success_fn": lambda ws: _json_has_keys(ws, "config.json", ["name", "version", "debug"]),
        "ui_assertions": [],
    },
    {
        "id": "T18",
        "category": "scaffold",
        "goal": "Write workspace/read_me.md with a short project description of Markly (at least 50 characters)",
        "success_fn": lambda ws: (
            _file_contains(ws, "read_me.md", r"markly") and
            _file_min_len(ws, "read_me.md", 50)
        ),
        "ui_assertions": [],
    },
    # ── fix ─────────────────────────────────────────────────────────────────
    {
        "id": "T03",
        "category": "fix",
        "goal": "The file workspace/broken.py has a syntax error. Fix it so the script runs without error and prints 'Fixed!'",
        "success_fn": lambda ws: _script_runs(ws, "broken.py", r"Fixed!"),
        "ui_assertions": [],
    },
    {
        "id": "T04",
        "category": "fix",
        "goal": "The file workspace/noop.py has a missing return statement. Fix it so calling double(5) returns 10. The file should print the result.",
        "success_fn": lambda ws: _script_runs(ws, "noop.py", r"10"),
        "ui_assertions": [],
    },
    {
        "id": "T12",
        "category": "fix",
        "goal": "The file workspace/loop_bug.py has an off-by-one error — it prints numbers 1-9 instead of 1-10. Fix it so it prints 1 through 10.",
        "success_fn": lambda ws: _script_runs(ws, "loop_bug.py", r"10"),
        "ui_assertions": [],
    },
    {
        "id": "T16",
        "category": "fix",
        "goal": "The file workspace/divide.py crashes with ZeroDivisionError. Fix it so it handles division by zero gracefully and prints 'Cannot divide by zero' instead of crashing.",
        "success_fn": lambda ws: _script_runs(ws, "divide.py", r"Cannot divide by zero"),
        "ui_assertions": [],
    },
    # ── research ────────────────────────────────────────────────────────────
    {
        "id": "T05",
        "category": "research",
        "goal": "Search the web for the current stable Python version number and write it to workspace/python_version.txt",
        "success_fn": lambda ws: (
            _file_exists(ws, "python_version.txt") and
            _file_min_len(ws, "python_version.txt", 3)
        ),
        "ui_assertions": [],
    },
    {
        "id": "T06",
        "category": "research",
        "goal": "Write a 3-sentence summary of what FastAPI is to workspace/fastapi_summary.txt",
        "success_fn": lambda ws: _file_min_len(ws, "fastapi_summary.txt", 100),
        "ui_assertions": [],
    },
    {
        "id": "T07",
        "category": "research",
        "goal": "Use the mcp.context7.query-docs tool with libraryId '/tiangolo/fastapi' to fetch the FastAPI path parameters documentation. Write a code example showing a FastAPI path parameter to workspace/fastapi_path_example.py",
        "success_fn": lambda ws: _file_contains(ws, "fastapi_path_example.py", r"@app\.(get|post|put)"),
        "ui_assertions": [],
    },
    {
        "id": "T13",
        "category": "research",
        "goal": "Read the file AGENTS.md at the root of the project and write a 5-bullet summary of its engineering principles to workspace/principles.md",
        "success_fn": lambda ws: _bullet_count(ws, "principles.md", 5),
        "ui_assertions": [],
    },
    {
        "id": "T17",
        "category": "research",
        "goal": "Search the web for Groq API rate limits and write what you find to workspace/groq_limits.txt",
        "success_fn": lambda ws: _file_min_len(ws, "groq_limits.txt", 50),
        "ui_assertions": [],
    },
    # ── ui ──────────────────────────────────────────────────────────────────
    {
        "id": "T08",
        "category": "ui",
        "goal": "Build workspace/signup/index.html with a signup form containing: an email input, a password input, and a submit button",
        "success_fn": lambda ws: _html_contains_elements(
            ws, "signup/index.html",
            ["input", "email", "password", "submit"]
        ),
        "ui_assertions": [
            {"type": "element_exists", "selector": "input[type=email], input[name=email]"},
            {"type": "element_exists", "selector": "input[type=password]"},
            {"type": "element_exists", "selector": "button[type=submit], input[type=submit]"},
        ],
    },
    {
        "id": "T09",
        "category": "ui",
        "goal": "Add a navigation bar to workspace/signup/index.html with links labeled 'Home' and 'About'",
        "success_fn": lambda ws: _html_contains_elements(ws, "signup/index.html", ["home", "about"]),
        "ui_assertions": [
            {"type": "text_contains", "selector": "a", "text": "Home"},
            {"type": "text_contains", "selector": "a", "text": "About"},
        ],
    },
    {
        "id": "T10",
        "category": "ui",
        "goal": "Build workspace/counter/index.html with a button that increments a displayed counter number when clicked (use JavaScript)",
        "success_fn": lambda ws: _html_contains_elements(ws, "counter/index.html", ["<button", "onclick", "counter"]),
        "ui_assertions": [
            {"type": "element_exists", "selector": "button"},
            {"type": "element_exists", "selector": "#counter, .counter, [id*=count], [class*=count]"},
        ],
    },
    {
        "id": "T15",
        "category": "ui",
        "goal": "Build workspace/dashboard/index.html with a submit button that shows a 'Success!' message when clicked (using JavaScript onclick or event listener)",
        "success_fn": lambda ws: _html_contains_elements(ws, "dashboard/index.html", ["<button", "success"]),
        "ui_assertions": [
            {"type": "element_exists", "selector": "button"},
            {"type": "click_then_text", "click_selector": "button", "text_selector": "body", "expected_text": "Success"},
        ],
    },
]

# Fast subset for CI (N=1) — covers all 4 categories
FAST_TASKS = ["T01", "T06", "T03", "T08", "T07"]
