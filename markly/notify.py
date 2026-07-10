"""Escalation notification — real human alert on run failure.

Per AGENTS.md Section 6:
- Unhandled failure always defaults to pause-and-notify-human.
- Never silent continuation, never silent failure.

What this module does:
1. Sends a desktop toast notification (plyer, graceful fallback to stderr).
2. Writes a human-readable ESCALATION_<run_id>.md in the repo root.

The run is already permanently halted before this is called (escalate()
routes to END). This is purely the notification path.
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Where to write escalation files — repo root
_REPO_ROOT = Path(__file__).parent.parent


def _toast(title: str, message: str) -> None:
    """Send a desktop notification, falling back to stderr."""
    try:
        import plyer
        plyer.notification.notify(
            title=title,
            message=message[:255],  # plyer caps at 255 chars on Windows
            app_name="Markly",
            timeout=10,
        )
        logger.info("ESCALATE: desktop notification sent")
    except Exception as e:
        # plyer not installed, or notification daemon unavailable — non-fatal
        logger.warning("ESCALATE: desktop notification unavailable (%s) — using stderr", e)
        print(f"\n🚨 MARKLY ESCALATION: {title}\n{message}", flush=True)


def _write_escalation_file(
    run_id: str,
    reason: str,
    last_turns: list[dict],
    critic_diagnosis: str | None,
) -> Path:
    """Write ESCALATION_<run_id>.md and return its path."""
    path = _REPO_ROOT / f"ESCALATION_{run_id[:8]}.md"

    lines = [
        f"# Markly Escalation Report",
        f"",
        f"**Run ID:** `{run_id}`",
        f"**Time:** {datetime.now(timezone.utc).isoformat()}",
        f"**Reason:** {reason}",
        f"",
        f"## Last 3 Turns",
        f"",
    ]
    for i, t in enumerate(last_turns[-3:], 1):
        lines += [
            f"### Turn {i}",
            f"- **Subgoal:** {t.get('subgoal', '')}",
            f"- **Tool:** `{t.get('tool_name', 'N/A')}`",
            f"- **Score:** {t.get('verify_score', 'N/A')}",
            f"- **Observation:** {str(t.get('observation', ''))[:300]}",
            f"",
        ]

    if critic_diagnosis:
        lines += [
            f"## Critic's Last Diagnosis",
            f"",
            f"```",
            critic_diagnosis,
            f"```",
            f"",
        ]

    lines += [
        f"## Actions Available",
        f"",
        f"- **Retry:** Re-run from this subgoal via `markly resume {run_id}`",
        f"- **Kill:** `markly kill {run_id}`",
        f"- **Review:** Open the TUI and use the Escalation Review screen.",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("ESCALATE: wrote %s", path)
    return path


def escalate_notify(
    run_id: str,
    reason: str,
    last_turns: list[dict],
    critic_diagnosis: str | None,
) -> None:
    """Full escalation notification: toast + file write.

    Called from engine.escalate() after the run is permanently halted.
    Never raises — any failure here is logged but does not affect the
    already-halted run state.
    """
    try:
        file_path = _write_escalation_file(run_id, reason, last_turns, critic_diagnosis)
        _toast(
            title="Markly — Human Review Required",
            message=f"Run {run_id[:8]} needs your attention.\n{reason}\nSee: {file_path.name}",
        )
    except Exception as e:
        logger.error("ESCALATE: notify failed completely (%s) — run is still halted", e)
