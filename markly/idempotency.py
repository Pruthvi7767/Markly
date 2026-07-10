"""Idempotency layer — prevents duplicate side-effects on crash-retry.

Per AGENTS.md Section 6:
- Idempotency keys on every side-effecting action.
- A retry must never duplicate a side effect.

Usage in executor.py:
    key = make_key(run_id, tool_name, tool_args)
    cached = check_key(key)
    if cached is not None:
        return cached          # replay — safe to return
    result = func(args)
    record_key(key, run_id, tool_name, tool_args, result)
"""
import hashlib
import json
import logging
import os

from sqlalchemy import text

from markly.db.session import get_engine

logger = logging.getLogger(__name__)

# Tiers that carry side effects and therefore need idempotency protection.
# read_only tools never mutate state, so they are excluded.
SIDE_EFFECTING_TIERS = {"safe", "write_local", "destructive"}


def make_key(run_id: str, tool_name: str, tool_args: dict) -> str:
    """Deterministic SHA-256 key: run_id + tool_name + sorted args."""
    raw = json.dumps(
        {"run_id": run_id, "tool": tool_name, "args": tool_args}, sort_keys=True
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def check_key(key: str) -> str | None:
    """Return the previously stored result if key succeeded, else None.

    Returns None (not raises) if the DB is unavailable — callers must
    handle the None case by proceeding to execute.
    """
    if not os.environ.get("DATABASE_URL"):
        return None
    try:
        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT result FROM idempotency_keys WHERE key = :key"),
                {"key": key},
            ).fetchone()
        if row:
            logger.info("IDEMPOTENCY: cache hit key=%s — replaying result", key[:16])
            return row[0]
    except Exception as e:
        logger.error("IDEMPOTENCY: check_key failed (%s) — proceeding without cache", e)
    return None


def record_key(
    key: str,
    run_id: str,
    tool_name: str,
    tool_args: dict,
    result: str,
) -> None:
    """Persist a successful result so future retries can replay it.

    Failure here is logged loudly but does NOT abort the run — the
    action already succeeded; losing the idempotency record is a
    degraded-safety situation, not a fatal one.
    """
    if not os.environ.get("DATABASE_URL"):
        return
    try:
        with get_engine().connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO idempotency_keys (key, run_id, tool_name, tool_args, result)
                    VALUES (:key, :run_id, :tool_name, CAST(:tool_args AS jsonb), :result)
                    ON CONFLICT (key) DO NOTHING
                """),
                {
                    "key": key,
                    "run_id": run_id,
                    "tool_name": tool_name,
                    "tool_args": json.dumps(tool_args),
                    "result": result[:4000],  # guard against huge blobs
                },
            )
            conn.commit()
        logger.debug("IDEMPOTENCY: recorded key=%s tool=%s", key[:16], tool_name)
    except Exception as e:
        logger.error(
            "IDEMPOTENCY: record_key FAILED for key=%s tool=%s — "
            "this action is NOT idempotency-protected. Error: %s",
            key[:16], tool_name, e,
        )
