## Checkpoint — 2026-07-09 — Phase 3 MCP Integration

**Branch:** phase-3-mcp
**Status:** in-progress

**What was built this session:**
- Merged `phase-2-tools-sandbox` into `develop` after successful E2E test with robust Node.js/Python sandbox.
- Initialized `phase-3-mcp` branch.

**What is NOT yet done in this phase:**
- Connect Markly's `ToolRegistry` to external MCP servers (Model Context Protocol).
- Allow loading external MCP tools (e.g. `github-mcp-server`, `postgres`) dynamically into the sandbox environment or engine.
- Update `config.toml` to support defining MCP server connections.

**Known issues / open questions:**
- Need to determine whether MCP calls should be sandboxed or run directly on host (likely host, since MCP servers run via standard stdio on host).

**Next session should start with:**
- Create `markly/tools/mcp_client.py` to handle connecting to MCP stdio servers and parsing their tool schemas into Level 1/Level 0 Markly schemas.
