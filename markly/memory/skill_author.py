import os
import json
import logging
import threading
from typing import Dict, Any
from sqlalchemy import text
from markly.db.session import get_engine
from markly.llm import call_llm
from markly.tools.skills import SKILLS_DIR

logger = logging.getLogger(__name__)

def evaluate_and_author_skill_bg(run_id: str, state: Dict[str, Any]):
    """
    Launch the authoring pass in a daemon thread.
    Never blocks the main loop.
    """
    t = threading.Thread(
        target=_author_skill_pass,
        args=(run_id, state),
        daemon=True,
        name=f"skill_author_{run_id}"
    )
    t.start()

def _author_skill_pass(run_id: str, state: Dict[str, Any]):
    """
    Background pass: read all turns for this run, check triggers, 
    and ask LLM if anything warrants becoming a reusable skill.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT turn_number, subgoal, tool_name, verify_score FROM turns WHERE run_id = :run_id ORDER BY turn_number ASC"),
                {"run_id": run_id}
            ).fetchall()
        
        if not rows:
            return

        # Trigger check (Requirement 1)
        # 1. a subgoal took 5+ tool calls
        # 2. critic successfully fixed a failure (we approximate by checking if critic_count > 0 in state)
        # 3. user gave explicit correction (escalate)
        
        subgoal_counts = {}
        for r in rows:
            subgoal = r[1]
            subgoal_counts[subgoal] = subgoal_counts.get(subgoal, 0) + 1
            
        took_5_calls = any(count >= 5 for count in subgoal_counts.values())
        critic_used = state.get("critic_count", 0) > 0
        is_escalated = state.get("status") == "waiting_human_review"
        
        if not (took_5_calls or critic_used or is_escalated):
            logger.info("SKILL_AUTHOR: Run %s did not meet trigger conditions. Skipping.", run_id)
            return

        # Format transcript for LLM
        transcript = []
        for r in rows:
            transcript.append(f"Turn {r[0]}: Subgoal: {r[1]}, Tool: {r[2]}, Verify Score: {r[3]}")
        transcript_str = "\n".join(transcript)

        system_prompt = (
            "You are Markly's Autonomous Skill Author. You evaluate a recently completed task transcript.\n"
            "If the agent struggled but eventually succeeded, or discovered a complex multi-step workflow, "
            "you should author a reusable skill to teach future agents how to do it efficiently.\n"
            "If the task was trivial, failed completely without resolution, or didn't contain anything worth saving, output exactly: {\"status\": \"nothing to save\"}\n"
            "Otherwise, output valid JSON with these keys:\n"
            " - status: \"authored\"\n"
            " - name: A short lowercase-with-underscores name for the skill (e.g. 'git_commit_flow')\n"
            " - description: A one-sentence description of when to use this skill.\n"
            " - body: The markdown body of the skill (the instructions for the agent).\n"
            "Do NOT include markdown block backticks around your JSON response."
        )

        user_prompt = f"Run Goal: {state.get('goal')}\nTranscript:\n{transcript_str}\n\nDid anything here deserve becoming a reusable skill? If yes, author it."

        content, _, _, _ = call_llm(
            role="skill_author",
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            max_tokens=2000
        )

        try:
            cs = content.find("{")
            ce = content.rfind("}") + 1
            if cs == -1 or ce == 0:
                logger.info("SKILL_AUTHOR: LLM did not return JSON. Exiting.")
                return
            
            result = json.loads(content[cs:ce])
            if result.get("status") != "authored":
                logger.info("SKILL_AUTHOR: %s", result.get("status", "nothing to save"))
                return
                
            name = result.get("name")
            desc = result.get("description", "")
            body = result.get("body", "")
            
            if not name or not body:
                logger.info("SKILL_AUTHOR: Missing name or body in JSON.")
                return
                
            # Create skill folder
            skill_folder = SKILLS_DIR / name
            skill_folder.mkdir(parents=True, exist_ok=True)
            
            skill_md = skill_folder / "SKILL.md"
            
            # Baseline success rate calculation would normally query historical runs matching this skill domain.
            # For now, we initialize baseline at 50% if unknown.
            baseline = 0.5
            
            frontmatter = (
                f"---\n"
                f"name: {name}\n"
                f"description: {desc}\n"
                f"immutable: false\n"
                f"times_invoked: 0\n"
                f"status: unproven\n"
                f"success_rate_with_skill: 0.0\n"
                f"success_rate_before_skill_existed: {baseline}\n"
                f"avg_iterations_with: 0.0\n"
                f"avg_iterations_before: 0.0\n"
                f"---\n\n"
                f"{body}\n"
            )
            
            skill_md.write_text(frontmatter, encoding="utf-8")
            logger.info("SKILL_AUTHOR: Authored new skill '%s' successfully.", name)

        except json.JSONDecodeError:
            logger.error("SKILL_AUTHOR: Could not parse JSON from LLM: %s", content)

    except Exception as e:
        logger.error("SKILL_AUTHOR error: %s", e)
