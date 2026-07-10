import asyncio
import os
import queue
import sys
import logging
import threading
import uuid
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Input, RichLog, OptionList, Label
from textual.screen import ModalScreen, Screen
from textual.message import Message

from markly.state import initial_state
from markly.engine import GRAPH
from markly.tools.executor import set_approval_callback, add_always_approved_tool

# Global queue for approval communication
# Background thread puts requests, TUI thread processes them and puts results back.
approval_request_q = queue.Queue()
approval_response_q = queue.Queue()

# ASCII art logo
MARKLY_LOGO = """
 ██████╗██████╗  ██████╗ ██████╗██╗  ██╗██╗   ██╗
██╔════╝██╔══██╗██╔═══██╗██╔═══╝██║  ██║╚██╗ ██╔╝
██║     ██████╔╝██║   ██║██║    ███████║ ╚████╔╝ 
██║     ██╔══██╗██║   ██║██║    ██╔══██║  ╚██╔╝  
╚██████╗██║  ██║╚██████╔╝╚████████║  ██║   ██║   
 ╚═════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝   ╚═╝   
"""

from markly.llm import get_session_cost, get_session_tokens

def get_pricing_cost(tokens: int, model: str) -> float:
    # Delegate to central LLM cost tracker
    return get_session_cost()



def load_planner_model() -> str:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            cfg = tomllib.load(f)
            return cfg.get("models", {}).get("planner", "unknown-model")
    return "unknown-model"

# --- Approval Modal Screen ---
class ApprovalScreen(ModalScreen):
    """Modal screen for human-in-the-loop tool approvals."""
    
    def __init__(self, tool_name: str, tool_args: str, tier: str):
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.tier = tier

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"⚠️  APPROVAL REQUIRED", id="modal-title"),
            Label(f"Tool Name:  {self.tool_name}", id="modal-tool"),
            Label(f"Tier:       {self.tier}", id="modal-tier"),
            Label(f"Arguments:  {self.tool_args}", id="modal-args"),
            Label("\nSelect an action: (Use Up/Down Arrow + Enter)"),
            OptionList(
                "Approve (this time only)",
                f"Always approve '{self.tool_name}' for this project",
                "Reject execution",
                id="approval-options"
            ),
            id="modal-container"
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # 0 = Approve, 1 = Always approve, 2 = Reject
        self.dismiss(event.option_index)

# --- Selection Menu Screen for Mode/Access ---
class MenuScreen(ModalScreen):
    """General menu screen for changing mode or access."""
    
    def __init__(self, title: str, options: list[str]):
        super().__init__()
        self.title_text = title
        self.options = options

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.title_text, id="menu-title"),
            OptionList(*self.options, id="menu-options"),
            id="menu-container"
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.options[event.option_index])

# --- Escalation Review Screen ---
class EscalationReviewScreen(ModalScreen):
    """Modal shown when a run escalates to waiting_human_review.

    Loads the ESCALATION_<run_id>.md file written by notify.escalate_notify()
    and presents Retry / Kill / Dismiss options using the same OptionList
    pattern as ApprovalScreen (Phase 3).
    """

    def __init__(self, run_id: str, reason: str):
        super().__init__()
        self.run_id = run_id
        self.reason = reason
        self._report = self._load_report()

    def _load_report(self) -> str:
        from pathlib import Path
        report_path = Path(__file__).parent.parent / f"ESCALATION_{self.run_id[:8]}.md"
        if report_path.exists():
            return report_path.read_text(encoding="utf-8")[:1500]
        return "(Escalation report file not found — check logs for details.)"

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("🚨  HUMAN REVIEW REQUIRED", id="esc-title"),
            Label(f"Run ID: {self.run_id[:8]}", id="esc-run-id"),
            Label(f"Reason: {self.reason}", id="esc-reason"),
            Static(self._report, id="esc-report"),
            Label("\nChoose an action: (Up/Down + Enter)"),
            OptionList(
                "Retry  — re-queue the failed subgoal",
                "Kill   — mark run as permanently killed",
                "Dismiss — close this screen (run stays paused in DB)",
                id="esc-options",
            ),
            id="esc-container",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # 0 = Retry, 1 = Kill, 2 = Dismiss
        choice = event.option_index
        if choice == 1:
            self._kill_run()
        self.dismiss(choice)

    def _kill_run(self) -> None:
        """Mark the run as killed in Postgres."""
        import os
        if not os.environ.get("DATABASE_URL"):
            return
        try:
            from markly.db.session import get_engine
            from sqlalchemy import text
            with get_engine().connect() as conn:
                conn.execute(
                    text("UPDATE runs SET status = 'killed' WHERE run_id = :run_id"),
                    {"run_id": self.run_id},
                )
                conn.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("EscalationReviewScreen: kill failed: %s", e)


