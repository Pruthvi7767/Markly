import logging
import os
from pathlib import Path
from typing import Tuple

import docker

logger = logging.getLogger(__name__)


class DockerSandbox:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.client = docker.from_env()
        self.container_name = f"markly_sandbox_{run_id}"
        # We will mount a local workspace dir into the container
        self.workspace_dir = Path(os.getcwd()) / "workspace"
        self.workspace_dir.mkdir(exist_ok=True)
        self.container = None

    def start(self) -> None:
        try:
            self.container = self.client.containers.get(self.container_name)
            if self.container.status != "running":
                self.container.start()
        except docker.errors.NotFound:
            logger.info(f"Starting sandbox container {self.container_name}...")
            self.container = self.client.containers.run(
                "nikolaik/python-nodejs:python3.12-nodejs20",
                name=self.container_name,
                command="tail -f /dev/null",  # Keep alive
                detach=True,
                volumes={
                    str(self.workspace_dir.resolve()): {
                        "bind": "/workspace",
                        "mode": "rw"
                    }
                },
                working_dir="/workspace",
                network_mode="bridge",
                remove=True
            )

    def stop(self) -> None:
        if self.container:
            logger.info(f"Stopping sandbox container {self.container_name}...")
            try:
                self.container.stop(timeout=2)
            except Exception as e:
                logger.error(f"Error stopping container: {e}")

    def execute(self, cmd: str) -> Tuple[int, str]:
        """Returns (exit_code, output)"""
        if not self.container:
            self.start()

        # Run via shell to support piping, env vars, etc.
        result = self.container.exec_run(
            cmd=["/bin/sh", "-c", cmd],
            workdir="/workspace"
        )
        return result.exit_code, result.output.decode('utf-8', errors='replace')

    def write_file(self, path: str, content: str) -> None:
        """Write a file into the local workspace directory (which is mounted into the container)."""
        # Ensure path is treated as relative to workspace
        if path.startswith("/workspace/"):
            path = path[len("/workspace/"):]
        elif path.startswith("/"):
            path = path.lstrip("/")
            
        target = self.workspace_dir / path
        
        # Security check to prevent directory traversal out of workspace
        try:
            target.resolve().relative_to(self.workspace_dir.resolve())
        except ValueError:
            # Revert to a flat file in root of workspace if it tries to escape
            target = self.workspace_dir / Path(path).name

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

    def read_file(self, path: str) -> str:
        if path.startswith("/workspace/"):
            path = path[len("/workspace/"):]
        elif path.startswith("/"):
            path = path.lstrip("/")
            
        target = self.workspace_dir / path
        if not target.exists():
            return f"Error: File {path} not found in workspace."
            
        try:
            with open(target, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {path}: {e}"
