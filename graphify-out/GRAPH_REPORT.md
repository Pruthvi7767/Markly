# Graph Report - Markly  (2026-07-09)

## Corpus Check
- 204 files · ~17,395 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 710 nodes · 922 edges · 74 communities (53 shown, 21 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6c501824`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 72|Community 72]]

## God Nodes (most connected - your core abstractions)
1. `MarklyTApp` - 21 edges
2. `get_engine()` - 15 edges
3. `RunState` - 13 edges
4. `ToolRegistry` - 13 edges
5. `_checkpoint()` - 11 edges
6. `subgoal_loop()` - 11 edges
7. `DockerSandbox` - 11 edges
8. `check_setup()` - 9 edges
9. `call_llm()` - 9 edges
10. `ConnectionTestScreen` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_setup()` --calls--> `SetupWizardApp`  [EXTRACTED]
  test_phase4.py → markly/setup_wizard.py
- `run_test()` --calls--> `initial_state()`  [EXTRACTED]
  test_engine.py → markly/state.py
- `save_run()` --calls--> `get_engine()`  [EXTRACTED]
  markly/checkpoint.py → markly/db/session.py
- `_checkpoint()` --calls--> `save_run()`  [EXTRACTED]
  markly/engine.py → markly/checkpoint.py
- `save_turn()` --calls--> `get_engine()`  [EXTRACTED]
  markly/checkpoint.py → markly/db/session.py

## Import Cycles
- None detected.

## Communities (74 total, 21 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (24): _attempt_call(), Outgoing Connections, call_llm(), Outgoing Connections, Call the LLM for the given role with automatic fallback.      Args:         role, Outgoing Connections, Ensure API keys are never leaked in error strings., Outgoing Connections (+16 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (23): Outgoing Connections, ComposeResult, ConnectionTestScreen, Outgoing Connections, Interactive startup screen., Outgoing Connections, Live execution visualizer., Outgoing Connections (+15 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (16): browser.py, Outgoing Connections, Outgoing Connections, register_browser_tools(), Outgoing Connections, register_web_tools(), Outgoing Connections, registry.py (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (15): core.py, Outgoing Connections, DockerSandbox, Outgoing Connections, Outgoing Connections, get_current_sandbox(), Outgoing Connections, Outgoing Connections (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (27): get_engine(), SQLAlchemy engine + session factory.  Reads DATABASE_URL from environment. Fails, Return a cached SQLAlchemy engine. Raises on missing DATABASE_URL., Engine, load_stale_run(), On startup, find any run with status='running' and stale heartbeat.      Retur, approve_run(), check_setup() (+19 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (12): Any, Execute a registered tool. Returns wrapped observation string.      Raises Val, Outgoing Connections, execute_tool(), Outgoing Connections, Executed inside the background engine thread. Blocks until approved/rejected., Outgoing Connections, executor.py (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (14): App, First-run setup wizard., setup(), ConnectionTestScreen, Textual-based setup wizard for Markly.  Collects API keys, tests connections,, Main setup screen for Markly., The Markly Setup Wizard application., Shows connection testing progress and results. (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (14): checkpoint.py, Outgoing Connections, Insert a turn record into the turns table., Outgoing Connections, load_stale_run(), Outgoing Connections, On startup, find any run with status='running' and stale heartbeat.      Retur, Outgoing Connections (+6 more)

### Community 8 - "Community 8"
Cohesion: 0.19
Nodes (16): _checkpoint(), critic(), decompose(), escalate(), final_output(), next_subgoal(), Markly core engine — LangGraph StateGraph implementation.  Loop: decompose → [, Diagnose why the subgoal failed; inject a correction hint. (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (8): Outgoing Connections, Outgoing Connections, General menu screen for changing mode or access., Outgoing Connections, MenuScreen, Outgoing Connections, Outgoing Connections, Submitted

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (11): App, First-run setup wizard., Outgoing Connections, Outgoing Connections, run_setup_wizard(), Outgoing Connections, setup(), Outgoing Connections (+3 more)

### Community 11 - "Community 11"
Cohesion: 0.20
Nodes (12): Exception, _attempt_call(), _calculate_cost(), call_llm(), _get_client(), LLM client — single choke point for all LLM calls.  All Planner, Verifier, and, Make the API call with backoff and jitter., Call the LLM for the given role with automatic fallback.      Args:         r (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (6): register_browser_tools(), Tool registry with progressive disclosure.  Level 0 index (name + category + d, Returns the base index string to always include in context., Returns full JSON schemas for the requested categories., ToolRegistry, register_web_tools()

### Community 13 - "Community 13"
Cohesion: 0.15
Nodes (9): Build the starting RunState for a fresh run., Outgoing Connections, initial_state(), Outgoing Connections, Outgoing Connections, RunState, Outgoing Connections, state.py (+1 more)

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (5): get_current_sandbox(), DockerSandbox, Returns (exit_code, output), Write a file into the local workspace directory (which is mounted into the conta, register_core_tools()

### Community 15 - "Community 15"
Cohesion: 0.15
Nodes (7): ApprovalScreen, Outgoing Connections, Modal screen for human-in-the-loop tool approvals., Outgoing Connections, ModalScreen, Outgoing Connections, OptionSelected

### Community 16 - "Community 16"
Cohesion: 0.18
Nodes (4): MarklyTApp, Outgoing Connections, Outgoing Connections, Outgoing Connections

### Community 17 - "Community 17"
Cohesion: 0.18
Nodes (7): Any, Executed inside the background engine thread. Blocks until approved/rejected., add_always_approved_tool(), execute_tool(), _get_permissions(), Tool executor — Phase 2 Sandbox.  Dispatches tool calls to their implementatio, Execute a registered tool. Returns wrapped observation string.      Raises Val

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (6): ComposeResult, Interactive startup screen., Live execution visualizer., RunView, SplashView, Screen

### Community 19 - "Community 19"
Cohesion: 0.18
Nodes (7): ApprovalScreen, MenuScreen, Polled by Textual main thread to trigger Modals., Modal screen for human-in-the-loop tool approvals., General menu screen for changing mode or access., ModalScreen, OptionSelected

### Community 20 - "Community 20"
Cohesion: 0.18
Nodes (7): Engine, get_engine(), Outgoing Connections, Outgoing Connections, Return a cached SQLAlchemy engine. Raises on missing DATABASE_URL., Outgoing Connections, session.py

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (6): Execute ONE TURN of the inner loop for the current subgoal.      Turn sequence, Outgoing Connections, Outgoing Connections, Short deterministic hash of tool+args for dedup checking., Outgoing Connections, subgoal_loop()

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (6): Outgoing Connections, run_tui(), Outgoing Connections, setup_tui_logging(), Outgoing Connections, tui.py

### Community 23 - "Community 23"
Cohesion: 0.22
Nodes (10): Insert a turn record into the turns table., save_turn(), _estimate_tokens(), _fail_turn(), _hash_action(), Execute ONE TURN of the inner loop for the current subgoal.      Turn sequence, Immediate verify-fail helper for validation/dedup errors., Short deterministic hash of tool+args for dedup checking. (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.27
Nodes (6): get_session_cost(), get_session_tokens(), get_pricing_cost(), Fetch live tokens and cost from the global tracker., setup_tui_logging(), TuiLogHandler

### Community 25 - "Community 25"
Cohesion: 0.31
Nodes (3): MarklyTApp, Submitted, set_approval_callback()

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (4): engine.py, Outgoing Connections, Outgoing Connections, _route()

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (4): cli.py, Outgoing Connections, List all registered skills (stub)., Outgoing Connections

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (3): Outgoing Connections, Outgoing Connections, TuiLogHandler

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (3): Fetch live tokens and cost from the global tracker., Outgoing Connections, Outgoing Connections

### Community 30 - "Community 30"
Cohesion: 0.25
Nodes (3): get_pricing_cost(), Outgoing Connections, Outgoing Connections

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (4): main(), Outgoing Connections, __main__.py, Outgoing Connections

### Community 33 - "Community 33"
Cohesion: 0.47
Nodes (4): initial_state(), RunState — the single source of truth for a Markly run.  All fields are plain, Build the starting RunState for a fresh run., run_test()

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (4): Advance to the next subgoal or signal completion., Outgoing Connections, next_subgoal(), Outgoing Connections

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (4): approve_run(), Outgoing Connections, Manually approve a pending action (CLI counterpart)., Outgoing Connections

### Community 36 - "Community 36"
Cohesion: 0.33
Nodes (3): Outgoing Connections, Outgoing Connections, Polled by Textual main thread to trigger Modals.

### Community 37 - "Community 37"
Cohesion: 0.33
Nodes (4): _checkpoint(), Outgoing Connections, Outgoing Connections, Save merged state to Postgres. Logs error but re-raises — never silent.

### Community 38 - "Community 38"
Cohesion: 0.33
Nodes (4): config(), Outgoing Connections, Outgoing Connections, Show the current parsed config.toml.

### Community 39 - "Community 39"
Cohesion: 0.33
Nodes (4): critic(), Outgoing Connections, Diagnose why the subgoal failed; inject a correction hint., Outgoing Connections

### Community 40 - "Community 40"
Cohesion: 0.33
Nodes (4): decompose(), Outgoing Connections, Outgoing Connections, Phase 0: break the goal into subgoals via LLM (skipped on resume).

### Community 41 - "Community 41"
Cohesion: 0.33
Nodes (4): escalate(), Outgoing Connections, Outgoing Connections, Terminal: escalate to human review.

### Community 42 - "Community 42"
Cohesion: 0.33
Nodes (4): _fail_turn(), Outgoing Connections, Immediate verify-fail helper for validation/dedup errors., Outgoing Connections

### Community 43 - "Community 43"
Cohesion: 0.33
Nodes (4): final_output(), Outgoing Connections, Mark run complete and print summary., Outgoing Connections

### Community 44 - "Community 44"
Cohesion: 0.33
Nodes (4): Inspect the turn history and state of a run., Outgoing Connections, Outgoing Connections, show_run()

### Community 45 - "Community 45"
Cohesion: 0.33
Nodes (4): kill_run(), Outgoing Connections, Outgoing Connections, Signal a run to halt immediately by setting status='killed'.

### Community 46 - "Community 46"
Cohesion: 0.33
Nodes (4): List all historical runs from Postgres., Outgoing Connections, list_runs(), Outgoing Connections

### Community 47 - "Community 47"
Cohesion: 0.33
Nodes (4): Outgoing Connections, Resume a stopped or escalated run., Outgoing Connections, resume_run()

### Community 48 - "Community 48"
Cohesion: 0.33
Nodes (4): Outgoing Connections, Run a goal in one-shot CLI mode., Outgoing Connections, run()

### Community 49 - "Community 49"
Cohesion: 0.60
Nodes (4): _load_config(), main(), Markly entry point.  Usage:     python -m markly "Your goal here"     python, run_tui()

### Community 54 - "Community 54"
Cohesion: 0.50
Nodes (3): Postgres checkpointing — persists RunState after every turn.  Per AGENTS.md Se, Upsert the full RunState to the runs table. Updates heartbeat., save_run()

## Knowledge Gaps
- **154 isolated node(s):** `markly`, `graphify`, `Workflow: graphify`, `Checkpoint — 2026-07-09 — Phase 3 (CLI & TUI) Completed`, `Outgoing Connections` (+149 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_engine()` connect `Community 4` to `Community 8`, `Community 54`, `Community 23`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Why does `MarklyTApp` connect `Community 25` to `Community 6`, `Community 17`, `Community 50`, `Community 19`, `Community 18`, `Community 49`, `Community 24`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Why does `initial_state()` connect `Community 33` to `Community 8`, `Community 24`, `Community 4`, `Community 25`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **What connects `Alembic environment — reads DATABASE_URL from .env.`, `Markly — self-hosted autonomous AI agent platform.`, `Markly entry point.  Usage:     python -m markly "Your goal here"     python` to the rest of the system?**
  _210 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05537098560354374 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.053426248548199766 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.058823529411764705 - nodes in this community are weakly interconnected._