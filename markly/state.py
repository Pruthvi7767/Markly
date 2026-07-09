"""RunState — the single source of truth for a Markly run.

All fields are plain Python types so the state can be JSON-serialized
for Postgres checkpointing without any extra conversion step.
"""
from typing import TypedDict


class RunState(TypedDict):
    # ── Identity ─────────────────────────────────────────────────────────────
    run_id: str          # UUID string
    goal: str            # original user goal

    # ── Subgoal progress ─────────────────────────────────────────────────────
    remaining_subgoals: list[str]   # subgoals not yet started
    current_subgoal: str            # subgoal currently being executed
    subgoal_index: int              # 0-based index of current_subgoal

    # ── Turn-level state ─────────────────────────────────────────────────────
    last_observation: str           # most recent tool observation (tagged untrusted)
    correction_hint: str | None     # set by critic, cleared after use

    # ── Counters ─────────────────────────────────────────────────────────────
    turn_count: int                 # total turns across all subgoals
    subgoal_turn_count: int         # turns within the current subgoal (resets)
    tokens_used: int                # total tokens consumed this run

    # ── Per-subgoal tracking (all reset when advancing to next subgoal) ──────
    verify_fail_count: int          # verify failures within current subgoal
    critic_attempted: bool          # has critic fired for current subgoal
    action_hash_history: list[str]  # dedup hashes for current subgoal

    # ── Global run tracking ───────────────────────────────────────────────────
    consecutive_failures: int       # consecutive subgoal-level failures
    critic_count: int               # total critic invocations in this run

    # ── Status ───────────────────────────────────────────────────────────────
    # Values: "running" | "completed" | "escalated" | "waiting_human_review"
    status: str
    escalate_reason: str            # populated when status="escalated"

    # ── Resume flag ───────────────────────────────────────────────────────────
    is_resuming: bool               # True when loaded from Postgres checkpoint

    # ── Budget (set once at run start from config.toml) ──────────────────────
    max_turns: int
    max_tokens: int
    max_turns_per_subgoal: int
    max_consecutive_failures: int
    max_critic_invocations: int
    stagnation_turns: int

    # ── Interactive Settings ─────────────────────────────────────────────────
    mode: str    # "plan" | "goal" | "read-only"
    access: str  # "auto" | "ask"

    # ── Internal routing signal (read by LangGraph conditional edges) ─────────
    # Values vary per node — see engine.py routing functions
    route: str


def initial_state(run_id: str, goal: str, cfg: dict) -> RunState:
    """Build the starting RunState for a fresh run."""
    engine_cfg = cfg.get("engine", {})
    return RunState(
        run_id=run_id,
        goal=goal,
        remaining_subgoals=[],
        current_subgoal="",
        subgoal_index=0,
        last_observation="",
        correction_hint=None,
        turn_count=0,
        subgoal_turn_count=0,
        tokens_used=0,
        verify_fail_count=0,
        critic_attempted=False,
        action_hash_history=[],
        consecutive_failures=0,
        critic_count=0,
        status="running",
        escalate_reason="",
        is_resuming=False,
        max_turns=engine_cfg.get("max_turns", 50),
        max_tokens=engine_cfg.get("max_tokens", 200000),
        max_turns_per_subgoal=engine_cfg.get("max_turns_per_subgoal", 8),
        max_consecutive_failures=engine_cfg.get("max_consecutive_failures", 3),
        max_critic_invocations=engine_cfg.get("max_critic_invocations", 5),
        stagnation_turns=engine_cfg.get("stagnation_turns", 3),
        mode=engine_cfg.get("default_mode", "goal"),
        access=engine_cfg.get("default_access", "auto"),
        route="",
    )
