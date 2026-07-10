# Markly Telemetry Transparency & Privacy

Markly collects anonymous structural telemetry to help improve the platform. **Telemetry is entirely opt-in and is disabled by default.**

## Our Principles
1. **No User Content**: We never collect your goal descriptions, prompt contents, files, code, error messages, paths, variables, or tool arguments.
2. **Opt-in Only**: Telemetry is turned off by default. You must explicitly enable it during `markly setup` or by running `markly telemetry on`.
3. **No Identifiers**: We hash the UUID of runs on your local machine so we cannot trace them back to you or your system.
4. **No Monetization**: Your structural metrics are used solely for identifying bugs, failure caps, and debugging platform reliability.

## What We Collect
If you opt-in to telemetry, Markly sends a simple JSON payload with the following fields:

| Field | Description | Example |
| :--- | :--- | :--- |
| `run_id_hash` | A truncated SHA-256 hash of your local run UUID | `a8f9c1e2d3b4a5f6` |
| `status` | The final status of the run | `"completed"` or `"waiting_human_review"` |
| `turn_count` | The total number of turns executed in the run | `12` |
| `critic_count` | Number of critic diagnostics triggered | `1` |
| `consecutive_failures` | Number of consecutive subgoal failures | `0` |
| `tokens_used` | Total input and output tokens consumed | `42352` |
| `cost_total` | Total computed run cost in USD | `0.1250` |
| `tool_categories_used` | An array of tool prefixes executed (no args or outputs) | `["file", "shell", "web"]` |
| `infra_profile` | The configured setup profile | `"lightweight"` or `"heavy"` |

## Managing Telemetry Settings
You can check or change your settings at any time using the CLI:

- **Check Status**:
  ```bash
  markly telemetry status
  ```
- **Turn On**:
  ```bash
  markly telemetry on
  ```
- **Turn Off**:
  ```bash
  markly telemetry off
  ```
