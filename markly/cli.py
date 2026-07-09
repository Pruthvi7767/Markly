import os
import sys
import uuid
import tomllib
from pathlib import Path
from typing import Optional
import typer
from sqlalchemy import text
from markly.db.session import get_engine
from markly.secrets_manager import is_setup_complete
from markly.setup_wizard import run_setup_wizard


app = typer.Typer(help="Markly CLI — Autonomous AI Developer Platform")

# runs group
runs_app = typer.Typer(help="Manage Markly runs")
app.add_typer(runs_app, name="runs")

VERSION = "0.1.0-alpha"

def _load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)

def check_setup():
    """Ensure setup wizard has been run."""
    if not is_setup_complete():
        typer.echo("❌ Setup incomplete. Please run `markly setup` first.")
        raise typer.Exit(1)


@app.command("version")
def version():
    """Print the version of Markly."""
    typer.echo(f"Markly v{VERSION}")

@app.command("config")
def config():
    """Show the current parsed config.toml."""
    check_setup()
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if not cfg_path.exists():
        typer.echo("config.toml not found.")
        raise typer.Exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        typer.echo(f.read())

@app.command("setup")
def setup():
    """First-run setup wizard."""
    result = run_setup_wizard()
    if result:
        typer.echo("✅ Setup complete!")
    else:
        typer.echo("❌ Setup aborted.")


@app.command("run")
def run(goal: str = typer.Argument(..., help="The goal for the AI agent to complete")):
    """Run a goal in one-shot CLI mode."""
    check_setup()
    cfg = _load_config()
    from markly.state import initial_state
    from markly.engine import GRAPH
    
    run_id = str(uuid.uuid4())
    state = initial_state(run_id, goal, cfg)
    
    typer.echo(f"🚀 Starting new run: {run_id}")
    typer.echo(f"Goal: {goal}\n")
    
    try:
        final_state = GRAPH.invoke(state)
        if final_state.get("status") == "completed":
            typer.echo("✅ Run completed successfully!")
        else:
            typer.echo(f"❌ Run halted with status: {final_state.get('status')}")
            if final_state.get("escalate_reason"):
                typer.echo(f"Reason: {final_state.get('escalate_reason')}")
    except Exception as e:
        typer.echo(f"💥 Fatal error: {e}")
        raise typer.Exit(2)

@runs_app.command("list")
def list_runs():
    """List all historical runs from Postgres."""
    check_setup()
    if not os.environ.get("DATABASE_URL"):
        typer.echo("DATABASE_URL is not configured.")
        raise typer.Exit(1)
        
    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT run_id, goal, status, heartbeat, created_at FROM runs ORDER BY created_at DESC")
            ).fetchall()
            
        if not rows:
            typer.echo("No runs found in database.")
            return
            
        typer.echo(f"{'Run ID':<38} | {'Status':<20} | {'Created At':<20} | Goal")
        typer.echo("-" * 100)
        for r_id, goal, status, heartbeat, created_at in rows:
            goal_trunc = goal[:40] + "..." if len(goal) > 40 else goal
            typer.echo(f"{r_id:<38} | {status:<20} | {str(created_at)[:19]:<20} | {goal_trunc}")
    except Exception as e:
        typer.echo(f"Database error: {e}")
        raise typer.Exit(1)

@runs_app.command("show")
def show_run(run_id: str = typer.Argument(..., help="The Run ID to inspect")):
    """Inspect the turn history and state of a run."""
    check_setup()
    if not os.environ.get("DATABASE_URL"):
        typer.echo("DATABASE_URL is not configured.")
        raise typer.Exit(1)
        
    try:
        engine = get_engine()
        with engine.connect() as conn:
            run_row = conn.execute(
                text("SELECT goal, status, state_json FROM runs WHERE run_id = :run_id"),
                {"run_id": run_id}
            ).fetchone()
            
            if not run_row:
                typer.echo(f"Run {run_id} not found.")
                raise typer.Exit(1)
                
            goal, status, state_json = run_row
            typer.echo(f"Run ID: {run_id}")
            typer.echo(f"Goal:   {goal}")
            typer.echo(f"Status: {status}")
            typer.echo("-" * 80)
            
            turns = conn.execute(
                text("SELECT turn_number, subgoal, tool_name, tool_args, verify_score, created_at FROM turns WHERE run_id = :run_id ORDER BY turn_number ASC"),
                {"run_id": run_id}
            ).fetchall()
            
            if not turns:
                typer.echo("No turns executed yet.")
                return
                
            for t_num, subgoal, tool, args, score, created in turns:
                typer.echo(f"\nTurn #{t_num} [{created}]")
                typer.echo(f"Subgoal: {subgoal}")
                if tool:
                    typer.echo(f"Action:  {tool}({args})")
                    typer.echo(f"Verify:  Score={score}")
                else:
                    typer.echo("Action:  None")
                typer.echo("-" * 40)
    except Exception as e:
        typer.echo(f"Database error: {e}")
        raise typer.Exit(1)

