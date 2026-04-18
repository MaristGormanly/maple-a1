"""
LLM service layer for MAPLE A1.

Milestone 1 scope: Regex Redactor that strips secrets and PII before any
data leaves the system to an external LLM API.

Milestone 3 scope (stub only): complete() LLM call wrapper with retry,
fallback, structured logging, and cost tracking per Architecture Guide §4.
"""

import asyncio
import json
import logging
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("github_pat", re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"), "[REDACTED_GITHUB_PAT]"),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
]

_ENV_VALUE_PATTERN = re.compile(r"([A-Z][A-Z_]{2,}=)(\S+)")


def redact(text: str) -> str:
    """Apply all redaction patterns to a string, replacing matches with
    typed placeholder tokens."""
    for _name, pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    text = _ENV_VALUE_PATTERN.sub(r"\1[REDACTED_ENV_VALUE]", text)
    return text


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact all string values in a nested dict."""
    result = deepcopy(data)
    _redact_recursive(result)
    return result


def _redact_recursive(obj: Any) -> None:
    if isinstance(obj, dict):
        for key in obj:
            if isinstance(obj[key], str):
                obj[key] = redact(obj[key])
            elif isinstance(obj[key], (dict, list)):
                _redact_recursive(obj[key])
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                obj[i] = redact(item)
            elif isinstance(item, (dict, list)):
                _redact_recursive(item)


# ---------------------------------------------------------------------------
# Milestone 3 stubs -- LLM call wrapper
# ---------------------------------------------------------------------------

@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage
    latency_ms: int


# ---------------------------------------------------------------------------
# Model chain and provider dispatch
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    name: str
    provider: str


MODEL_CHAIN: list[ModelSpec] = [
    ModelSpec(name="gemini-3.1-pro-preview", provider="gemini"),
    ModelSpec(name="gemini-3.1-flash-lite", provider="gemini"),
    ModelSpec(name="gpt-4o", provider="openai"),
]


class ProviderError(Exception):
    pass


class EvaluationFailedError(Exception):
    pass


def _call_gemini(
    spec: ModelSpec,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> LLMResponse:
    from openai import OpenAI
    from server.app.config import settings as _settings
    if not _settings.GEMINI_API_KEY:
        raise ProviderError("GEMINI_API_KEY not configured")
    client = OpenAI(
        api_key=_settings.GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    resp = client.chat.completions.create(
        model=spec.name,
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = resp.choices[0].message.content or ""
    usage = LLMUsage(
        input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
        output_tokens=resp.usage.completion_tokens if resp.usage else 0,
        cost_usd=0.0,
    )
    return LLMResponse(content=content, usage=usage, latency_ms=0)


def _call_openai(
    spec: ModelSpec,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> LLMResponse:
    from openai import OpenAI
    from server.app.config import settings as _settings
    if not _settings.OPENAI_API_KEY:
        raise ProviderError("OPENAI_API_KEY not configured")
    client = OpenAI(api_key=_settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=spec.name,
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = resp.choices[0].message.content or ""
    usage = LLMUsage(
        input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
        output_tokens=resp.usage.completion_tokens if resp.usage else 0,
        cost_usd=0.0,
    )
    return LLMResponse(content=content, usage=usage, latency_ms=0)


def _dispatch(
    spec: ModelSpec,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> LLMResponse:
    if spec.provider == "gemini":
        return _call_gemini(spec, system, messages, max_tokens, temperature)
    if spec.provider == "openai":
        return _call_openai(spec, system, messages, max_tokens, temperature)
    raise ProviderError(f"Unknown provider: {spec.provider}")


async def complete(
    system_prompt: str,
    messages: list[dict],
    *,
    complexity: Literal["standard", "complex"] = "standard",
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> LLMResponse:
    """Send a completion request to the configured LLM provider.

    Walks MODEL_CHAIN; each model gets LLM_MAX_RETRIES attempts with
    exponential backoff. Raises EvaluationFailedError if all models
    are exhausted.
    """
    from server.app.config import settings

    timeout = (
        settings.LLM_TIMEOUT_COMPLEX
        if complexity == "complex"
        else settings.LLM_TIMEOUT_STANDARD
    )
    max_retries = settings.LLM_MAX_RETRIES
    backoff_base = settings.LLM_BACKOFF_BASE

    safe_system = redact(system_prompt)
    safe_messages = [redact_dict(m) for m in messages]

    for spec in MODEL_CHAIN:
        for attempt in range(1, max_retries + 1):
            t0 = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        _dispatch,
                        spec, safe_system, safe_messages, max_tokens, temperature,
                    ),
                    timeout=timeout,
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    json.dumps(
                        {
                            "event": "llm_call",
                            "model": spec.name,
                            "attempt": attempt,
                            "latency_ms": latency_ms,
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens,
                            "status": "ok",
                        }
                    )
                )
                return LLMResponse(
                    content=response.content,
                    usage=response.usage,
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                latency_ms = int((time.monotonic() - t0) * 1000)
                error_type = type(exc).__name__
                if attempt < max_retries:
                    logger.warning(
                        json.dumps(
                            {
                                "event": "llm_retry",
                                "model": spec.name,
                                "attempt": attempt,
                                "latency_ms": latency_ms,
                                "error_type": error_type,
                                "status": "retry",
                            }
                        )
                    )
                    sleep_secs = backoff_base * (2 ** (attempt - 1))
                    await asyncio.sleep(sleep_secs)
                else:
                    # Final attempt for this model also failed — log and move on.
                    logger.warning(
                        json.dumps(
                            {
                                "event": "llm_retry",
                                "model": spec.name,
                                "attempt": attempt,
                                "latency_ms": latency_ms,
                                "error_type": error_type,
                                "status": "retry",
                            }
                        )
                    )

        logger.error(
            json.dumps({"event": "llm_model_exhausted", "model": spec.name})
        )

    raise EvaluationFailedError("all LLM models exhausted retries")
