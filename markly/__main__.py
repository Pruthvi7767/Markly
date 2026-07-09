"""Markly entry point.

Usage:
    python -m markly "Your goal here"
    python -m markly  (reads MARKLY_GOAL env var)
"""
import logging
import os
import sys
import tomllib
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("markly")


def _load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.toml not found at {cfg_path}")
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def main() -> None:
    # ── Goal ─────────────────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    else:
        goal = os.environ.get("MARKLY_GOAL", "").strip()

    if not goal:
        print("Usage: python -m markly \"Your goal here\"")
        print("   or: set MARKLY_GOAL=... and run python -m markly")
        sys.exit(1)

    cfg = _load_config()

    # ── Resume check ─────────────────────────────────────────────────────────
    from markly.checkpoint import load_stale_run
    state = load_stale_run()

    if state:
        print(f"\n♻️  Resuming stale run: {state['run_id']}")
        print(f"   Goal: {state['goal']}")
        print(f"   Turn: {state['turn_count']} | Subgoal: {state['subgoal_index']}")
    else:
        from markly.state import initial_state
        run_id = str(uuid.uuid4())
        state  = initial_state(run_id, goal, cfg)
        print(f"\n🚀 Starting new run: {run_id}")
        print(f"   Goal: {goal}\n")

    # ── Run ───────────────────────────────────────────────────────────────────
    from markly.engine import GRAPH

    try:
        final_state = GRAPH.invoke(state)
        exit_code   = 0 if final_state.get("status") == "completed" else 1
    except Exception as e:
        logger.error("FATAL: unhandled exception in graph: %s", e, exc_info=True)
        print(f"\n💥 FATAL ERROR: {e}")
        print("   Run was NOT marked complete. Check logs and Postgres for state.")
        exit_code = 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
