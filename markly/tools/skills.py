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
                    
    return {
        "name": metadata.get("name", skill_path.parent.name),
        "description": metadata.get("description", "No description provided."),
        "immutable": metadata.get("immutable", False),
        "body": body
    }

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
                skills.append(f"- {skill_data['name']}: {skill_data['description']}")
                
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
        
    return skill_path.read_text(encoding="utf-8")


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
