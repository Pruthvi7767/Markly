"""Notification tools — Phase 11.

- notify.telegram: sends a real message via Telegram Bot API.
- notify.human: generic notification (Telegram if set up, else desktop/console).
"""
import logging
import requests
from typing import Dict, Any
from markly.tools.registry import ToolRegistry
from markly.secrets_manager import get_secret
from markly.notify import _toast

logger = logging.getLogger(__name__)

def send_telegram_msg(token: str, chat_id: str, text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        return resp.status_code in (200, 201)
    except Exception as e:
        logger.error("Failed to deliver Telegram notification: %s", e)
        return False

def notify_telegram(args: Dict[str, Any]) -> str:
    message = args.get("message")
    if not message:
        return "Error: missing 'message'"
        
    token = get_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_secret("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return "Error: Telegram is not configured in the secrets manager. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
        
    if send_telegram_msg(token, chat_id, message):
        return "Telegram notification delivered successfully."
    return "Error: Failed to deliver Telegram notification."

def notify_human(args: Dict[str, Any]) -> str:
    message = args.get("message")
    if not message:
        return "Error: missing 'message'"
        
    # 1. Try Telegram if configured
    token = get_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_secret("TELEGRAM_CHAT_ID")
    if token and chat_id:
        if send_telegram_msg(token, chat_id, message):
            return "Notification delivered to human via Telegram."
            
    # 2. Fallback to desktop toast and print
    _toast(title="Markly Alert", message=message)
    print(f"\n📢 MARKLY ALERT: {message}\n", flush=True)
    return "Notification delivered to human via fallback (desktop/console)."

def register_notify_tools(registry: ToolRegistry):
    registry.register(
        name="notify.telegram",
        category="notify",
        description="Deliver a real-time status update to the configured Telegram channel.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message text to send"}
            },
            "required": ["message"]
        },
        func=notify_telegram
    )
    
    registry.register(
        name="notify.human",
        category="notify",
        description="Alert the human operator via Telegram or fallback desktop/console channels.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The alert message"}
            },
            "required": ["message"]
        },
        func=notify_human
    )
