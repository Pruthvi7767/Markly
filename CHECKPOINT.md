## Checkpoint — 2026-07-11 — test-batch-1

**Branch:** test-batch-1
**Status:** ready-for-approval

**What was built/fixed this session:**
- Executed Tests 1.1 through 1.5 successfully.
- Produced `test-reports/batch-1.md` detailing the test logs and outputs, conforming to AGENTS.md rules.
- Fixed `markly runs resume` in `markly/cli.py` to properly inject the approval handler.
- Fixed the max_consecutive_failures threshold cap to accurately escalate the task on continuous verification failures.

**What is NOT yet done:**
- Batch 2 testing.

**Known issues / open questions:**
- Docker Desktop is not running, so `github-mcp-server` integration is currently disabled (falling back to standard CLI tools).

**Next session should start with:**
- Pruthvi reviewing and approving the `test-reports/batch-1.md` report. Once approved, merge `test-batch-1` into `develop` and provide instructions/prompt for Test Batch 2.
