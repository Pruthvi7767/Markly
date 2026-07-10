import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from markly.tools.skills import SKILLS_DIR, _parse_skill
from markly.llm import call_llm

logger = logging.getLogger(__name__)

ARCHIVE_DIR = SKILLS_DIR.parent / "archived_skills"

def run_curator_pass():
    """
    Background pass to curate skills:
    1. Archive unproven skills older than 30 days or degrading skills.
    2. Consolidate overlapping skills.
    Must never touch `immutable: true` skills.
    """
    if not SKILLS_DIR.exists():
        return
        
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    active_skills = []
    
    for skill_folder in SKILLS_DIR.iterdir():
        if not skill_folder.is_dir():
            continue
            
        skill_md = skill_folder / "SKILL.md"
        if not skill_md.exists():
            continue
            
        skill_data = _parse_skill(skill_md)
        
        # 1. Protect immutable skills
        if skill_data.get("immutable"):
            continue
            
        # 2. Check degrading or old unproven
        status = skill_data.get("status", "unproven")
        mtime = datetime.fromtimestamp(skill_md.stat().st_mtime)
        age_days = (datetime.now() - mtime).days
        
        if status == "degrading":
            logger.info("CURATOR: Archiving degrading skill '%s'", skill_folder.name)
            shutil.move(str(skill_folder), str(ARCHIVE_DIR / skill_folder.name))
            continue
            
        if status == "unproven" and age_days > 30:
            logger.info("CURATOR: Archiving stale unproven skill '%s' (>30 days old)", skill_folder.name)
            shutil.move(str(skill_folder), str(ARCHIVE_DIR / skill_folder.name))
            continue
            
        active_skills.append({
            "name": skill_folder.name,
            "description": skill_data.get("description"),
            "path": skill_folder
        })
        
    # 3. Consolidate Overlapping Skills (LLM Pass)
    if len(active_skills) < 2:
        return
        
    summaries = []
    for s in active_skills:
        summaries.append(f"- {s['name']}: {s['description']}")
    
    summaries_str = "\n".join(summaries)
    
    system_prompt = (
        "You are Markly's Skill Curator. Review the active skills list and identify ONE pair of redundant/overlapping skills.\n"
        "If no overlap exists, output exactly: {\"status\": \"no overlap\"}\n"
        "Otherwise, output valid JSON:\n"
        " - status: \"overlap_found\"\n"
        " - skill_to_keep: \"name of skill to keep\"\n"
        " - skill_to_archive: \"name of skill to archive\""
    )
    
    content, _, _ = call_llm(
        role="curator",
        messages=[{"role": "user", "content": summaries_str}],
        system=system_prompt,
        max_tokens=100
    )
    
    try:
        cs = content.find("{")
        ce = content.rfind("}") + 1
        if cs != -1 and ce > 0:
            import json
            result = json.loads(content[cs:ce])
            if result.get("status") == "overlap_found":
                to_keep = result.get("skill_to_keep")
                to_archive = result.get("skill_to_archive")
                
                # Verify both exist and are mutable
                archive_path = SKILLS_DIR / to_archive
                keep_path = SKILLS_DIR / to_keep
                
                if archive_path.exists() and keep_path.exists():
                    data = _parse_skill(archive_path / "SKILL.md")
                    if not data.get("immutable"):
                        logger.info("CURATOR: Consolidating overlapping skills. Archiving '%s' in favor of '%s'.", to_archive, to_keep)
                        shutil.move(str(archive_path), str(ARCHIVE_DIR / to_archive))
    except Exception as e:
        logger.error("CURATOR overlap check failed: %s", e)
