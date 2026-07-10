"""Outer scheduler daemon — Phase 11.

Watches the runs table for pending runs, manages execution retries with backoff,
and triggers recurring cron schedules.
"""
import time
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from markly.db.session import get_engine
from markly.state import initial_state, RunState
from markly.checkpoint import save_run
from markly.tools.notify_tools import notify_human

logger = logging.getLogger(__name__)

# ── Pure Python Cron Matcher ──────────────────────────────────────────────

def match_cron_field(field: str, value: int) -> bool:
    if field == "*":
        return True
    if "/" in field:
        base, step = field.split("/")
        step = int(step)
        if base == "*":
            return value % step == 0
        return (value - int(base)) % step == 0
    if "," in field:
        return any(match_cron_field(sub, value) for sub in field.split(","))
    if "-" in field:
        start, end = field.split("-")
        return int(start) <= value <= int(end)
    return int(field) == value

def is_cron_match(cron_expr: str, dt: datetime) -> bool:
    fields = cron_expr.split()
    if len(fields) != 5:
        return False
    minute, hour, day, month, dow = fields
    return (
        match_cron_field(minute, dt.minute) and
        match_cron_field(hour, dt.hour) and
        match_cron_field(day, dt.day) and
        match_cron_field(month, dt.month) and
        match_cron_field(dow, dt.weekday())
    )

def calculate_next_run(cron_expr: str, start_dt: datetime) -> datetime:
    """Find the next minute matching the cron expression."""
    current = start_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Limit search to 1 year to prevent infinite loops on bad crons
    limit = current + timedelta(days=365)
    while current < limit:
        if is_cron_match(cron_expr, current):
            return current
        current += timedelta(minutes=1)
    return start_dt + timedelta(minutes=5)

# ── Scheduler Core Poller ──────────────────────────────────────────────────

def poll_and_execute_schedules():
    """Poll schedules table and spawn pending runs."""
    engine = get_engine()
    now = datetime.now(timezone.utc)
    
    try:
        with engine.connect() as conn:
            # 1. Fetch active schedules that are due
            rows = conn.execute(
                text("""
                    SELECT schedule_id, cron_expression, goal, next_run_at 
                    FROM schedules 
                    WHERE active = TRUE AND (next_run_at IS NULL OR next_run_at <= :now)
                """),
                {"now": now}
            ).fetchall()
            
            for sched_id, cron_expr, goal, next_run in rows:
                logger.info("SCHEDULER: Triggering recurring schedule %s ('%s')", sched_id, goal[:40])
                
                # Spawn a new pending run
                run_id = str(uuid.uuid4())
                from markly.cli import _load_config
                cfg = _load_config()
                state = initial_state(run_id, goal, cfg)
                state["status"] = "pending"
                state["parent_schedule_id"] = sched_id
                state["retry_count"] = 0
                
                # Insert run
                conn.execute(
                    text("""
                        INSERT INTO runs (run_id, goal, status, state_json, heartbeat, created_at, updated_at)
                        VALUES (:run_id, :goal, 'pending', CAST(:state_json AS jsonb), NOW(), NOW(), NOW())
                    """),
                    {
                        "run_id": run_id,
                        "goal": goal,
                        "state_json": json.dumps(state)
                    }
                )
                
                # Update next run time
                next_dt = calculate_next_run(cron_expr, now)
                conn.execute(
                    text("UPDATE schedules SET next_run_at = :next, updated_at = NOW() WHERE schedule_id = :id"),
                    {"next": next_dt, "id": sched_id}
                )
                conn.commit()
                logger.info("SCHEDULER: Scheduled next execution for %s at %s", sched_id, next_dt)
                
    except Exception as e:
        logger.error("SCHEDULER: schedules polling failed: %s", e)

def poll_and_execute_runs():
    """Poll pending runs, execute them, and apply retry/dead-letter logic."""
    engine = get_engine()
    from markly.engine import GRAPH
    
    try:
        with engine.connect() as conn:
            # Fetch one pending run
            row = conn.execute(
                text("SELECT run_id, goal, state_json FROM runs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1")
            ).fetchone()
            
            if not row:
                return
                
            run_id, goal, state_json = row
            state = state_json if isinstance(state_json, dict) else json.loads(state_json)
            
            # Set to running
            state["status"] = "running"
            conn.execute(
                text("UPDATE runs SET status = 'running', heartbeat = NOW() WHERE run_id = :id"),
                {"id": run_id}
            )
            conn.commit()
            
        logger.info("SCHEDULER: Executing pending run %s...", run_id)
        
        # Execute the Graph harness
        try:
            final_state = GRAPH.invoke(state)
            status = final_state.get("status", "completed")
        except Exception as e:
            logger.error("SCHEDULER: Run %s execution crashed: %s", run_id, e)
            status = "failed"
            final_state = state
            final_state["status"] = "failed"
            final_state["escalate_reason"] = f"Scheduler execution crash: {e}"
            
        # Update run status
        with engine.connect() as conn:
            if status == "completed":
                logger.info("SCHEDULER: Run %s succeeded!", run_id)
                # Successful run notification
                notify_human({"message": f"Markly execution succeeded for Run {run_id[:8]}: {goal[:50]}"})
            else:
                # Failure / Escalation: Apply retry policy
                retry_count = final_state.get("retry_count", 0)
                max_retries = 3
                
                if retry_count < max_retries:
                    retry_count += 1
                    final_state["retry_count"] = retry_count
                    final_state["status"] = "pending"
                    final_state["route"] = "decompose"
                    final_state["is_resuming"] = False
                    
                    conn.execute(
                        text("""
                            UPDATE runs 
                            SET status = 'pending', state_json = CAST(:state_json AS jsonb), updated_at = NOW() 
                            WHERE run_id = :id
                        """),
                        {
                            "state_json": json.dumps(final_state),
                            "id": run_id
                        }
                    )
                    conn.commit()
                    logger.warning("SCHEDULER: Run %s failed. Retrying (%d/%d)...", run_id, retry_count, max_retries)
                else:
                    # Dead-letter permanently
                    logger.error("SCHEDULER: Run %s failed permanently after %d retries.", run_id, max_retries)
                    conn.execute(
                        text("UPDATE runs SET status = 'failed', updated_at = NOW() WHERE run_id = :id"),
                        {"id": run_id}
                    )
                    conn.commit()
                    notify_human({"message": f"🚨 Markly execution FAILED permanently for Run {run_id[:8]}: {goal[:50]}. Reason: {final_state.get('escalate_reason')}"})
                    
    except Exception as e:
        logger.error("SCHEDULER: runs execution failed: %s", e)

def run_scheduler_loop():
    """Main scheduler loop running indefinitely."""
    logger.info("SCHEDULER: Daemon loop started.")
    while True:
        poll_and_execute_schedules()
        poll_and_execute_runs()
        time.sleep(10)
