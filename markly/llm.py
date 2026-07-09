"""LLM client — single choke point for all LLM calls.

All Planner, Verifier, and Critic calls go through call_llm().
Never called directly from anything else.

Infrastructure-layer retry (backoff with jitter) is invisible to the engine/planner.
Supports provider fallback if the primary provider fails persistently.
"""
import time
import random
import logging
import tomllib
from pathlib import Path
from openai import OpenAI, RateLimitError, APIStatusError, APIConnectionError

from markly.secrets_manager import get_secret

logger = logging.getLogger(__name__)

# ─── config ──────────────────────────────────────────────────────────────────

def _load_model_cfg() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            return tomllib.load(f).get("models", {})
    return {}

def _load_pricing_cfg() -> dict:
    cfg_path = Path(__file__).parent.parent / "pricing.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            return tomllib.load(f).get("models", {})
    return {}

_MODEL_CFG = _load_model_cfg()
_PRICING_CFG = _load_pricing_cfg()

# Primary (NVIDIA)
MODEL_PLANNER  = _MODEL_CFG.get("planner",  "mistralai/mistral-large-3-675b-instruct-2512")
MODEL_VERIFIER = _MODEL_CFG.get("verifier", "mistralai/mistral-large-3-675b-instruct-2512")
MODEL_CRITIC   = _MODEL_CFG.get("critic",   "microsoft/phi-4-mini-instruct")
BASE_URL       = _MODEL_CFG.get("base_url", "https://integrate.api.nvidia.com/v1")

# Fallback (Groq) - hardcoded for now as per fallback protocol, or can be in config
FALLBACK_BASE_URL = "https://api.groq.com/openai/v1"
FALLBACK_MODELS = {
    "planner": "llama-3.3-70b-versatile",
    "verifier": "llama-3.3-70b-versatile",
    "critic": "llama-3.1-8b-instant"
}

_ROLE_TO_MODEL = {
    "planner":  MODEL_PLANNER,
    "verifier": MODEL_VERIFIER,
    "critic":   MODEL_CRITIC,
}

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds

# Global cost accumulator (in-memory for the current run session)
_SESSION_COST_USD = 0.0
_SESSION_TOKENS = 0

def get_session_cost() -> float:
    return _SESSION_COST_USD

def get_session_tokens() -> int:
    return _SESSION_TOKENS


def _scrub_error(e: Exception) -> str:
    """Ensure API keys are never leaked in error strings."""
    msg = str(e)
    # Import locally to avoid circular dependency if any, or just use get_secret
    from markly.secrets_manager import load_secrets
    secrets = load_secrets()
    for key_val in secrets.values():
        if key_val and len(key_val) > 4:
            msg = msg.replace(key_val, "[REDACTED_SECRET]")
    return msg


# ─── client factory ──────────────────────────────────────────────────────────

def _get_client(provider: str) -> tuple[OpenAI, str]:
    """Return the client and its base URL based on provider."""
    if provider == "nvidia":
        api_key = get_secret("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY is not configured in secrets.")
        return OpenAI(base_url=BASE_URL, api_key=api_key), BASE_URL
    elif provider == "groq":
        api_key = get_secret("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured in secrets.")
        return OpenAI(base_url=FALLBACK_BASE_URL, api_key=api_key), FALLBACK_BASE_URL
    else:
        raise ValueError(f"Unknown provider: {provider}")

def _calculate_cost(model: str, tok_in: int, tok_out: int) -> float:
    if model not in _PRICING_CFG:
        return 0.0
    
    in_rate = _PRICING_CFG[model].get("input_cost_per_m", 0.0) / 1_000_000
    out_rate = _PRICING_CFG[model].get("output_cost_per_m", 0.0) / 1_000_000
    
    return (tok_in * in_rate) + (tok_out * out_rate)


# ─── public interface ─────────────────────────────────────────────────────────

def _attempt_call(
    client: OpenAI, 
    model: str, 
    role: str, 
    messages: list[dict], 
    max_tokens: int,
    provider: str
) -> tuple[str, int, int]:
    """Make the API call with backoff and jitter."""
    last_err: Exception | None = None
    
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            content = resp.choices[0].message.content or ""
            tok_in  = resp.usage.prompt_tokens if resp.usage else 0
            tok_out = resp.usage.completion_tokens if resp.usage else 0
            
            logger.debug("LLM[%s/%s][%s] in=%d out=%d", role, model.split("/")[-1], provider, tok_in, tok_out)
            
            cost = _calculate_cost(model, tok_in, tok_out)
            global _SESSION_COST_USD, _SESSION_TOKENS
            _SESSION_COST_USD += cost
            _SESSION_TOKENS += (tok_in + tok_out)
            
            return content, tok_in, tok_out


        except RateLimitError as e:
            wait = (_BACKOFF_BASE ** attempt) + random.uniform(0, 1)
            logger.warning("LLM[%s][%s] rate-limited (attempt %d/%d) — waiting %.1fs", role, provider, attempt, _MAX_RETRIES, wait)
            last_err = e
            time.sleep(wait)

        except (APIStatusError, APIConnectionError) as e:
            wait = (_BACKOFF_BASE ** attempt) + random.uniform(0, 1)
            logger.warning("LLM[%s][%s] API error %s (attempt %d/%d) — waiting %.1fs", role, provider, _scrub_error(e), attempt, _MAX_RETRIES, wait)
            last_err = e
            time.sleep(wait)

        except Exception as e:
            # Non-retryable
            logger.error("LLM[%s][%s] non-retryable error: %s", role, provider, _scrub_error(e))
            raise RuntimeError(f"LLM call failed (role={role}, model={model}): {_scrub_error(e)}") from e

    raise RuntimeError(
        f"LLM call exhausted {_MAX_RETRIES} retries on {provider} (role={role}, model={model}). "
        f"Last error: {_scrub_error(last_err) if last_err else 'None'}"
    )



def call_llm(
    role: str,
    messages: list[dict],
    system: str = "",
    max_tokens: int = 512,
) -> tuple[str, int, int]:
    """Call the LLM for the given role with automatic fallback.

    Args:
        role: "planner" | "verifier" | "critic"
        messages: list of {role, content} dicts (user/assistant turns)
        system: system prompt string
        max_tokens: max output tokens

    Returns:
        (content: str, tokens_in: int, tokens_out: int)

    Raises:
        RuntimeError if all retries on all configured fallback paths are exhausted.
    """
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)
    
    # Provider chain
    providers = ["nvidia", "groq"]
    last_err: Exception | None = None
    
    for provider in providers:
        try:
            client, _ = _get_client(provider)
        except RuntimeError as e:
            logger.debug("Skipping provider %s: %s", provider, _scrub_error(e))
            continue
            
        model = _ROLE_TO_MODEL.get(role, MODEL_PLANNER) if provider == "nvidia" else FALLBACK_MODELS.get(role)
        if not model:
            continue
            
        try:
            return _attempt_call(client, model, role, full_messages, max_tokens, provider)
        except RuntimeError as e:
            logger.error("Provider %s failed fully: %s. Attempting fallback.", provider, _scrub_error(e))
            last_err = e
            continue
            
    raise RuntimeError(
        f"LLM call failed on all providers (role={role}). Last error: {_scrub_error(last_err) if last_err else 'None'}"
    )
