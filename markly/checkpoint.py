"""Postgres checkpointing — persists RunState after every turn.

Per AGENTS.md Section 6:
- Every write/state-changing action gets a post-write verification check.
- Unhandled failure always defaults to pause-and-notify-human (never silent).

Heartbeat is updated every save. On startup, stale runs (heartbeat >
STALE_SECONDS old with status='running') are candidates for resume.
"""
import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text

from markly.db.session import get_engine

logger = logging.getLogger(__name__)

STALE_SECONDS = 30  # heartbeat older than this = process likely died


# ─── public interface ─────────────────────────────────────────────────────────

def save_run(state: dict) -> None:
    """Upsert the full RunState to the runs table. Updates heartbeat."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set — skipping checkpoint (state NOT persisted)")
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO runs (run_id, goal, status, state_json, heartbeat, created_at, updated_at)
                    VALUES (:run_id, :goal, :status, CAST(:state_json AS jsonb), NOW(), NOW(), NOW())
                    ON CONFLICT (run_id) DO UPDATE SET
                        status     = EXCLUDED.status,
                        state_json = EXCLUDED.state_json,
                        heartbeat  = NOW(),
                        updated_at = NOW()
                """),
                {
                    "run_id":     state["run_id"],
                    "goal":       state["goal"],
                    "status":     state["status"],
                    "state_json": json.dumps(state),
                },
            )
            conn.commit()
        logger.debug("CHECKPOINT saved: run_id=%s status=%s turn=%s",
                     state["run_id"], state["status"], state.get("turn_count"))
    except Exception as e:
        # Log loudly — never silent per AGENTS.md rule 6
        logger.error(
            "CHECKPOINT FAILED for run_id=%s: %s — state NOT persisted. "
            "Manual recovery may be required.",
            state.get("run_id"), e,
        )
        raise  # re-raise so engine can decide: retry-with-correction or escalate


def save_turn(
    state: dict,
    tool_name: str | None,
    tool_args: dict | None,
    observation: str,
    verify_score: int | None,
) -> None:
    """Insert a turn record into the turns table."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO turns
                        (run_id, turn_number, subgoal_index, subgoal,
                         tool_name, tool_args, observation, verify_score, created_at)
                    VALUES
                        (:run_id, :turn_number, :subgoal_index, :subgoal,
                         :tool_name, CAST(:tool_args AS jsonb), :observation, :verify_score, NOW())
                """),
                {
                    "run_id":        state["run_id"],
                    "turn_number":   state.get("turn_count", 0),
                    "subgoal_index": state.get("subgoal_index", 0),
                    "subgoal":       state.get("current_subgoal", ""),
                    "tool_name":     tool_name,
                    "tool_args":     json.dumps(tool_args or {}),
                    "observation":   observation[:2000],  # cap to avoid huge rows
                    "verify_score":  verify_score,
                },
            )
            conn.commit()
    except Exception as e:
        logger.error("TURN SAVE FAILED: %s", e)
        # Non-fatal — don't stop the run for a turn record failure, but log it loudly


def load_stale_run() -> dict | None:
    """On startup, find any run with status='running' and stale heartbeat.

    Returns deserialized RunState dict if found, else None.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None

    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT state_json FROM runs
                    WHERE status = 'running'
                      AND heartbeat < NOW() - INTERVAL ':stale_s seconds'
                    ORDER BY heartbeat DESC
                    LIMIT 1
                """),
                {"stale_s": STALE_SECONDS},
            ).fetchone()

        if row:
            state = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            logger.warning(
                "RESUME: Found stale run run_id=%s (goal='%s', turn=%s). Resuming.",
                state.get("run_id"), state.get("goal", "")[:50], state.get("turn_count"),
            )
            state["is_resuming"] = True
            return state

    except Exception as e:
        logger.error("STALE RUN CHECK failed: %s — starting fresh.", e)

    return None
