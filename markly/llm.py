"""LLM client — single choke point for all LLM calls.

All Planner, Verifier, and Critic calls go through call_llm().
Never called directly from anything else.

Infrastructure-layer retry (backoff) is invisible to the engine/planner.
Per AGENTS.md Section 6: every external call wrapped in backoff/retry.
"""
import os
import time
import logging
import tomllib
from pathlib import Path
from openai import OpenAI, RateLimitError, APIStatusError, APIConnectionError

logger = logging.getLogger(__name__)

# ─── config ──────────────────────────────────────────────────────────────────

def _load_model_cfg() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            return tomllib.load(f).get("models", {})
    return {}

_MODEL_CFG = _load_model_cfg()

MODEL_PLANNER  = _MODEL_CFG.get("planner",  "mistralai/mistral-large-3-675b-instruct-2512")
MODEL_VERIFIER = _MODEL_CFG.get("verifier", "mistralai/mistral-large-3-675b-instruct-2512")
MODEL_CRITIC   = _MODEL_CFG.get("critic",   "microsoft/phi-4-mini-instruct")
BASE_URL       = _MODEL_CFG.get("base_url", "https://integrate.api.nvidia.com/v1")

_ROLE_TO_MODEL = {
    "planner":  MODEL_PLANNER,
    "verifier": MODEL_VERIFIER,
    "critic":   MODEL_CRITIC,
}

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds; attempts: 2s, 4s, 8s

# ─── client ──────────────────────────────────────────────────────────────────

def _get_client() -> OpenAI:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY is not set. "
            "Add it to your .env file. See .env.example."
        )
    return OpenAI(base_url=BASE_URL, api_key=api_key)


# ─── public interface ─────────────────────────────────────────────────────────

def call_llm(
    role: str,
    messages: list[dict],
    system: str = "",
    max_tokens: int = 512,
) -> tuple[str, int, int]:
    """Call the LLM for the given role.

    Args:
        role: "planner" | "verifier" | "critic"
        messages: list of {role, content} dicts (user/assistant turns)
        system: system prompt string
        max_tokens: max output tokens

    Returns:
        (content: str, tokens_in: int, tokens_out: int)

    Raises:
        RuntimeError if all retries exhausted — never returns silently on failure.
    """
    model = _ROLE_TO_MODEL.get(role, MODEL_PLANNER)
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    client = _get_client()
    last_err: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            content = resp.choices[0].message.content or ""
            tok_in  = resp.usage.prompt_tokens if resp.usage else 0
            tok_out = resp.usage.completion_tokens if resp.usage else 0
            logger.debug("LLM[%s/%s] in=%d out=%d", role, model.split("/")[-1], tok_in, tok_out)
            return content, tok_in, tok_out

        except RateLimitError as e:
            wait = _BACKOFF_BASE ** attempt
            logger.warning("LLM[%s] rate-limited (attempt %d/%d) — waiting %ds", role, attempt, _MAX_RETRIES, wait)
            last_err = e
            time.sleep(wait)

        except (APIStatusError, APIConnectionError) as e:
            wait = _BACKOFF_BASE ** attempt
            logger.warning("LLM[%s] API error %s (attempt %d/%d) — waiting %ds", role, e, attempt, _MAX_RETRIES, wait)
            last_err = e
            time.sleep(wait)

        except Exception as e:
            # Non-retryable — fail immediately with full context
            logger.error("LLM[%s] non-retryable error: %s", role, e)
            raise RuntimeError(f"LLM call failed (role={role}, model={model}): {e}") from e

    raise RuntimeError(
        f"LLM call exhausted {_MAX_RETRIES} retries (role={role}, model={model}). "
        f"Last error: {last_err}"
    )
