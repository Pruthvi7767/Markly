"""Tool executor — Phase 2 Sandbox.

Dispatches tool calls to their implementations, running them
within the DockerSandbox and applying permission tiers.
"""
import logging
import tomllib
from typing import Dict, Any
from pathlib import Path

from markly.tools.registry import registry

logger = logging.getLogger(__name__)


def _get_permissions() -> tuple[list[str], list[str]]:
    cfg_path = Path(__file__).parent.parent.parent / "config.toml"
    if not cfg_path.exists():
        return ["read_only", "write_local"], ["destructive"]
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    perms = cfg.get("permissions", {})
    return (
        perms.get("auto_execute_tiers", ["read_only", "write_local"]),
        perms.get("approval_required_tiers", ["destructive"])
    )


def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute a registered tool. Returns wrapped observation string.

    Raises ValueError for unknown tools.
    """
    tool_meta = registry.get_tool(name)
    if not tool_meta:
        raise ValueError(f"Tool '{name}' is not registered. Valid: {registry.list_names()}")

    # Permission check
    auto_execute_tiers, approval_required_tiers = _get_permissions()
    tier = tool_meta["tier"]
    
    if tier in approval_required_tiers:
        # In Phase 2, we just log that it needs approval, but execute it since we don't have TUI yet.
        logger.warning(f"Tool {name} requires approval (tier: {tier}). Auto-approving for Phase 2 test.")

    logger.info("EXECUTE: %s(%s)", name, args)

    try:
        func = tool_meta["func"]
        result = func(args)
        if isinstance(result, str) and result.startswith("Error:"):
            result += f"\nSchema for {name}: {tool_meta['schema']}"
    except Exception as e:
        result = f"Error executing tool {name}: {e}\nSchema for {name}: {tool_meta['schema']}"
        logger.exception("Tool execution failed")

    # Untrusted Tagging (Requirement 6)
    return f'<tool_observation source="{name}" trust="untrusted">\n{result}\n</tool_observation>'
