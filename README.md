# Markly — Autonomous AI Developer Platform

Markly is a self-hosted, open-source autonomous developer agent. It orchestrates a structured Planner → Worker (CodeAct) → Verifier → Critic loop powered by LangGraph, with robust PostgreSQL checkpointing, safe sandboxed container execution, and progressive tool discovery.

## Features
- **Deterministic Loop Orchestration**: Strict StateGraph implementation separation between Planner (proposes subgoals), Worker (executes deterministically inside Docker sandbox), Verifier (double-checks results with strict scores), and Critic (diagnoses and injects corrections on failure).
- **Docker-in-Docker Sandboxing**: Sibling container execution ensures all code writing, shell executions, and playbooks are fully isolated from the host.
- **Three-Tier Memory**: Fact store limits (`MEMORY.md` & `USER.md`), dynamically discoverable procedural skills (`skills/` directory), and episodic database log with native PostgreSQL full-text search.
- **Opt-in Transparency**: Clear, non-identifying telemetry disabled by default (see [TELEMETRY.md](TELEMETRY.md)).
- **Cost & Token Breakdown**: Real-time role-based token accounting and cost tracking using pricing specifications from `pricing.toml`.

---

## Quickstart

### Prerequisites
- Docker Desktop or Docker Engine + Docker Compose v2.
- An API Key for [NVIDIA NIM](https://build.nvidia.com/) (Required for primary models like `mistralai/mistral-large-3-675b-instruct-2512`).
- Optional: An API Key for Groq (for automatic rate-limit and service fallbacks).

### One-Command Installation

#### Windows (PowerShell):
Run the installer script:
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

#### macOS / Linux:
Run the installer script:
```bash
curl -fsSL get.markly.dev/install.sh | bash
# or run the local script:
chmod +x install.sh && ./install.sh
```

---

## Usage

### 1. Setup Wizard
Launch the first-run configuration wizard to configure LLM keys, select your infrastructure profile, test API connections, and manage telemetry options:
```bash
markly setup
```

### 2. Run a Goal
Run an autonomous developer cycle to achieve a specific goal:
```bash
markly run "Scaffold a python web app that shows active network logs in a styled HTML table"
```

### 3. Review Historical Runs
Inspect the status and turn audit logs of past runs:
```bash
markly runs list
```

Show a detailed breakdown of state, tool calls, and role-based token/cost tracking:
```bash
markly runs show <run-id>
```

### 4. Telemetry Settings
View and change your telemetry settings:
```bash
markly telemetry status
markly telemetry off
markly telemetry on
```

### 5. Self-Update
Keep Markly up-to-date with new images and migrations automatically:
```bash
markly update
```

---

## Architecture Scope
Markly is designed to be **single-user and self-hosted**. It is **not designed for multi-tenant deployments** or running as a public SaaS. All databases, checkpoint ledgers, and sandboxed work spaces are kept strictly local to your machine.

## License
MIT License. See [LICENSE](LICENSE) for details.
