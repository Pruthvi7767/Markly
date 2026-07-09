## Checkpoint — 2026-07-09 — Phase 2: CLI & Tool Sandboxing

**Branch:** phase-2-tools-sandbox
**Status:** ready-for-approval

**What was built this session:**
- Implemented `markly/sandbox.py` using `docker` Python SDK to spin up a persistent `python:3.12-slim` container per run.
- Refactored `markly/tools/registry.py` into a `ToolRegistry` class supporting Level 0 (index only) and Level 1 (full schema) progressive disclosure.
- Implemented core system tools (`shell.execute`, `file.read`, `file.write`, `code.run_python`).
- Implemented web and browser tools (`web.search`, `web.fetch`, and Playwright-based `browser.*`).
- Implemented the `<tool_observation trust="untrusted">` tagging in `executor.py`.
- Added dynamic schema injection into tool error messages to facilitate progressive disclosure without requiring a two-step planner call.
- Patched `checkpoint.py` JSON decoding bug caused by PostgreSQL `JSONB` returning dicts instead of strings in SQLAlchemy.
- Updated `engine.py` to utilize the new tool registry, sandbox execution, and progressive disclosure system.

**What is NOT yet done in this phase:**
- Nothing! Phase 2 implementation is functionally complete.

**Known issues / open questions:**
- **NVIDIA NIM Rate Limits:** The free tier for large models (`mistral-large-3-675b` and `llama-3.1-70b`) suffers from heavy rate limiting (429 Too Many Requests) and high latency, which interrupted the real-world test execution.
- **Docker Sandbox Environment:** `python:3.12-slim` does not have `node` or `npm` pre-installed, so commands like `npx` will fail unless the agent actively installs them first using `apt-get` or `npm`.

**Next session should start with:**
- Pruthvi's approval of Phase 2 based on the Test Report.
- Merging `phase-2-tools-sandbox` into `develop`.
- Beginning Phase 3 (MCP integration).