@runs_app.command("kill")
def kill_run(run_id: str = typer.Argument(..., help="The Run ID to kill")):
    """Signal a run to halt immediately by setting status='killed'."""
    check_setup()
    if not os.environ.get("DATABASE_URL"):
        typer.echo("DATABASE_URL is not configured.")
        raise typer.Exit(1)
        
    try:
        engine = get_engine()
        with engine.connect() as conn:
            res = conn.execute(
                text("UPDATE runs SET status = 'killed' WHERE run_id = :run_id"),
                {"run_id": run_id}
            )
            conn.commit()
            if res.rowcount > 0:
                # Also create local .kill file for instant fallback detection
                Path(f".kill_{run_id}").touch()
                typer.echo(f"Sent kill signal to run {run_id}")
            else:
                typer.echo(f"Run {run_id} not found.")
    except Exception as e:
        typer.echo(f"Database error: {e}")
        raise typer.Exit(1)

@runs_app.command("resume")
def resume_run(run_id: str = typer.Argument(..., help="The Run ID to resume")):
    """Resume a stopped or escalated run."""
    check_setup()
    if not os.environ.get("DATABASE_URL"):
        typer.echo("DATABASE_URL is not configured.")
        raise typer.Exit(1)
        
    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT state_json FROM runs WHERE run_id = :run_id"),
                {"run_id": run_id}
            ).fetchone()
            
            if not row:
                typer.echo(f"Run {run_id} not found.")
                raise typer.Exit(1)
                
            state = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            
        # Clear kill signals and set status to running
        state["status"] = "running"
        state["is_resuming"] = True
        
        kill_file = Path(f".kill_{run_id}")
        if kill_file.exists():
            kill_file.unlink()
            
        # Update status in DB first
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE runs SET status = 'running' WHERE run_id = :run_id"),
                {"run_id": run_id}
            )
            conn.commit()
            
        typer.echo(f"♻️ Resuming run {run_id}...")
        
        from markly.engine import GRAPH
        final_state = GRAPH.invoke(state)
        if final_state.get("status") == "completed":
            typer.echo("✅ Run completed successfully!")
        else:
            typer.echo(f"❌ Run status: {final_state.get('status')}")
    except Exception as e:
        typer.echo(f"Error resuming: {e}")
        raise typer.Exit(1)

@app.command("approve")
def approve_run(run_id: str = typer.Argument(..., help="The Run ID with pending approval")):
    """Manually approve a pending action (CLI counterpart)."""
    check_setup()
    if not os.environ.get("DATABASE_URL"):
        typer.echo("DATABASE_URL is not configured.")
        raise typer.Exit(1)
        
    try:
        # For CLI approval, we update the status of the run back to 'running'
        # so that it can be picked up or resumed.
        engine = get_engine()
        with engine.connect() as conn:
            res = conn.execute(
                text("UPDATE runs SET status = 'running' WHERE run_id = :run_id AND status = 'waiting_human_review'"),
                {"run_id": run_id}
            )
            conn.commit()
            if res.rowcount > 0:
                typer.echo(f"Approved run {run_id}. Run status set to 'running'.")
            else:
                typer.echo(f"Run {run_id} is not waiting for approval.")
    except Exception as e:
        typer.echo(f"Database error: {e}")
        raise typer.Exit(1)

@app.command("skills")
def list_skills():
    """List all registered skills (stub)."""
    typer.echo("Skills: None registered. (Skills will be introduced in Phase 5)")

if __name__ == "__main__":
    app()