# --- Main App Screens ---
class SplashView(Screen):
    """Interactive startup screen."""
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static(MARKLY_LOGO, id="logo"),
            Static("Type goal and press Enter, or use /mode and /access to configure settings.", id="instruction"),
            Input(placeholder="Ask anything... e.g. 'Build a dropshipping website'", id="goal-input"),
            Static(id="status-bar"),
            id="splash-container"
        )

    def on_mount(self) -> None:
        self.app.update_status_bar()

class RunView(Screen):
    """Live execution visualizer."""
    
    def compose(self) -> ComposeResult:
        yield Container(
            Label("Subgoal Checklist:", id="checklist-title"),
            Static("[ ] No subgoals decomposed yet", id="checklist-list"),
            Label("Turn-by-Turn Execution Log:", id="log-title"),
            RichLog(id="run-log", wrap=True, highlight=True),
            Static("Tokens: 0 | Estimated Cost: $0.00", id="ticker"),
            id="run-container"
        )

# --- Main App ---
class MarklyTApp(App):
    CSS = """
    #splash-container {
        align: center middle;
        padding: 2;
    }
    #logo {
        text-align: center;
        color: cyan;
        margin-bottom: 2;
    }
    #instruction {
        text-align: center;
        color: gray;
        margin-bottom: 1;
    }
    #goal-input {
        width: 80;
        margin-bottom: 2;
    }
    #status-bar {
        text-align: center;
        background: blue;
        color: white;
        padding: 0 1;
        width: 80;
    }
    #run-container {
        padding: 1;
    }
    #checklist-title, #log-title {
        color: yellow;
        text-style: bold;
        margin-top: 1;
    }
    #checklist-list {
        background: #222;
        border: solid gray;
        padding: 1;
        margin-bottom: 1;
    }
    #run-log {
        height: 60%;
        border: solid gray;
        background: black;
        margin-bottom: 1;
    }
    #ticker {
        background: darkgreen;
        color: white;
        text-align: right;
        padding: 0 1;
    }
    
    /* Modal styles */
    #modal-container, #menu-container {
        padding: 1 2;
        background: #333;
        border: thick red;
        width: 60;
        height: auto;
        align: center middle;
    }
    #modal-title, #menu-title {
        text-style: bold;
        color: red;
        margin-bottom: 1;
        text-align: center;
    }
    #modal-tool, #modal-tier, #modal-args {
        color: white;
    }
    #approval-options, #menu-options {
        border: solid gray;
        height: 8;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("ctrl+m", "mode_menu", "Select Mode"),
        ("ctrl+a", "access_menu", "Select Access"),
        ("q", "quit", "Quit")
    ]

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.mode = cfg.get("engine", {}).get("default_mode", "goal")
        self.access = cfg.get("engine", {}).get("default_access", "auto")
        self.model = load_planner_model()
        self.run_thread = None
        self.subgoals_list = []
        self.current_subgoal_idx = 0
        self.total_tokens = 0
        self.log_widget = None

    def on_mount(self) -> None:
        self.push_screen(SplashView())
        # Set up a polling timer to process approval requests from background thread
        self.set_interval(0.2, self.check_approval_requests)
        self.set_interval(1.0, self.poll_cost_and_tokens)

    def poll_cost_and_tokens(self) -> None:
        """Fetch live tokens and cost from the global tracker."""
        from markly.llm import get_session_cost, get_session_tokens
        tokens = get_session_tokens()
        cost = get_session_cost()
        try:
            ticker = self.query_one("#ticker", Static)
            ticker.update(f"Tokens: {tokens} | Estimated Cost: ${cost:.4f}")
        except Exception:
            pass


    def update_status_bar(self) -> None:
        try:
            bar = self.screen.query_one("#status-bar", Static)
            bar.update(f"Mode: {self.mode.upper()} | Access: {self.access.upper()} | Model: {self.model}")
        except Exception:
            pass

    def action_mode_menu(self) -> None:
        self.push_screen(
            MenuScreen("Select Mode", ["plan", "goal", "read-only"]),
            self.on_mode_selected
        )

    def on_mode_selected(self, selected_mode: str) -> None:
        if selected_mode:
            self.mode = selected_mode
            self.update_status_bar()

    def action_access_menu(self) -> None:
        self.push_screen(
            MenuScreen("Select Access", ["auto", "ask"]),
            self.on_access_selected
        )

    def on_access_selected(self, selected_access: str) -> None:
        if selected_access:
            self.access = selected_access
            self.update_status_bar()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text_val = event.value.strip()
        if not text_val:
            return

        # Interactive commands checking
        if text_val.startswith("/mode"):
            parts = text_val.split()
            if len(parts) > 1 and parts[1] in ("plan", "goal", "read-only"):
                self.mode = parts[1]
                self.update_status_bar()
                event.input.value = ""
            else:
                self.action_mode_menu()
            return
        elif text_val.startswith("/access"):
            parts = text_val.split()
            if len(parts) > 1 and parts[1] in ("auto", "ask"):
                self.access = parts[1]
                self.update_status_bar()
                event.input.value = ""
            else:
                self.action_access_menu()
            return

        # Start agent execution
        event.input.disabled = True
        run_view = RunView()
        self.push_screen(run_view)
        self.call_after_refresh(lambda: self.start_agent_run(text_val, run_view))

    def start_agent_run(self, goal: str, run_view: RunView) -> None:
        self.log_widget = run_view.query_one("#run-log", RichLog)
        self.log_widget.write(f"Initializing engine for goal: '{goal}'...")

        # Setup engine approvals
        set_approval_callback(self._thread_approval_handler)

        # Run state
        run_id = str(uuid.uuid4())
        state = initial_state(run_id, goal, self.cfg)
        state["mode"] = self.mode
        state["access"] = self.access

        # Run background thread
        self.run_thread = threading.Thread(
            target=self._engine_run_wrapper,
            args=(state,),
            daemon=True
        )
        self.run_thread.start()

    def _engine_run_wrapper(self, state: dict) -> None:
        try:
            # We capture logging or status checkpoints via callback or custom log
            # Since standard engine prints to stdout/logs, we can mock print or write custom logging handlers.
            # For simplicity, we just invoke LangGraph and write progress updates.
            final_state = GRAPH.invoke(state)
            self.call_from_thread(self.log_message, f"\nFinished invocation. Status: {final_state.get('status')}")
        except Exception as e:
            self.call_from_thread(self.log_message, f"\nFATAL ERROR in graph: {e}")

    def log_message(self, msg: str) -> None:
        if self.log_widget:
            self.log_widget.write(msg)

    def _thread_approval_handler(self, tool_name: str, tool_args: Dict[str, Any], tier: str) -> bool:
        """Executed inside the background engine thread. Blocks until approved/rejected."""
        # Post request to queue and notify TUI
        approval_request_q.put((tool_name, str(tool_args), tier))
        
        # Block until response is put into queue
        approved = approval_response_q.get()
        return approved

    def check_approval_requests(self) -> None:
        """Polled by Textual main thread to trigger Modals."""
        try:
            # Check non-blocking
            tool_name, tool_args, tier = approval_request_q.get_nowait()
            self.current_pending_tool = tool_name
            
            # Show approval screen
            self.push_screen(
                ApprovalScreen(tool_name, tool_args, tier),
                self.on_approval_decision
            )
        except queue.Empty:
            pass

    def on_approval_decision(self, choice_index: int) -> None:
        # Choice: 0 = Approve, 1 = Always approve, 2 = Reject
        if choice_index == 0:
            self.log_message("[TUI] Approved execution.")
            approval_response_q.put(True)
        elif choice_index == 1:
            tool_name = getattr(self, "current_pending_tool", None)
            if tool_name:
                self.log_message(f"[TUI] Whitelisted tool '{tool_name}' for this run.")
                add_always_approved_tool(tool_name)
            else:
                self.log_message("[TUI] Whitelisted tool for this run.")
            approval_response_q.put(True)
        else:
            self.log_message("[TUI] Execution rejected.")
            approval_response_q.put(False)

    def update_ticker(self, tokens: int) -> None:
        self.total_tokens = tokens
        cost = get_pricing_cost(tokens, self.model)
        try:
            ticker = self.query_one("#ticker", Static)
            ticker.update(f"Tokens: {tokens} | Estimated Cost: ${cost:.4f}")
        except Exception:
            pass

# To bridge turns logging into textual, we can tap into engine.py logging
# We will redirect python logging to our RichLog
class TuiLogHandler(logging.Handler):
    def __init__(self, app: MarklyTApp):
        super().__init__()
        self.app = app

    def emit(self, record):
        try:
            msg = self.format(record)
            self.app.call_from_thread(self.app.log_message, msg)
            
            # Update tokens if engine logs tokens
            if "VERIFY" in msg or "FINAL" in msg:
                # Parse tokens dynamically from state or checkpoint if possible
                pass
        except Exception:
            pass

import logging
def setup_tui_logging(app: MarklyTApp):
    handler = TuiLogHandler(app)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S"))
    logging.getLogger("markly").addHandler(handler)
    logging.getLogger("markly.engine").addHandler(handler)

def run_tui(cfg: dict):
    app = MarklyTApp(cfg)
    setup_tui_logging(app)
    app.run()
