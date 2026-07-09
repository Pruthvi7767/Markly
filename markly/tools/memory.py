import os
from pathlib import Path
from sqlalchemy import text
from markly.db.session import get_engine

MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_CAP = 2200
USER_CAP = 1375

def get_fact_store_content() -> str:
    """Reads both MEMORY.md and USER.md to inject into the system prompt."""
    memory_path = MEMORY_DIR / "MEMORY.md"
    user_path = MEMORY_DIR / "USER.md"
    
    memory_content = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
    user_content = user_path.read_text(encoding="utf-8") if user_path.exists() else ""
    
    return f"--- GLOBAL MEMORY ---\n{memory_content}\n\n--- USER PROFILE ---\n{user_content}"


def memory_write(args: dict) -> str:
    """
    Overwrites the specified memory file (either 'memory' or 'user').
    Enforces a strict character cap.
    """
    target = args.get("target")
    content = args.get("content")
    if not target or not content:
        return "ERROR: Missing required arguments 'target' or 'content'."
    if target.lower() not in ("memory", "user"):
        return "ERROR: target must be either 'memory' or 'user'."
        
    cap = MEMORY_CAP if target.lower() == "memory" else USER_CAP
    filename = "MEMORY.md" if target.lower() == "memory" else "USER.md"
    
    if len(content) > cap:
        return f"ERROR: Content length ({len(content)}) exceeds the hard cap of {cap} characters for {target}."
        
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    filepath = MEMORY_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    
    return f"Successfully updated {filename}."


def memory_lookup(args: dict) -> str:
    """
    Looks up episodic memory in Postgres using full-text search.
    Useful for checking if we have failed this exact situation before.
    """
    query = args.get("query")
    if not query:
        return "ERROR: Missing required argument 'query'."
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return "ERROR: DATABASE_URL not set. Episodic memory lookup unavailable."
        
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # plainto_tsquery converts text to a tsquery format (e.g. 'foo' & 'bar')
            # we search the search_vector column we added in alembic
            rows = conn.execute(
                text("""
                    SELECT run_id, turn_number, subgoal, tool_name, verify_score, observation
                    FROM turns
                    WHERE search_vector @@ plainto_tsquery('english', :query)
                    ORDER BY created_at DESC
                    LIMIT 5
                """),
                {"query": query}
            ).fetchall()
            
            if not rows:
                return "No past memories found for this query."
                
            results = []
            for row in rows:
                run_id, turn_num, subgoal, tool_name, verify_score, obs = row
                res = (
                    f"[Run {run_id[:8]} Turn {turn_num}] Score: {verify_score}\n"
                    f"Subgoal: {subgoal}\n"
                    f"Tool: {tool_name}\n"
                    f"Observation: {str(obs)[:300]}..."
                )
                results.append(res)
                
            return "\n\n".join(results)
    except Exception as e:
        return f"ERROR looking up episodic memory: {e}"


def register_memory_tools(registry):
    registry.register(
        name="memory.write",
        category="memory",
        description="Write facts to long-term memory (MEMORY.md or USER.md). Overwrites existing content. Respect the size limits.",
        tier="safe",
        schema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Either 'memory' (global facts) or 'user' (user profile preferences)."
                },
                "content": {
                    "type": "string",
                    "description": "The full markdown content to write to the file."
                }
            },
            "required": ["target", "content"]
        },
        func=memory_write
    )

    registry.register(
        name="memory.lookup",
        category="memory",
        description="Search episodic memory (past runs and turns) for a specific situation, failure, or observation using keywords.",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (keywords describing the situation or tool error)."
                }
            },
            "required": ["query"]
        },
        func=memory_lookup
    )
