# Markly Escalation Report

**Run ID:** `379e79f6-c45f-4e52-aeee-c21c134b74b9`
**Time:** 2026-07-10T03:59:23.981998+00:00
**Reason:** 3 consecutive subgoal failures

## Last 3 Turns

### Turn 1
- **Subgoal:** Run the command mcp.context7.query-docs FastAPI to access the documentation
- **Tool:** `mcp.context7.resolve-library-id`
- **Score:** 20
- **Observation:** <tool_observation source="mcp:context7" trust="untrusted">
Error from tool: [TextContent(type='text', text='MCP error -32602: Input validation error: Invalid arguments for tool resolve-library-id: [\n  {\n    "expected": "string",\n    "code": "invalid_type",\n    "path": [\n      "query"\n    ],\n 

### Turn 2
- **Subgoal:** Search for path parameter definition within the displayed documentation
- **Tool:** `mcp.context7.query-docs`
- **Score:** 20
- **Observation:** <tool_observation source="mcp:context7" trust="untrusted">
Error from tool: [TextContent(type='text', text='MCP error -32602: Input validation error: Invalid arguments for tool query-docs: [\n  {\n    "expected": "string",\n    "code": "invalid_type",\n    "path": [\n      "libraryId"\n    ],\n    "

### Turn 3
- **Subgoal:** Search for path parameter definition within the displayed documentation
- **Tool:** `mcp.context7.resolve-library-id`
- **Score:** 20
- **Observation:** <tool_observation source="mcp:context7" trust="untrusted">
Error from tool: [TextContent(type='text', text='MCP error -32602: Input validation error: Invalid arguments for tool resolve-library-id: [\n  {\n    "expected": "string",\n    "code": "invalid_type",\n    "path": [\n      "libraryName"\n   

## Actions Available

- **Retry:** Re-run from this subgoal via `markly resume 379e79f6-c45f-4e52-aeee-c21c134b74b9`
- **Kill:** `markly kill 379e79f6-c45f-4e52-aeee-c21c134b74b9`
- **Review:** Open the TUI and use the Escalation Review screen.