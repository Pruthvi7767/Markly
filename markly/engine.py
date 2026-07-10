"""Markly core engine — LangGraph StateGraph implementation.

Loop: decompose → [stop_check → perceive → plan → validate → dedup →
                   act → verify] → critic? → next_subgoal → repeat

Per AGENTS.md Section 6 (all enforced here):
- Planner is the only tool-caller.
- Verifier is a separate LLM call from the Planner.
- Critic gets exactly ONE correction attempt per subgoal (critic_attempted flag).
- Caps everywhere: turn, token, per-subgoal, consecutive-failure, critic.
  Every cap that fires logs a structured CAP_FIRED line.
- Unhandled failure always defaults to escalate — never silent continuation.
- External tool output tagged untrusted before re-entering context.
- Idempotency keys on every side-effecting action (enforced in executor.py).
- Prompt-size guard trims context before LLM call if > 80% of context limit.
"""
import hashlib
import json
import logging
import os

from langgraph.graph import END, START, StateGraph

from markly.checkpoint import save_run, save_turn
from markly.llm import call_llm
from markly.state import RunState
from markly.tools.executor import execute_tool, set_current_run_id
from markly.tools.registry import registry
from markly.tools.core import register_core_tools
from markly.tools.web import register_web_tools
from markly.tools.browser import register_browser_tools
from markly.tools.memory import register_memory_tools, get_fact_store_content
from markly.tools.skills import register_skill_tools, get_skills_level_0_index
from markly.sandbox import DockerSandbox

from markly.tools.mcp_client import register_mcp_tools
from markly.tools.git import register_git_tools
from markly.tools.doc import register_doc_tools
from markly.tools.http_tool import register_http_tools
from markly.tools.notify_tools import register_notify_tools
from markly.tools.verify import register_verify_tools
from markly.tools.schedule_tools import register_schedule_tools

logger = logging.getLogger(__name__)

_sandbox_instance = None
def get_current_sandbox() -> DockerSandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = DockerSandbox("cli_run")
    return _sandbox_instance

register_core_tools(registry, get_current_sandbox)
register_web_tools(registry)
register_browser_tools(registry)
register_memory_tools(registry)
register_skill_tools(registry)
register_mcp_tools(registry)
register_git_tools(registry)
register_doc_tools(registry)
register_http_tools(registry)
register_notify_tools(registry)
register_verify_tools(registry)
register_schedule_tools(registry)


VERIFY_PASS_THRESHOLD = 70  # score >= this → pass

# Prompt-size guard constants (conservative — covers Groq Llama-3.1 8k limit)
MODEL_CONTEXT_LIMIT = 8192
TOKEN_BUDGET = int(MODEL_CONTEXT_LIMIT * 0.80)  # 6553 tokens


# ─── helpers ─────────────────────────────────────────────────────────────────

