"""Scheduled runs tools — Phase 11.

- schedule.create_recurring: creates a recurring execution schedule.
- cron.list: lists all active cron schedules.
- cron.cancel: cancels a recurring schedule.
"""
import uuid
import logging
from typing import Dict, Any
from sqlalchemy import text

from markly.db.session import get_engine
from markly.tools.registry import ToolRegistry
from markly.scheduler import calculate_next_run, datetime, timezone

logger = logging.getLogger(__name__)

def create_recurring(args: Dict[str, Any]) -> str:
    cron_expression = args.get("cron_expression")
    goal = args.get("goal")
    if not cron_expression or not goal:
        return "Error: missing 'cron_expression' or 'goal'"
        
    engine = get_engine()
    schedule_id = str(uuid.uuid4())
    
    # Calculate initial next_run_at
    try:
        now = datetime.now(timezone.utc)
        next_run = calculate_next_run(cron_expression, now)
    except Exception as e:
        return f"Error: Invalid cron expression '{cron_expression}': {e}"
        
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO schedules (schedule_id, cron_expression, goal, active, next_run_at, created_at, updated_at)
                    VALUES (:id, :cron, :goal, TRUE, :next, NOW(), NOW())
                """),
                {
                    "id": schedule_id,
                    "cron": cron_expression,
                    "goal": goal,
                    "next": next_run
                }
            )
            conn.commit()
        return f"Successfully created recurring schedule. Schedule ID: {schedule_id}. Next execution at: {next_run}"
    except Exception as e:
        return f"Error database write failed: {e}"

def cron_list(args: Dict[str, Any]) -> str:
    engine = get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT schedule_id, cron_expression, goal, active, next_run_at FROM schedules WHERE active = TRUE")
            ).fetchall()
            
        if not rows:
            return "No active recurring cron schedules found."
            
        output = []
        for s_id, cron, goal, active, next_run in rows:
            output.append(f"ID: {s_id} | Cron: {cron} | Next Run: {next_run} | Goal: {goal}")
        return "\n".join(output)
    except Exception as e:
        return f"Error fetching schedules: {e}"

def cron_cancel(args: Dict[str, Any]) -> str:
    schedule_id = args.get("schedule_id")
    if not schedule_id:
        return "Error: missing 'schedule_id'"
        
    engine = get_engine()
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("UPDATE schedules SET active = FALSE, updated_at = NOW() WHERE schedule_id = :id AND active = TRUE"),
                {"id": schedule_id}
            )
            conn.commit()
            if res.rowcount > 0:
                return f"Successfully cancelled schedule {schedule_id}."
            else:
                return f"Schedule {schedule_id} not found or already inactive."
    except Exception as e:
        return f"Error updating schedule status: {e}"

def register_schedule_tools(registry: ToolRegistry):
    registry.register(
        name="schedule.create_recurring",
        category="schedule",
        description="Schedule a recurring execution task using a 5-field cron expression.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "cron_expression": {"type": "string", "description": "Standard 5-field cron string (e.g. '*/5 * * * *')"},
                "goal": {"type": "string", "description": "The goal description to run on this schedule"}
            },
            "required": ["cron_expression", "goal"]
        },
        func=create_recurring
    )
    
    registry.register(
        name="cron.list",
        category="schedule",
        description="List all active recurring schedules currently registered in the system.",
        tier="read_only",
        schema={"type": "object", "properties": {}},
        func=cron_list
    )
    
    registry.register(
        name="cron.cancel",
        category="schedule",
        description="Cancel an active recurring schedule by its Schedule ID.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "schedule_id": {"type": "string", "description": "The Schedule ID to deactivate"}
            },
            "required": ["schedule_id"]
        },
        func=cron_cancel
    )
