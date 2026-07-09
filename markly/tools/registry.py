"""Tool registry — Level 0 index (name + description) always in context.
Level 1 (full schema) loaded on demand in Phase 2+.

Phase 1: one stub tool only — proves the loop mechanics.
"""

# Each entry: name → {description, parameters (JSON Schema), tier}
TOOL_REGISTRY: dict[str, dict] = {
    "echo": {
        "description": "Echo the input message back as the observation. Used for testing.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to echo back."}
            },
            "required": ["message"],
        },
        "tier": "read_only",
        "needs_approval": False,
    }
}

# Level 0 index string — always injected into planner prompt
TOOL_INDEX = "\n".join(
    f"- {name}: {meta['description']}"
    for name, meta in TOOL_REGISTRY.items()
)
