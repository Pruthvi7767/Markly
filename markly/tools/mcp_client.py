"""MCP Client integration.

Spawns a daemon thread running an asyncio event loop to handle MCP stdio
connections. Exposes a synchronous interface so the Planner can call MCP
tools inside LangGraph's blocking executor.

AGENTS.md Section 6:
- MCP tool results get untrusted tagging.
- Default to approval-required (tier = destructive) unless auto_execute=true.
"""
import asyncio
import logging
import os
import threading
from typing import Any, Dict, List, Optional
import tomllib
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# Background loop for MCP
_mcp_loop: Optional[asyncio.AbstractEventLoop] = None
_mcp_thread: Optional[threading.Thread] = None
_sessions: Dict[str, ClientSession] = {}
_shutdown_events: Dict[str, asyncio.Event] = {}

def _start_loop():
    """Run the asyncio event loop forever in a background thread."""
    global _mcp_loop
    _mcp_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_mcp_loop)
    try:
        _mcp_loop.run_forever()
    except Exception as e:
        logger.error("MCP event loop crashed: %s", e)

def _ensure_loop():
    global _mcp_thread
    if _mcp_thread is None or not _mcp_thread.is_alive():
        _mcp_thread = threading.Thread(target=_start_loop, daemon=True, name="MCP_Loop")
        _mcp_thread.start()
        # Wait briefly for loop to initialize
        while _mcp_loop is None:
            pass

async def _connect_server_async(name: str, config: dict) -> ClientSession:
    """Connect to an MCP server and keep the session alive."""
    command = config.get("command")
    args = config.get("args", [])
    
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=os.environ.copy()
    )

    shutdown_event = asyncio.Event()
    _shutdown_events[name] = shutdown_event

    async def _run_session():
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    _sessions[name] = session
                    logger.info("MCP server '%s' initialized.", name)
                    # Block here to keep the context managers alive
                    await shutdown_event.wait()
                    logger.info("MCP server '%s' shutting down.", name)
        except Exception as e:
            logger.error("MCP server '%s' crashed: %s", name, e)
            if name in _sessions:
                del _sessions[name]

    # Spawn the session runner as a background task on the loop
    asyncio.create_task(_run_session())
    
    # Wait until the session is populated
    while name not in _sessions:
        await asyncio.sleep(0.1)
    
    return _sessions[name]

def connect_server_sync(name: str, config: dict) -> ClientSession:
    """Synchronously connect an MCP server."""
    _ensure_loop()
    assert _mcp_loop is not None
    future = asyncio.run_coroutine_threadsafe(_connect_server_async(name, config), _mcp_loop)
    return future.result(timeout=15.0)

async def _list_tools_async(session: ClientSession):
    return await session.list_tools()

async def _call_tool_async(session: ClientSession, tool_name: str, args: dict):
    return await session.call_tool(tool_name, arguments=args)

def call_tool_sync(server_name: str, tool_name: str, args: dict) -> str:
    """Call an MCP tool synchronously."""
    session = _sessions.get(server_name)
    if not session:
        return f"Error: MCP server {server_name} not connected."
    
    _ensure_loop()
    assert _mcp_loop is not None
    future = asyncio.run_coroutine_threadsafe(_call_tool_async(session, tool_name, args), _mcp_loop)
    try:
        # Default 60-second timeout to prevent deadlocks
        result = future.result(timeout=60.0)
        
        if result.isError:
            error_output = []
            for content in result.content:
                if content.type == "text":
                    error_output.append(content.text)
                else:
                    error_output.append(f"[{content.type} content omitted]")
            return f"Error from tool:\n" + "\n".join(error_output)
        
        # Format the ToolResultContent
        output = []
        for content in result.content:
            if content.type == "text":
                output.append(content.text)
            else:
                output.append(f"[{content.type} content omitted]")
        return "\n".join(output)
    except Exception as e:
        logger.error("MCP tool call failed: %s", e)
        return f"Error calling {tool_name} on {server_name}: {e}"

def register_mcp_tools(registry) -> None:
    """Read config.toml, boot servers, and register their tools."""
    cfg_path = Path(__file__).parent.parent.parent / "config.toml"
    if not cfg_path.exists():
        return
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    
    servers = cfg.get("mcp_servers", {})
    if not servers:
        return

    _ensure_loop()
    assert _mcp_loop is not None

    for server_name, server_cfg in servers.items():
        try:
            logger.info("Initializing MCP server '%s'...", server_name)
            session = connect_server_sync(server_name, server_cfg)
            
            # List tools
            future = asyncio.run_coroutine_threadsafe(_list_tools_async(session), _mcp_loop)
            tools_result = future.result(timeout=10.0)
            
            includes = set(server_cfg.get("tools", {}).get("include", []))
            excludes = set(server_cfg.get("tools", {}).get("exclude", []))
            auto_exec = server_cfg.get("auto_execute", False)
            
            # auto_execute mapping: if false, "destructive" (needs approval).
            # if true, "write_local" (auto_execute_tiers includes this).
            tier = "write_local" if auto_exec else "destructive"

            for tool in tools_result.tools:
                # Include/Exclude filtering BEFORE reaching the index
                if includes and tool.name not in includes:
                    continue
                if excludes and tool.name in excludes:
                    continue
                
                registered_name = f"mcp.{server_name}.{tool.name}"
                
                # Transform MCP inputSchema to OpenAI style
                schema = tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}}

                # Python closure trap - bind server_name and tool.name
                def make_wrapper(s_name, t_name):
                    def wrapper(args: dict) -> str:
                        return call_tool_sync(s_name, t_name, args)
                    return wrapper

                registry.register(
                    name=registered_name,
                    category=f"mcp.{server_name}",
                    description=tool.description or "No description provided.",
                    tier=tier,
                    schema=schema,
                    func=make_wrapper(server_name, tool.name)
                )
            logger.info("Registered MCP tools for '%s'", server_name)
        except Exception as e:
            logger.error("Failed to register MCP server '%s': %s", server_name, e)
