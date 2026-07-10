"""Eval test runner — executes each task N times and collects statistics.

Per AGENTS.md §4: a phase is not done until real outputs are shown.
This module IS that enforcement: it runs tasks, checks success_fn, and
produces a structured report with real numbers.
"""
from __future__ import annotations
import json
import logging
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"


# ── Cap tracker ───────────────────────────────────────────────────────────

_CAP_NAMES = [
    "global_turns", "token_budget", "critic_retry",
    "consecutive_failures", "critic_invocations",
    "stagnation", "dedup",
]


def _extract_caps_from_logs(log_output: str) -> dict[str, int]:
    """Count CAP_FIRED log lines by cap name."""
    import re
    counts: dict[str, int] = {c: 0 for c in _CAP_NAMES}
    for match in re.finditer(r"CAP_FIRED cap=(\S+)", log_output):
        cap = match.group(1)
        counts[cap] = counts.get(cap, 0) + 1
    return counts


# ── Cost calculator ───────────────────────────────────────────────────────

def _load_pricing() -> dict[str, Any]:
    try:
        import tomllib
        p = Path(__file__).parent.parent.parent / "pricing.toml"
        if p.exists():
            with open(p, "rb") as f:
                return tomllib.load(f).get("models", {})
    except Exception:
        pass
    return {}


_PRICING = _load_pricing()


def _tokens_to_cost(tokens_used: int, role: str = "planner") -> float:
    """Estimate cost in USD. Falls back to $0 if pricing not configured."""
    for model_key, model_data in _PRICING.items():
        # Fallback heuristic if we don't have exact token splits: 
        # assume tokens are roughly 75% input, 25% output
        if "planner" in model_key.lower() or role in model_key.lower() or "llama" in model_key.lower():
            in_cost_m = model_data.get("input_cost_per_m", 0.0)
            out_cost_m = model_data.get("output_cost_per_m", 0.0)
            est_in = tokens_used * 0.75
            est_out = tokens_used * 0.25
            return (est_in / 1_000_000) * in_cost_m + (est_out / 1_000_000) * out_cost_m
    return 0.0


# ── Single task run ───────────────────────────────────────────────────────

def _run_once(task: dict, workspace: Path) -> dict:
    """Run a single task, return metrics dict."""
    import io
    from markly.engine import GRAPH
    from markly.state import initial_state
    from markly.checkpoint import get_run_config

    run_id = str(uuid.uuid4())[:8]
    cfg = get_run_config()

    state = initial_state(run_id=run_id, goal=task["goal"], cfg=cfg)

    # Capture logs for cap counting
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger("markly")
    root_logger.addHandler(handler)

    start_time = time.monotonic()
    status = "error"
    turns = 0
    tokens = 0

    try:
        final = GRAPH.invoke(state)
        status = final.get("status", "unknown")
        turns = final.get("turn_count", 0)
        tokens = final.get("tokens_used", 0)
    except Exception as e:
        logger.error("Task %s run %s crashed: %s", task["id"], run_id, e)
        status = "crashed"
    finally:
        root_logger.removeHandler(handler)

    elapsed = time.monotonic() - start_time
    log_text = log_capture.getvalue()

    # Check success
    try:
        success = task["success_fn"](workspace)
    except Exception as e:
        logger.warning("success_fn error for %s: %s", task["id"], e)
        success = False

    no_progress = status in ("escalated", "waiting_human_review", "crashed")
    caps = _extract_caps_from_logs(log_text)
    cost = _tokens_to_cost(tokens)

    return {
        "run_id": run_id,
        "success": success,
        "status": status,
        "turns": turns,
        "tokens": tokens,
        "cost_usd": cost,
        "elapsed_s": round(elapsed, 1),
        "no_progress": no_progress,
        "caps": caps,
    }


# ── UI verification step ──────────────────────────────────────────────────

