import os
from pathlib import Path
from markly.tools.registry import registry

SKILLS_DIR = Path(__file__).parent.parent / "memory" / "skills"

def _parse_skill(skill_path: Path) -> dict:
    """Parses a SKILL.md file with YAML frontmatter."""
    content = skill_path.read_text(encoding="utf-8")
    metadata = {}
    body = content
    
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            body = parts[2].strip()
            for line in frontmatter.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if v.lower() == "true":
                        v = True
                    elif v.lower() == "false":
                        v = False
                    metadata[k] = v
                    
    result = dict(metadata)
    result.update({
        "name": metadata.get("name", skill_path.parent.name),
        "description": metadata.get("description", "No description provided."),
        "immutable": metadata.get("immutable", False),
        "body": body
    })
    return result

def get_skills_level_0_index() -> str:
    """Returns a summary index of all available skills for the system prompt."""
    if not SKILLS_DIR.exists():
        return "No skills directory found."
        
    skills = []
    for skill_folder in SKILLS_DIR.iterdir():
        if skill_folder.is_dir():
            skill_md = skill_folder / "SKILL.md"
            if skill_md.exists():
                skill_data = _parse_skill(skill_md)
                
                # Exclude degrading skills from standard index to protect loop
                status = skill_data.get("status", "unproven")
                if status == "degrading":
                    continue
                    
                trust_str = "[VALIDATED]" if status == "validated" else "[UNPROVEN - use cautiously]"
                skills.append(f"- {skill_data['name']} {trust_str}: {skill_data['description']}")
                
    if not skills:
        return "No skills currently available."
        
    return "Available Procedural Skills:\n" + "\n".join(skills)

def skill_view(args: dict) -> str:
    """
    Views the full content of a procedural skill by its name.
    """
    name = args.get("name")
    if not name:
        return "ERROR: Missing required argument 'name'."
    skill_path = SKILLS_DIR / name / "SKILL.md"
    if not skill_path.exists():
        return f"ERROR: Skill '{name}' not found at {skill_path}."
        
    content = skill_path.read_text(encoding="utf-8")
    
    # Increment times_invoked if we can cleanly parse it
    try:
        import re
        if re.search(r"^times_invoked:\s*(\d+)", content, re.MULTILINE):
            new_content = re.sub(
                r"^(times_invoked:\s*)(\d+)", 
                lambda m: f"{m.group(1)}{int(m.group(2)) + 1}", 
                content, 
                count=1, 
                flags=re.MULTILINE
            )
            skill_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not increment times_invoked: %s", e)
        
    return content


def register_skill_tools(registry):
    registry.register(
        name="skill.view",
        category="skills",
        description="Load the full markdown body of a skill. Use this when the level 0 index describes a skill that could help with your current task.",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the skill to view (e.g. 'git_workflow')."
                }
            },
            "required": ["name"]
        },
        func=skill_view
    )
