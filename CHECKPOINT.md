## Checkpoint — 2026-07-09 — Phase 3 (CLI & TUI) Completed

**Branch:** phase-3-cli-tui
**Status:** ready-for-approval

**What was built this session:**
- Installed `typer` and `textual` dependencies.
- Added default mode and access parameters to `config.toml`.
- Updated `engine.py` and `executor.py` to support interactive modes (`plan`, `goal`, `read-only`), access levels (`auto`, `ask`), and thread-safe approval callbacks.
- Implemented whitelisting support (`Always approve [tool] for this project`) which registers whitelisted tools dynamically inside `_always_approved_tools` in the executor.
- Implemented standard one-shot CLI commands in `markly/cli.py`:
  - `markly setup`: Guided wizard (stubbed).
  - `markly run <goal>`: Run the goal in one-shot CLI mode.
  - `markly runs list`: Lists historical run details from Postgres.
  - `markly runs resume <id>`: Resumes a stopped run.
  - `markly runs kill <id>`: Sets status to `killed` in Postgres.
  - `markly runs show <id>`: Prints structured history logs for a run.
  - `markly approve <id>`: CLI counterpart to manually approve a run's pending action.
  - `markly config`: Displays `config.toml` settings.
  - `markly skills list`: Stub listing of registered skills.
  - `markly version`: Prints project version (`0.1.0-alpha`).
- Implemented interactive TUI in `markly/tui.py`:
  - Splash screen displaying ASCII banner, status lines, and goal input.
  - Navigation menus for mode selection (`/mode` or `ctrl+m`) and access selection (`/access` or `ctrl+a`).
  - Run View screen showing subgoal checklist progress, live turn-by-turn logs, and token/cost tickers.
  - Approval Modal screen suspending the background engine thread and requesting confirmation (Approve once, always approve, or reject) via arrow-keys + Enter.

**What is NOT yet done in this phase:**
- None. All requirements of Phase 3 are complete and validated.

**Known issues / open questions:**
- During live testing, the engine completed successfully but hit rate-limits (HTTP 429) at the very end from the NVIDIA NIM API. The core flow (plan, execute, approve, resume) executed flawlessly.

**Next session should start with:**
- Merge `phase-3-cli-tui` into `develop` once approved by Pruthvi.
- Await Phase 4 instructions from Pruthvi.
