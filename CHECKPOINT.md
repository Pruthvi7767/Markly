## Checkpoint — 2026-07-10 — Phase 7 MCP

**Branch:** phase-7-mcp
**Status:** ready-for-approval

**What was built this session:**
- Added `mcp` dependency to `pyproject.toml` and installed via `uv`.
- Added `mcp_servers` configuration block for GitHub in `config.toml`, with `auto_execute = false` and specific `tools.include`.
- Implemented `markly/tools/mcp_client.py`:
  - Runs a dedicated `asyncio` event loop in a daemon thread.
  - Connects to MCP servers over stdio and initializes the `ClientSession`.
  - Bridges the sync/async gap using `asyncio.run_coroutine_threadsafe`.
  - Applies `tools.include`/`exclude` filtering *before* registering tools.
  - Registers tools dynamically as `mcp.<server>.<tool>`.
  - Applies progressive disclosure tiering: `write_local` if `auto_execute` is true, otherwise defaults safely to `destructive` (requires approval).
- Updated `markly/engine.py` to call `register_mcp_tools(registry)` during boot.
- Updated `markly/tools/executor.py` to format MCP tool results with `<tool_observation source="mcp:<server>" trust="untrusted">`.

**What is NOT yet done in this phase:**
- Nothing. All requirements implemented.

**Known issues / open questions:**
- We added a conservative 60-second execution timeout to MCP tool calls to prevent background deadlocks.

**Next session should start with:**
- Awaiting Pruthvi's approval to merge `phase-7-mcp` into `develop`.
- Begin Phase 8.
