## Checkpoint — 2026-07-10 — Phase 8 Eval Harness

**Branch:** phase-8-eval-harness
**Status:** ready-for-approval

**What was built this session:**
- `markly/eval/tasks.py`: 18 curated eval tasks across 4 categories with programmatic success checks.
- `markly/eval/runner.py`: Eval test runner that executes tasks N times, computes success rate, cost, turns, and cap fire counts.
- `markly/eval/ui_verifier.py`: Playwright-based headless browser verifier for UI tasks using a local HTTP server.
- `markly/eval/regression.py`: Persists passing UI assertions to `workspace/<task_id>/regression.json` for continuous regression testing.
- `markly/cli.py`: Added `markly eval` subcommand with `--fast` mode (N=1) and `--tasks` subset running.
- `.github/workflows/markly_eval.yml`: Configured CI gate running the fast eval subset on PRs to `develop`.
- Test fixtures (`broken.py`, `noop.py`, `loop_bug.py`, `divide.py`).
- Fixed an alias in `markly/tools/core.py` to map Groq's hallucinatory `filename` argument back to `path` in `file.write`.

**What is NOT yet done in this phase:**
- Nothing — all requirements met.

**Known issues / open questions:**
- We added a conservative 60-second execution timeout to MCP tool calls to prevent background deadlocks.

**Next session should start with:**
- Awaiting Pruthvi's approval to merge `phase-7-mcp` into `develop`.
- Begin Phase 8.
