"""Regression suite persistence.

After a UI task's assertions pass, serializes the checklist to
workspace/<task_id>/regression.json so future runs re-verify the same
invariants even after code changes.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

REGRESSION_FILENAME = "regression.json"


def save_regression(workspace: Path, task_id: str, assertions: list[dict]) -> Path:
    """Persist a passing assertion set as a permanent regression file."""
    task_dir = workspace / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    dest = task_dir / REGRESSION_FILENAME
    data = {
        "task_id": task_id,
        "assertions": assertions,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    dest.write_text(json.dumps(data, indent=2))
    logger.info("REGRESSION saved: %s", dest)
    return dest


def load_all_regressions(workspace: Path) -> list[dict]:
    """Load every regression.json found under workspace/."""
    suites: list[dict] = []
    for path in workspace.rglob(REGRESSION_FILENAME):
        try:
            data = json.loads(path.read_text())
            suites.append(data)
        except Exception as e:
            logger.warning("Could not load regression file %s: %s", path, e)
    return suites


def run_regression_suite(workspace: Path) -> dict[str, list[dict]]:
    """
    Re-run all accumulated regression assertions.

    Returns dict[task_id → list of assertion results].
    Empty dict if no regression files found.
    """
    from markly.eval.ui_verifier import run_ui_assertions

    suites = load_all_regressions(workspace)
    if not suites:
        logger.info("REGRESSION no suites found in %s", workspace)
        return {}

    all_results: dict[str, list[dict]] = {}
    for suite in suites:
        task_id = suite["task_id"]
        # Find the task output dir — convention: workspace/<task_output_dir>/index.html
        # For regression we look for any index.html under workspace that belongs to the task
        # by checking for the task_id directory or walking common candidates
        task_dir = _find_task_dir(workspace, task_id)
        if task_dir is None:
            logger.warning("REGRESSION: cannot find output dir for %s", task_id)
            continue

        results, _ = run_ui_assertions(
            task_dir=task_dir,
            assertions=suite["assertions"],
            task_id=task_id,
        )
        all_results[task_id] = results
        passed = sum(1 for r in results if r["passed"])
        logger.info(
            "REGRESSION [%s] %d/%d assertions passed",
            task_id, passed, len(results)
        )

    return all_results


# Task-id to output dir mapping (mirrors tasks.py conventions)
_TASK_OUTPUT_DIRS: dict[str, str] = {
    "T02": "app",
    "T08": "signup",
    "T09": "signup",
    "T10": "counter",
    "T15": "dashboard",
}

def _find_task_dir(workspace: Path, task_id: str) -> Path | None:
    sub = _TASK_OUTPUT_DIRS.get(task_id)
    if sub:
        d = workspace / sub
        return d if d.exists() else None
    return None
