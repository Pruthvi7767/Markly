from typing import Dict, Any, Callable
from markly.sandbox import DockerSandbox
from markly.tools.registry import ToolRegistry

def register_core_tools(registry: ToolRegistry, get_sandbox_fn: Callable[[], DockerSandbox]):
    
    def shell_execute(args: Dict[str, Any]) -> str:
        sandbox = get_sandbox_fn()
        cmd = args.get("command")
        if not cmd:
            return "Error: missing 'command'"
        exit_code, output = sandbox.execute(cmd)
        
        # Post-write verification (Requirement 7)
        # Shell commands can fail silently or return bad exit codes. 
        # We capture both and expose them so the LLM can verify.
        if exit_code != 0:
            return f"Command failed with exit code {exit_code}.\nOutput:\n{output}"
            
        return f"Exit code: {exit_code}\nOutput:\n{output}"

    def file_read(args: Dict[str, Any]) -> str:
        sandbox = get_sandbox_fn()
        path = args.get("path")
        if not path:
            return "Error: missing 'path'"
        return sandbox.read_file(path)

    def file_write(args: Dict[str, Any]) -> str:
        sandbox = get_sandbox_fn()
        path = args.get("path") or args.get("filename")
        content = args.get("content")
        if not path or content is None:
            return "Error: missing 'path' or 'content'"
        sandbox.write_file(path, content)
        
        # Post-write verification using standalone verify.check_output
        from markly.tools.verify import check_output
        import json
        res_json = check_output({"check_type": "file_exists", "args": {"path": path}})
        res = json.loads(res_json)
        if not res.get("passed"):
            return f"Error: File write failed verification. {res.get('detail')}"
            
        return f"File {path} successfully written. Verification passed."

    def code_run_python(args: Dict[str, Any]) -> str:
        sandbox = get_sandbox_fn()
        script = args.get("script")
        if not script:
            return "Error: missing 'script'"
        # Write to a temporary file
        sandbox.write_file(".tmp_run.py", script)
        exit_code, output = sandbox.execute("python .tmp_run.py")
        return f"Exit code: {exit_code}\nOutput:\n{output}"

    registry.register(
        name="shell.execute",
        category="shell",
        description="Run a shell command inside the secure sandbox environment. Has full network and filesystem access within the container.",
        tier="destructive",
        schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"}
            },
            "required": ["command"]
        },
        func=shell_execute
    )
    
    registry.register(
        name="file.read",
        category="file",
        description="Read the contents of a file from the sandbox workspace.",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file inside workspace"}
            },
            "required": ["path"]
        },
        func=file_read
    )
    
    registry.register(
        name="file.write",
        category="file",
        description="Write content to a file inside the sandbox workspace. Overwrites if exists.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "content": {"type": "string", "description": "The file content"}
            },
            "required": ["path", "content"]
        },
        func=file_write
    )
    
    registry.register(
        name="code.run_python",
        category="code",
        description="Execute a snippet of Python code in the sandbox and return the output.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "The python code to execute"}
            },
            "required": ["script"]
        },
        func=code_run_python
    )