def _run_ui_verification(task: dict, workspace: Path, task_run_dir: Path) -> dict:
    """Run browser assertions if task has ui_assertions."""
    from markly.eval.ui_verifier import run_ui_assertions
    from markly.eval.regression import save_regression

    assertions = task.get("ui_assertions", [])
    if not assertions:
        return {"ui_run": False}

    # Find the HTML dir for this task
    from markly.eval.regression import _find_task_dir
    task_dir = _find_task_dir(workspace, task["id"])
    if task_dir is None:
        return {"ui_run": False, "detail": "output dir not found"}

    screenshot_path = task_run_dir / f"ui_screenshot_{task['id']}.png"
    results, screenshot = run_ui_assertions(
        task_dir=task_dir,
        assertions=assertions,
        task_id=task["id"],
        screenshot_path=screenshot_path,
    )

    all_passed = all(r["passed"] for r in results)
    if all_passed:
        save_regression(workspace / "regressions", task["id"], assertions)

    return {
        "ui_run": True,
        "ui_passed": all_passed,
        "ui_results": results,
        "ui_screenshot": screenshot,
    }


# ── Multi-run task aggregation ────────────────────────────────────────────

def run_task(task: dict, n: int = 5, workspace: Path = WORKSPACE_DIR) -> dict:
    """Run a task N times and return aggregated stats."""
    logger.info("EVAL_TASK %s: starting %d runs", task["id"], n)
    runs: list[dict] = []
    ui_result: dict = {}

    for i in range(n):
        logger.info("EVAL_TASK %s: run %d/%d", task["id"], i + 1, n)
        r = _run_once(task, workspace)
        runs.append(r)

        # Run UI verification only on first successful run (one real check is enough)
        if r["success"] and task.get("ui_assertions") and not ui_result:
            task_run_dir = workspace / "eval_runs" / task["id"]
            task_run_dir.mkdir(parents=True, exist_ok=True)
            ui_result = _run_ui_verification(task, workspace, task_run_dir)

    successes = [r for r in runs if r["success"]]
    success_rate = len(successes) / n
    no_progress_rate = sum(1 for r in runs if r["no_progress"]) / n
    turns_list = [r["turns"] for r in runs]
    median_turns = statistics.median(turns_list) if turns_list else 0
    total_cost = sum(r["cost_usd"] for r in runs)
    total_tokens = sum(r["tokens"] for r in runs)

    # Aggregate cap counts
    agg_caps: dict[str, int] = {}
    for r in runs:
        for cap, count in r["caps"].items():
            agg_caps[cap] = agg_caps.get(cap, 0) + count

    result = {
        "task_id": task["id"],
        "category": task["category"],
        "n": n,
        "success_rate": round(success_rate, 2),
        "no_progress_rate": round(no_progress_rate, 2),
        "median_turns": median_turns,
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "cap_counts": agg_caps,
        "runs": runs,
    }
    if ui_result:
        result["ui_verification"] = ui_result

    logger.info(
        "EVAL_TASK %s done: success_rate=%.0f%% median_turns=%s cost=$%.4f",
        task["id"], success_rate * 100, median_turns, total_cost
    )
    return result


# ── Full suite runner ─────────────────────────────────────────────────────