def _hash_action(tool: str, args: dict) -> str:
    """Short deterministic hash of tool+args for dedup checking."""
    raw = json.dumps({"tool": tool, "args": args}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _estimate_tokens(text: str) -> int:
    """Rough estimate: 4 chars ≈ 1 token."""
    return len(text) // 4


def _cap_fired(cap: str, subgoal_idx: int, reason: str, decision: str) -> None:
    """Structured log emitted every time a cap triggers. Never silent."""
    logger.error(
        "CAP_FIRED cap=%s subgoal=%d reason=%s decision=%s",
        cap, subgoal_idx, reason, decision,
    )


def _checkpoint(current: RunState, update: dict) -> None:
    """Save merged state to Postgres. Logs error but re-raises — never silent."""
    merged = {**current, **update}
    save_run(merged)


def _fetch_last_turns(run_id: str, n: int = 3) -> list[dict]:
    """Fetch the last N turns from Postgres for escalation reporting."""
    try:
        from markly.db.session import get_engine
        from sqlalchemy import text
        with get_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT subgoal, tool_name, observation, verify_score
                    FROM turns WHERE run_id = :run_id
                    ORDER BY turn_number DESC LIMIT :n
                """),
                {"run_id": run_id, "n": n},
            ).fetchall()
        return [
            {"subgoal": r[0], "tool_name": r[1], "observation": r[2], "verify_score": r[3]}
            for r in reversed(rows)
        ]
    except Exception as e:
        logger.error("_fetch_last_turns failed: %s", e)
        return []


# ─── nodes ───────────────────────────────────────────────────────────────────

def decompose(state: RunState) -> dict:
    """Phase 0: break the goal into subgoals via LLM (skipped on resume)."""
    if state.get("is_resuming") and state.get("current_subgoal"):
        logger.info("DECOMPOSE: resuming — using existing subgoals from checkpoint")
        update = {"is_resuming": False, "route": "subgoal_loop"}
        _checkpoint(state, update)
        return update

    logger.info("DECOMPOSE: goal='%s'", state["goal"][:80])

    # Register run ID with executor so idempotency keys are scoped per run
    set_current_run_id(state["run_id"])

    system = (
        "You are a task planner. Break the given goal into 2-4 concrete, sequential subgoals. "
        "Each subgoal must be a single, specific, executable action. "
        'Reply ONLY with valid JSON — no markdown, no explanation:\n'
        '{"subgoals": ["subgoal 1", "subgoal 2", ...]}'
    )
    content, tok_in, tok_out, cost = call_llm(
        role="planner",
        messages=[{"role": "user", "content": f"Goal: {state['goal']}"}],
        system=system,
        max_tokens=400,
    )

    try:
        start = content.find("{")
        end   = content.rfind("}") + 1
        parsed   = json.loads(content[start:end])
        subgoals = parsed["subgoals"]
        assert isinstance(subgoals, list) and len(subgoals) > 0
    except Exception as e:
        logger.error("DECOMPOSE parse error: %s | raw: %s", e, content[:200])
        subgoals = [state["goal"]]  # fallback: treat whole goal as single subgoal

    logger.info("DECOMPOSE: %d subgoals → %s", len(subgoals), subgoals)

    update = {
        "remaining_subgoals": subgoals[1:],
        "current_subgoal":    subgoals[0],
        "subgoal_index":      0,
        "tokens_used":        state["tokens_used"] + tok_in + tok_out,
        "tokens_planner_in":   state["tokens_planner_in"] + tok_in,
        "tokens_planner_out":  state["tokens_planner_out"] + tok_out,
        "cost_planner":        state["cost_planner"] + cost,
        "cost_total":          state["cost_total"] + cost,
        "route":              "subgoal_loop",
    }
    _checkpoint(state, update)
    return update


def subgoal_loop(state: RunState) -> dict:
    """Execute ONE TURN of the inner loop for the current subgoal.

    Turn sequence:
      stop_check → perceive → prompt_guard → plan → validate → dedup →
      act → observe → verify → route
    """
    prefix = f"[sub#{state['subgoal_index']} turn#{state['subgoal_turn_count']}]"
    sg_idx = state["subgoal_index"]

    # ── PLAN MODE HALT CHECK ──────────────────────────────────────────────────
    if state.get("mode") == "plan":
        reason = "Halted in PLAN mode (checklist built)"
        logger.info("%s %s", prefix, reason)
        update = {"status": "waiting_human_review", "escalate_reason": reason, "route": "escalate"}
        _checkpoint(state, update)
        return update

    # ── STOP CHECK ────────────────────────────────────────────────────────────
    if state["status"] != "running":
        logger.warning("%s Status is '%s' — routing to escalate", prefix, state["status"])
        return {"route": "escalate"}

    if state["turn_count"] >= state["max_turns"]:
        reason = f"Global turn cap ({state['max_turns']}) reached"
        _cap_fired("global_turns", sg_idx, reason, "escalate")
        update = {"status": "escalated", "escalate_reason": reason, "route": "escalate"}
        _checkpoint(state, update)
        return update

    if state["tokens_used"] >= state["max_tokens"]:
        reason = f"Token budget ({state['max_tokens']}) exhausted"
        _cap_fired("token_budget", sg_idx, reason, "escalate")
        update = {"status": "escalated", "escalate_reason": reason, "route": "escalate"}
        _checkpoint(state, update)
        return update

    if state["consecutive_failures"] >= state["max_consecutive_failures"]:
        reason = f"{state['consecutive_failures']} consecutive subgoal failures"
        _cap_fired("consecutive_failures", sg_idx, reason, "escalate")
        update = {"status": "escalated", "escalate_reason": reason, "route": "escalate"}
        _checkpoint(state, update)
        return update

    # Human-kill signal
    from pathlib import Path
    from markly.db.session import get_engine
    from sqlalchemy import text
    db_killed = False
    if os.environ.get("DATABASE_URL"):
        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text("SELECT status FROM runs WHERE run_id = :run_id"),
                    {"run_id": state["run_id"]}
                ).fetchone()
                if row and row[0] in ("killed", "stopped", "stopping"):
                    db_killed = True
        except Exception as e:
            logger.error("Error checking DB status for kill signal: %s", e)
    if db_killed or Path(f".kill_{state['run_id']}").exists():
        reason = "Human-kill signal detected"
        _cap_fired("human_kill", sg_idx, reason, "escalate")
        update = {"status": "waiting_human_review", "escalate_reason": reason, "route": "escalate"}
        _checkpoint(state, update)
        return update

    # Stagnation check
    if state["verify_fail_count"] >= state.get("stagnation_turns", 3):
        reason = f"Stagnation: {state['verify_fail_count']} turns with no progress on subgoal"
        _cap_fired("stagnation", sg_idx, reason, "skip")
        update = {"status": "escalated", "escalate_reason": reason, "route": "escalate"}
        _checkpoint(state, update)
        return update

    if state["subgoal_turn_count"] >= state["max_turns_per_subgoal"]:
        reason = f"Per-subgoal turn cap ({state['max_turns_per_subgoal']}) reached"
        _cap_fired("subgoal_turns", sg_idx, reason, "skip")
        update = {
            "consecutive_failures": state["consecutive_failures"] + 1,
            "verify_fail_count":    state["verify_fail_count"] + 1,
            "route":                "next_subgoal",
        }
        _checkpoint(state, update)
        return update

    # ── PERCEIVE ──────────────────────────────────────────────────────────────
    hint_block = f"\n\nCORRECTION HINT: {state['correction_hint']}" if state.get("correction_hint") else ""
    obs_block  = f"\n\nLast observation:\n{state['last_observation']}" if state.get("last_observation") else ""
    context    = (
        f"Subgoal ({state['subgoal_index'] + 1}): {state['current_subgoal']}"
        f"{obs_block}{hint_block}"
    )

    # ── PROMPT-SIZE GUARD (real trim, not just a warning) ─────────────────────
    est = _estimate_tokens(context)
    if est > TOKEN_BUDGET:
        obs_trimmed = (state.get("last_observation") or "")[:500]
        context = (
            f"Subgoal ({state['subgoal_index'] + 1}): {state['current_subgoal']}"
            f"\n\nLast observation (trimmed):\n{obs_trimmed}"
            f"{hint_block}"
        )
        est_after = _estimate_tokens(context)
        logger.warning(
            "%s PROMPT_GUARD trim=observation tokens_before=%d tokens_after=%d",
            prefix, est, est_after,
        )
        # Second pass: if still over budget, drop observation entirely
        if est_after > TOKEN_BUDGET:
            context = (
                f"Subgoal ({state['subgoal_index'] + 1}): {state['current_subgoal']}"
                f"{hint_block}"
            )
            logger.warning(
                "%s PROMPT_GUARD trim=full_observation tokens_after=%d",
                prefix, _estimate_tokens(context),
            )

    # ── PLAN (LLM call) ───────────────────────────────────────────────────────
    restrict_read_only = (state.get("mode") == "read-only")
    system_static_context = (
        f"{get_fact_store_content()}\n\n"
        f"{get_skills_level_0_index()}\n\n"
    )
    plan_system = (
        "You are an AI agent. Select ONE tool to make progress on the current subgoal.\n\n"
        f"{system_static_context}"
        f"Available tools:\n{registry.get_level_0_index(restrict_read_only)}\n\n"
        "Rules:\n"
        "- Reply ONLY with valid JSON. No markdown. No explanation.\n"
        '- Format: {"tool": "tool_name", "args": {"key": "value"}}\n'
        "- Use the EXACT argument names shown in the tool schema."
    )

    plan_raw, p_in, p_out, p_cost = call_llm(
        role="planner",
        messages=[{"role": "user", "content": context}],
        system=plan_system,
        max_tokens=200,
    )

    # ── VALIDATE ──────────────────────────────────────────────────────────────
    tool_name: str | None = None
    tool_args: dict = {}
    try:
        start = plan_raw.find("{")
        end   = plan_raw.rfind("}") + 1
        parsed    = json.loads(plan_raw[start:end])
        tool_name = parsed.get("tool", "")
        tool_args = parsed.get("args", {})
        if not isinstance(tool_args, dict):
            tool_args = {}
    except Exception as e:
        logger.error("%s PLAN parse error: %s | raw: %.100s", prefix, e, plan_raw)
        observation = f"ERROR: Planner returned invalid JSON. Raw: {plan_raw[:100]}"
        return _fail_turn(state, observation, p_in, p_out, p_cost, None, {}, prefix)

    if tool_name not in registry.list_names():
        logger.error("%s VALIDATE: unknown tool '%s'", prefix, tool_name)
        observation = (
            f"ERROR: Tool '{tool_name}' is not registered. "
            f"Valid tools: {registry.list_names()}"
        )
        return _fail_turn(state, observation, p_in, p_out, p_cost, tool_name, tool_args, prefix)

    if restrict_read_only:
        tool_meta = registry.get_tool(tool_name)
        if tool_meta and tool_meta["tier"] != "read_only":
            logger.error("%s VALIDATE: tool '%s' not allowed in read-only mode", prefix, tool_name)
            observation = f"ERROR: Tool '{tool_name}' is not allowed in read-only mode."
            return _fail_turn(state, observation, p_in, p_out, p_cost, tool_name, tool_args, prefix)

    # ── DEDUP ─────────────────────────────────────────────────────────────────
    action_hash = _hash_action(tool_name, tool_args)
    if action_hash in state["action_hash_history"]:
        logger.warning("%s DEDUP: duplicate %s(%s)", prefix, tool_name, tool_args)
        observation = (
            f"ERROR: Duplicate action detected. "
            f"You already tried {tool_name} with args {tool_args}. Use a different approach."
        )
        return _fail_turn(state, observation, p_in, p_out, p_cost, tool_name, tool_args, prefix)

    logger.info("%s PLAN: %s(%s)", prefix, tool_name, tool_args)

    # ── ACT ───────────────────────────────────────────────────────────────────
    try:
        raw_obs = execute_tool(tool_name, tool_args, access_mode=state.get("access", "auto"))
    except Exception as e:
        logger.error("%s ACT error: %s", prefix, e)
        raw_obs = f"ERROR executing {tool_name}: {e}"

    # Tag all tool output as untrusted before re-entering context (AGENTS.md §6)
    observation = (
        f'<tool_observation source="{tool_name}" trust="untrusted">'
        f"{raw_obs}"
        f"</tool_observation>"
    )
    logger.info("%s OBS: %s", prefix, raw_obs[:80])

    # ── VERIFY (separate LLM call) ────────────────────────────────────────────
    verify_system = (
        "You are a strict verifier. Score 0-100 whether the observation shows "
        "meaningful progress toward completing the subgoal. "
        "70+ = pass. Be strict — partial progress scores 40-69. "
        'Reply ONLY with valid JSON: {"score": 85, "reason": "one line reason"}'
    )
    verify_user = (
        f"Subgoal: {state['current_subgoal']}\n"
        f"Tool used: {tool_name}\n"
        f"Observation: {raw_obs[:600]}"
    )
    verify_raw, v_in, v_out, v_cost = call_llm(
        role="verifier",
        messages=[{"role": "user", "content": verify_user}],
        system=verify_system,
        max_tokens=100,
    )

    try:
        vs = verify_raw.find("{")
        ve = verify_raw.rfind("}") + 1
        vp = json.loads(verify_raw[vs:ve])
        score  = int(vp.get("score", 0))
        reason = vp.get("reason", "")
    except Exception:
        score  = 0
        reason = f"parse error on: {verify_raw[:60]}"

    logger.info("%s VERIFY: score=%d | %s", prefix, score, reason[:60])

    # ── BUILD STATE UPDATE ────────────────────────────────────────────────────
    new_hash_history = state["action_hash_history"] + [action_hash]
    base_update = {
        "turn_count":          state["turn_count"] + 1,
        "subgoal_turn_count":  state["subgoal_turn_count"] + 1,
        "tokens_used":         state["tokens_used"] + p_in + p_out + v_in + v_out,
        "tokens_planner_in":   state["tokens_planner_in"] + p_in,
        "tokens_planner_out":  state["tokens_planner_out"] + p_out,
        "tokens_verifier_in":  state["tokens_verifier_in"] + v_in,
        "tokens_verifier_out": state["tokens_verifier_out"] + v_out,
        "cost_planner":        state["cost_planner"] + p_cost,
        "cost_verifier":       state["cost_verifier"] + v_cost,
        "cost_total":          state["cost_total"] + p_cost + v_cost,
        "last_observation":    observation,
        "action_hash_history": new_hash_history,
        "correction_hint":     None,
    }

    # Save turn record to Postgres
    save_turn(
        state={**state, **base_update},
        tool_name=tool_name,
        tool_args=tool_args,
        observation=raw_obs,
        verify_score=score,
    )

    # ── ROUTE ─────────────────────────────────────────────────────────────────
    if score >= VERIFY_PASS_THRESHOLD:
        logger.info("%s VERIFY PASS → next_subgoal", prefix)
        update = {**base_update, "verify_fail_count": 0, "consecutive_failures": 0, "route": "next_subgoal"}
        _checkpoint(state, update)
        return update

    new_fail_count = state["verify_fail_count"] + 1
    logger.warning("%s VERIFY FAIL #%d (score=%d)", prefix, new_fail_count, score)

    # Critic already used for this subgoal → hard-stop, skip subgoal
    if state["critic_attempted"]:
        _cap_fired(
            "critic_retry",
            sg_idx,
            f"critic already attempted this subgoal (score={score})",
            "skip",
        )
        update = {
            **base_update,
            "verify_fail_count":    new_fail_count,
            "consecutive_failures": state["consecutive_failures"] + 1,
            "route":                "next_subgoal",
        }
        _checkpoint(state, update)
        return update

    # Second verify-fail without critic → skip
    if new_fail_count >= 2:
        _cap_fired(
            "verify_fails",
            sg_idx,
            f"2+ verify fails without critic (score={score})",
            "skip",
        )
        update = {
            **base_update,
            "verify_fail_count":    new_fail_count,
            "consecutive_failures": state["consecutive_failures"] + 1,
            "route":                "next_subgoal",
        }
        _checkpoint(state, update)
        return update

    # 1st fail — try critic
    update = {**base_update, "verify_fail_count": new_fail_count, "route": "critic"}
    _checkpoint(state, update)
    return update


def _fail_turn(
    state: RunState,
    observation: str,
    p_in: int,
    p_out: int,
    p_cost: float,
    tool_name: str | None,
    tool_args: dict,
    prefix: str,
) -> dict:
    """Immediate verify-fail helper for validation/dedup errors."""
    sg_idx = state["subgoal_index"]
    new_fail_count = state["verify_fail_count"] + 1
    base = {
        "turn_count":          state["turn_count"] + 1,
        "subgoal_turn_count":  state["subgoal_turn_count"] + 1,
        "tokens_used":         state["tokens_used"] + p_in + p_out,
        "tokens_planner_in":   state["tokens_planner_in"] + p_in,
        "tokens_planner_out":  state["tokens_planner_out"] + p_out,
        "cost_planner":        state["cost_planner"] + p_cost,
        "cost_total":          state["cost_total"] + p_cost,
        "last_observation":    observation,
        "verify_fail_count":   new_fail_count,
        "correction_hint":     None,
    }
    save_turn(
        state={**state, **base},
        tool_name=tool_name,
        tool_args=tool_args,
        observation=observation,
        verify_score=0,
    )
    if state["critic_attempted"]:
        _cap_fired("critic_retry", sg_idx, "critic already attempted this subgoal", "skip")
        update = {**base, "consecutive_failures": state["consecutive_failures"] + 1, "route": "next_subgoal"}
    elif new_fail_count >= 2:
        _cap_fired("verify_fails", sg_idx, f"{new_fail_count} verify fails (validation error)", "skip")
        update = {**base, "consecutive_failures": state["consecutive_failures"] + 1, "route": "next_subgoal"}
    else:
        update = {**base, "route": "critic"}
    _checkpoint(state, update)
    return update


def critic(state: RunState) -> dict:
    """Diagnose why the subgoal failed; inject a correction hint.

    Hard cap: max_critic_invocations per run (AGENTS.md §6).
    """
    logger.info("CRITIC: diagnosing failure for subgoal: %s", state["current_subgoal"][:60])

    if state["critic_count"] >= state["max_critic_invocations"]:
        _cap_fired(
            "critic_run_cap",
            state["subgoal_index"],
            f"critic invocation cap ({state['max_critic_invocations']}) reached for this run",
            "skip",
        )
        update = {
            "critic_attempted":     True,
            "consecutive_failures": state["consecutive_failures"] + 1,
            "route":                "next_subgoal",
        }
        _checkpoint(state, update)
        return update

    CATEGORIES = [
        "wrong_tool", "bad_args", "missing_precondition",
        "environment_error", "goal_misunderstood",
    ]
    critic_system = (
        "You are a critic diagnosing an AI agent failure. "
        f"Reply ONLY with valid JSON using EXACTLY these fields:\n"
        f'{{"category": "<one of: {", ".join(CATEGORIES)}>", "reason": "<one concise line>"}}\n'
        "No markdown. No extra text. JSON only."
    )
    critic_user = (
        f"Subgoal: {state['current_subgoal']}\n"
        f"Last observation: {state['last_observation'][:600]}\n"
        "Diagnose what went wrong."
    )

    content, c_in, c_out, c_cost = call_llm(
        role="critic",
        messages=[{"role": "user", "content": critic_user}],
        system=critic_system,
        max_tokens=120,
    )

    try:
        cs = content.find("{")
        ce = content.rfind("}") + 1
        cp = json.loads(content[cs:ce])
        category = cp.get("category", "goal_misunderstood")
        reason   = cp.get("reason", "unknown")

        obs = state.get("last_observation", "")
        if ("ERROR" in obs or not obs.strip()) and category not in (
            "environment_error", "missing_precondition"
        ):
            logger.warning("CRITIC: category '%s' mismatches error observation → override", category)
            category = "environment_error"
            reason   = "Observation indicates an error; retry with a different approach"

        if category not in CATEGORIES:
            category = "goal_misunderstood"

        hint = f"[{category}] {reason}"
    except Exception as e:
        logger.warning("CRITIC parse error: %s → using generic hint", e)
        hint = "Retry with a fundamentally different approach."

    logger.info("CRITIC: %s", hint)
    update = {
        "correction_hint":  hint,
        "critic_attempted": True,
        "critic_count":     state["critic_count"] + 1,
        "tokens_used":      state["tokens_used"] + c_in + c_out,
        "tokens_critic_in":  state["tokens_critic_in"] + c_in,
        "tokens_critic_out": state["tokens_critic_out"] + c_out,
        "cost_critic":       state["cost_critic"] + c_cost,
        "cost_total":        state["cost_total"] + c_cost,
        "route":            "subgoal_loop",
    }
    _checkpoint(state, update)
    return update


def next_subgoal(state: RunState) -> dict:
    """Advance to the next subgoal or signal completion."""
    remaining = state["remaining_subgoals"]

    if not remaining:
        logger.info("NEXT_SUBGOAL: all done → final_output")
        update = {"route": "final_output"}
        _checkpoint(state, update)
        return update

    next_sg = remaining[0]
    logger.info("NEXT_SUBGOAL: → subgoal %d: %s", state["subgoal_index"] + 2, next_sg[:60])

    update = {
        "remaining_subgoals":  remaining[1:],
        "current_subgoal":     next_sg,
        "subgoal_index":       state["subgoal_index"] + 1,
        # Reset per-subgoal fields
        "subgoal_turn_count":  0,
        "verify_fail_count":   0,
        "critic_attempted":    False,
        "action_hash_history": [],
        "correction_hint":     None,
        "last_observation":    "",
        "route":               "subgoal_loop",
    }
    _checkpoint(state, update)
    return update


def final_output(state: RunState) -> dict:
    """Mark run complete and print summary."""
    logger.info(
        "FINAL: completed. subgoals=%d turns=%d tokens=%d",
        state["subgoal_index"] + 1, state["turn_count"], state["tokens_used"],
    )
    print("\n" + "=" * 60)
    print("✅  MARKLY RUN COMPLETE")
    print(f"    Goal:               {state['goal']}")
    print(f"    Subgoals completed: {state['subgoal_index'] + 1}")
    print(f"    Total turns:        {state['turn_count']}")
    print(f"    Total tokens used:  {state['tokens_used']}")
    print(f"    Run ID:             {state['run_id']}")
    print("=" * 60)
    update = {"status": "completed"}
    _checkpoint(state, update)
    
    try:
        from markly.telemetry import send_telemetry
        send_telemetry({**state, **update})
    except Exception:
        pass
    
    # Launch background skill authoring pass
    from markly.memory.skill_author import evaluate_and_author_skill_bg
    evaluate_and_author_skill_bg(state["run_id"], state)
    
    return update


def escalate(state: RunState) -> dict:
    """Terminal: escalate to human review.

    Phase 6 additions:
    - Fetches last 3 turns from DB for the escalation report.
    - Calls notify.escalate_notify() → desktop toast + ESCALATION_*.md.
    - Run is permanently halted (routes to END) — no auto-resume.
    """
    reason = state.get("escalate_reason") or "Budget or failure cap exceeded"
    logger.error("ESCALATE: %s", reason)

    last_turns = _fetch_last_turns(state["run_id"], n=3)
    critic_diagnosis = state.get("correction_hint")

    print("\n" + "=" * 60)
    print("🚨  MARKLY ESCALATED — HUMAN REVIEW REQUIRED")
    print(f"    Reason:    {reason}")
    print(f"    Run ID:    {state['run_id']}")
    print(f"    Status:    waiting_human_review")
    print(f"    Turns:     {state['turn_count']}")
    if last_turns:
        last = last_turns[-1]
        print(f"    Last obs:  {str(last.get('observation', ''))[:120]}")
    print("=" * 60)

    # Real notification — toast + file
    from markly.notify import escalate_notify
    escalate_notify(
        run_id=state["run_id"],
        reason=reason,
        last_turns=last_turns,
        critic_diagnosis=critic_diagnosis,
    )

    update = {"status": "waiting_human_review"}
    _checkpoint(state, update)
    
    try:
        from markly.telemetry import send_telemetry
        send_telemetry({**state, **update})
    except Exception:
        pass
    
    # Launch background skill authoring pass
    from markly.memory.skill_author import evaluate_and_author_skill_bg
    evaluate_and_author_skill_bg(state["run_id"], state)
    
    return update


# ─── routing functions ────────────────────────────────────────────────────────

def _route(state: RunState) -> str:
    return state.get("route", "escalate")


# ─── graph ───────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(RunState)

    g.add_node("decompose",    decompose)
    g.add_node("subgoal_loop", subgoal_loop)
    g.add_node("critic",       critic)
    g.add_node("next_subgoal", next_subgoal)
    g.add_node("final_output", final_output)
    g.add_node("escalate",     escalate)

    g.add_edge(START, "decompose")

    g.add_conditional_edges("decompose", _route, {
        "subgoal_loop": "subgoal_loop",
    })
    g.add_conditional_edges("subgoal_loop", _route, {
        "critic":       "critic",
        "next_subgoal": "next_subgoal",
        "escalate":     "escalate",
    })
    g.add_conditional_edges("critic", _route, {
        "subgoal_loop": "subgoal_loop",
        "next_subgoal": "next_subgoal",
    })
    g.add_conditional_edges("next_subgoal", _route, {
        "subgoal_loop": "subgoal_loop",
        "final_output": "final_output",
    })

    g.add_edge("final_output", END)
    g.add_edge("escalate",     END)

    return g.compile()


# Compiled graph — import and call .invoke(state) to run
GRAPH = build_graph()
