"""Git operations tool group — wraps git commands inside sandbox.

Tier rules (AGENTS.md & Phase 11 Prompt):
- git.clone / git.commit: write_local
- git.push / git.pr: destructive (requires approval by default)
"""
import shlex
import logging
from typing import Dict, Any, List
from markly.tools.registry import ToolRegistry
from markly.secrets_manager import get_secret

logger = logging.getLogger(__name__)

def get_sandbox():
    from markly.engine import get_current_sandbox
    return get_current_sandbox()

def git_clone(args: Dict[str, Any]) -> str:
    url = args.get("url")
    path = args.get("path")
    if not url:
        return "Error: missing 'url'"
    
    cmd = f"git clone {shlex.quote(url)}"
    if path:
        cmd += f" {shlex.quote(path)}"
        
    sb = get_sandbox()
    exit_code, output = sb.execute(cmd)
    if exit_code != 0:
        return f"Error: Git clone failed (exit {exit_code}). Output:\n{output}"
    return f"Git clone succeeded. Output:\n{output}"

def git_commit(args: Dict[str, Any]) -> str:
    message = args.get("message")
    files = args.get("files")
    if not message:
        return "Error: missing 'message'"
        
    sb = get_sandbox()
    
    # 1. Add files
    if files:
        if isinstance(files, list):
            add_targets = " ".join(shlex.quote(f) for f in files)
        else:
            add_targets = shlex.quote(str(files))
    else:
        add_targets = "."
        
    exit_code, output = sb.execute(f"git add {add_targets}")
    if exit_code != 0:
        return f"Error: Git add failed. Output:\n{output}"
        
    # 2. Commit
    exit_code, output = sb.execute(f"git commit -m {shlex.quote(message)}")
    if exit_code != 0:
        return f"Error: Git commit failed. Output:\n{output}"
        
    return f"Git commit succeeded. Output:\n{output}"

def git_push(args: Dict[str, Any]) -> str:
    remote = args.get("remote", "origin")
    branch = args.get("branch")
    
    # Determine branch name if not supplied
    sb = get_sandbox()
    if not branch:
        code, out = sb.execute("git branch --show-current")
        branch = out.strip() if code == 0 and out.strip() else "main"
        
    cmd = f"git push {shlex.quote(remote)} {shlex.quote(branch)}"
    exit_code, output = sb.execute(cmd)
    if exit_code != 0:
        return f"Error: Git push failed. Output:\n{output}"
    return f"Git push succeeded. Output:\n{output}"

def git_pr(args: Dict[str, Any]) -> str:
    title = args.get("title")
    body = args.get("body", "")
    base = args.get("base", "main")
    if not title:
        return "Error: missing 'title'"
        
    sb = get_sandbox()
    
    # Determine current branch
    code, out = sb.execute("git branch --show-current")
    head_branch = out.strip() if code == 0 and out.strip() else "main"
    
    # Check for GITHUB_TOKEN
    token = get_secret("GITHUB_TOKEN") or get_secret("GITHUB_API_KEY")
    if token:
        import requests
        # Get repository remote URL to determine owner/repo
        code, remote_url = sb.execute("git remote get-url origin")
        if code == 0 and remote_url.strip():
            url_str = remote_url.strip()
            # Parse owner/repo from URL
            # e.g., https://github.com/owner/repo.git or git@github.com:owner/repo.git
            owner_repo = None
            if "github.com" in url_str:
                parts = url_str.split("github.com")[-1].strip("/:").replace(".git", "").split("/")
                if len(parts) >= 2:
                    owner_repo = f"{parts[0]}/{parts[1]}"
            
            if owner_repo:
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                payload = {
                    "title": title,
                    "body": body,
                    "head": head_branch,
                    "base": base
                }
                api_url = f"https://api.github.com/repos/{owner_repo}/pulls"
                try:
                    resp = requests.post(api_url, json=payload, headers=headers, timeout=10)
                    if resp.status_code in (201, 200):
                        pr_info = resp.json()
                        return f"GitHub Pull Request created successfully: {pr_info.get('html_url')}"
                    else:
                        logger.warning("GitHub API PR creation failed: %s", resp.text)
                except Exception as e:
                    logger.error("Error creating PR via GitHub API: %s", e)
                    
    # Fallback to CLI gh command in container
    exit_code, output = sb.execute(
        f"gh pr create --title {shlex.quote(title)} --body {shlex.quote(body)} --base {shlex.quote(base)}"
    )
    if exit_code != 0:
        return f"Error: Pull Request creation failed. GITHUB_TOKEN API attempt and 'gh' CLI attempt both failed.\nOutput:\n{output}"
    return f"Git Pull Request created successfully via CLI. Output:\n{output}"

def register_git_tools(registry: ToolRegistry):
    registry.register(
        name="git.clone",
        category="git",
        description="Clone a git repository into the sandbox workspace.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Repository URL"},
                "path": {"type": "string", "description": "Optional local directory name to clone into"}
            },
            "required": ["url"]
        },
        func=git_clone
    )
    
    registry.register(
        name="git.commit",
        category="git",
        description="Stage and commit changes inside the sandbox repository.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of files to stage. Defaults to staging all changes."
                }
            },
            "required": ["message"]
        },
        func=git_commit
    )
    
    registry.register(
        name="git.push",
        category="git",
        description="Push commits to a remote git branch. Requires approval.",
        tier="destructive",
        schema={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Remote name (defaults to 'origin')"},
                "branch": {"type": "string", "description": "Branch to push to (defaults to current branch)"}
            }
        },
        func=git_push
    )
    
    registry.register(
        name="git.pr",
        category="git",
        description="Create a pull request on GitHub. Requires approval.",
        tier="destructive",
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "PR Title"},
                "body": {"type": "string", "description": "PR Description body"},
                "base": {"type": "string", "description": "Target branch (defaults to 'main')"}
            },
            "required": ["title"]
        },
        func=git_pr
    )
