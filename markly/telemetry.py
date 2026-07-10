import os
import json
import logging
import urllib.request
import threading
import hashlib
from pathlib import Path
import tomllib
from sqlalchemy import text

from markly.db.session import get_engine
from markly.state import RunState

logger = logging.getLogger(__name__)

TELEMETRY_URL = "https://telemetry.markly.dev/v1/metrics"

def _load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}

def _send_payload_sync(payload: dict) -> None:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
    except Exception as e:
        logger.debug("Telemetry send failed: %s", e)

def send_telemetry(state: RunState) -> None:
    """Asynchronously collect and send anonymous structural metrics if telemetry is enabled."""
    cfg = _load_config()
    if not cfg.get("telemetry", False):
        return

    tool_categories = set()
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            engine = get_engine()
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT DISTINCT tool_name FROM turns WHERE run_id = :run_id AND tool_name IS NOT NULL"),
                    {"run_id": state["run_id"]}
                ).fetchall()
                for (t_name,) in rows:
                    if "." in t_name:
                        tool_categories.add(t_name.split(".")[0])
                    else:
                        tool_categories.add("native")
        except Exception as e:
            logger.debug("Telemetry db fetch failed: %s", e)

    payload = {
        "run_id_hash": hashlib.sha256(state["run_id"].encode()).hexdigest()[:16],
        "status": state["status"],
        "turn_count": state["turn_count"],
        "critic_count": state["critic_count"],
        "consecutive_failures": state["consecutive_failures"],
        "tokens_used": state["tokens_used"],
        "cost_total": state.get("cost_total", 0.0),
        "tool_categories_used": list(tool_categories),
        "infra_profile": cfg.get("infra_profile", "lightweight")
    }

    threading.Thread(target=_send_payload_sync, args=(payload,), daemon=True).start()
