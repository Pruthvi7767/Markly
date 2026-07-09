"""Tool executor — Phase 1 stub.

Dispatches tool calls to their implementations.
Unknown tool names are caught here as the final safety net
(should already be caught by validate step in engine.py).
"""
import logging
from markly.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def execute_tool(name: str, args: dict) -> str:
    """Execute a registered tool. Returns observation string.

    Raises ValueError for unknown tools — callers must handle this.
    """
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{name}' is not registered. Valid: {list(TOOL_REGISTRY.keys())}")

    logger.info("EXECUTE: %s(%s)", name, args)

    if name == "echo":
        return _echo(args)

    # Unreachable in Phase 1 — all tools must have an implementation
    raise NotImplementedError(f"Tool '{name}' has no executor implementation yet.")


# ─── implementations ──────────────────────────────────────────────────────────

def _echo(args: dict) -> str:
    message = args.get("message", "")
    if not message:
        return "ERROR: echo tool requires a non-empty 'message' argument."
    return f"ECHO: {message}"