def run_suite(
    task_ids: list[str] | None = None,
    n: int = 5,
    workspace: Path = WORKSPACE_DIR,
    report_path: Path | None = None,
) -> dict:
    """Run the full eval suite and return aggregate results + write report."""
    from markly.eval.tasks import TASKS, FAST_TASKS
    from markly.eval.regression import run_regression_suite

    if task_ids:
        tasks = [t for t in TASKS if t["id"] in task_ids]
    else:
        tasks = TASKS

    if not tasks:
        raise ValueError(f"No tasks matched IDs: {task_ids}")

    logger.info("EVAL_SUITE: running %d tasks × %d reps each", len(tasks), n)

    task_results: list[dict] = []
    for task in tasks:
        result = run_task(task, n=n, workspace=workspace)
        task_results.append(result)

    # Re-run accumulated regression suites
    regression_results = run_regression_suite(workspace / "regressions")

    # Aggregate across all tasks
    all_caps: dict[str, int] = {}
    for r in task_results:
        for cap, count in r["cap_counts"].items():
            all_caps[cap] = all_caps.get(cap, 0) + count

    suite_summary = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "n_tasks": len(tasks),
        "n_reps": n,
        "aggregate": {
            "overall_success_rate": round(
                sum(r["success_rate"] for r in task_results) / len(task_results), 2
            ),
            "total_cost_usd": round(sum(r["total_cost_usd"] for r in task_results), 4),
            "total_tokens": sum(r["total_tokens"] for r in task_results),
            "cap_counts": all_caps,
        },
        "by_category": _aggregate_by_category(task_results),
        "tasks": task_results,
        "regression_results": {
            tid: [{"assertion": r["assertion"], "passed": r["passed"]} for r in results]
            for tid, results in regression_results.items()
        },
    }

    # Write JSON
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        json_path = report_path.with_suffix(".json")
        json_path.write_text(json.dumps(suite_summary, indent=2, default=str))
        md = _render_markdown_report(suite_summary)
        report_path.write_text(md)
        logger.info("EVAL_SUITE report written to %s", report_path)

    return suite_summary


def _aggregate_by_category(task_results: list[dict]) -> dict[str, dict]:
    cats: dict[str, list] = {}
    for r in task_results:
        cats.setdefault(r["category"], []).append(r)
    out = {}
    for cat, items in cats.items():
        out[cat] = {
            "count": len(items),
            "success_rate": round(sum(i["success_rate"] for i in items) / len(items), 2),
        }
    return out


def _render_markdown_report(s: dict) -> str:
    agg = s["aggregate"]
    lines = [
        f"# Markly Eval Report",
        f"",
        f"**Generated:** {s['timestamp']}",
        f"**Tasks:** {s['n_tasks']}  **Reps each:** {s['n_reps']}",
        f"",
        f"## Aggregate",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Overall success rate | {agg['overall_success_rate']*100:.0f}% |",
        f"| Total cost (USD) | ${agg['total_cost_usd']:.4f} |",
        f"| Total tokens | {agg['total_tokens']:,} |",
        f"",
        f"### Cap Triggers (aggregated)",
        f"| Cap | Fires |",
        f"|-----|-------|",
    ]
    for cap, count in sorted(agg["cap_counts"].items()):
        if count > 0:
            lines.append(f"| {cap} | {count} |")

    lines += [
        f"",
        f"## By Category",
        f"| Category | Tasks | Success Rate |",
        f"|----------|-------|--------------|",
    ]
    for cat, data in s["by_category"].items():
        lines.append(f"| {cat} | {data['count']} | {data['success_rate']*100:.0f}% |")

    lines += [
        f"",
        f"## Per-Task Results",
        f"| ID | Category | Success | Median Turns | Cost |",
        f"|----|----------|---------|--------------|------|",
    ]
    for r in s["tasks"]:
        sr = f"{r['success_rate']*100:.0f}%"
        lines.append(
            f"| {r['task_id']} | {r['category']} | {sr} | {r['median_turns']} | ${r['total_cost_usd']:.4f} |"
        )

    # UI verification section
    ui_tasks = [r for r in s["tasks"] if "ui_verification" in r and r["ui_verification"].get("ui_run")]
    if ui_tasks:
        lines += [f"", f"## UI Verification Results"]
        for r in ui_tasks:
            ui = r["ui_verification"]
            passed_str = "✅ PASS" if ui.get("ui_passed") else "❌ FAIL"
            lines.append(f"", f"### {r['task_id']} — {passed_str}")
            for ur in ui.get("ui_results", []):
                icon = "✅" if ur["passed"] else "❌"
                lines.append(f"- {icon} `{ur['assertion']['type']}` — {ur['detail']}")
            if ui.get("ui_screenshot"):
                lines.append(f"- 📸 Screenshot: `{ui['ui_screenshot']}`")

    return "\n".join(lines) + "\n"
