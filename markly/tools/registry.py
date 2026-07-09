"""Tool registry with progressive disclosure.

Level 0 index (name + category + description) always in context.
Level 1 (full schema) loaded on demand based on Planner's intent.
"""
from typing import Callable, Any, Dict, List, Optional

class ToolRegistry:
    def __init__(self):
        # name -> metadata
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, category: str, description: str, tier: str, schema: dict, func: Callable):
        self.tools[name] = {
            "name": name,
            "category": category,
            "description": description,
            "tier": tier,
            "schema": schema,
            "func": func
        }

    def get_level_0_index(self, restrict_read_only: bool = False) -> str:
        """Returns the base index string to always include in context."""
        if not self.tools:
            return "No tools registered."
        lines = []
        for name, meta in sorted(self.tools.items()):
            if restrict_read_only and meta["tier"] != "read_only":
                continue
            lines.append(f"- {name} [{meta['category']}]: {meta['description']}")
        return "\n".join(lines)

    def get_schemas_for_intent(self, categories: List[str]) -> List[Dict]:
        """Returns full JSON schemas for the requested categories."""
        schemas = []
        for name, meta in self.tools.items():
            if meta["category"] in categories or "all" in categories:
                # Build OpenAI-style tool definition
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": meta["description"],
                        "parameters": meta["schema"]
                    }
                })
        return schemas

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self.tools.get(name)
        
    def list_names(self) -> List[str]:
        return list(self.tools.keys())

# Global registry instance
registry = ToolRegistry()
