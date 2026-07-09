"""Markly entry point.

Usage:
    python -m markly "Your goal here"
    python -m markly  (reads MARKLY_GOAL env var)
"""
import logging
import os
import sys
import tomllib
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("markly")


def _load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.toml not found at {cfg_path}")
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def main() -> None:
    cfg = _load_config()

    # If no arguments, start the interactive Textual TUI
    if len(sys.argv) == 1:
        from markly.tui import run_tui
        run_tui(cfg)
    else:
        # Otherwise, run the Typer CLI app
        from markly.cli import app
        app(prog_name="markly")


if __name__ == "__main__":
    main()
