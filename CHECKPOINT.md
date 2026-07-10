## Checkpoint — 2026-07-10 — Phase 10 Packaging, Deployment, and Cost Tracking

**Branch:** phase-10-packaging
**Status:** ready-for-approval

**What was built this session:**
- **Cost & Token Tracking**: Integrated role-based token counting and pricing calculation into `markly/state.py`, `markly/llm.py`, `markly/engine.py`, and `markly/cli.py` (`markly runs show` breakdown).
- **Opt-in Telemetry**: Built `markly/telemetry.py` to send anonymous structural metrics asynchronously when enabled, and created `TELEMETRY.md` transparency document.
- **Docker Bundling**: Created `Dockerfile` and updated `docker-compose.yml` to bundle `markly-cli`, `postgres`, and `chroma` services with healthchecks and persistent volumes.
- **Install Scripts**: Created `install.sh` and `install.ps1` for one-command installation and automatic path configuration.
- **Cleaned Win32 Prints**: Replaced all heavy unicode emojis in `markly/cli.py` with ASCII indicators (`[OK]`, `[ERROR]`, `[START]`) to prevent encoding failures on Windows consoles.
- **Obsidian Vault Graph**: Compiled 12 hand-written Markdown files inside `graphify-out/obsidian/` detailing the exact architecture, logic, schemas, and API definitions of every module in the project.

**What is NOT yet done in this phase:**
- Nothing — all requirements and verification steps are completed.

**Known issues / open questions:**
- None.

**Next session should start with:**
- Awaiting Pruthvi's approval of the Phase 10 Test Report and the Obsidian Knowledge Graph.
- Merge `phase-10-packaging` branch into `develop` and tag `v0.1.0-alpha`.
