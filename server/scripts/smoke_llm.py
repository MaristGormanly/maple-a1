"""Live smoke test for LLM provider dispatch — calls real APIs.

Hits OpenAI and Gemini directly with a tiny prompt and prints the
response + token usage. Run with:
    cd server && python3 -m scripts.smoke_llm
"""

import asyncio
import sys
import time

from app.services.llm import (
    MODEL_CHAIN,
    ProviderError,
    _call_gemini,
    _call_openai,
    complete,
)


SYSTEM = "You are a terse assistant. Reply in <=8 words."
MESSAGES = [{"role": "user", "content": "Say 'pong' and nothing else."}]


def _direct_openai():
    spec = next(m for m in MODEL_CHAIN if m.provider == "openai")
    print(f"\n--- OpenAI direct: {spec.name} ---")
    t0 = time.monotonic()
    try:
        resp = _call_openai(spec, SYSTEM, MESSAGES, max_tokens=32, temperature=0.0)
        dt = int((time.monotonic() - t0) * 1000)
        print(f"  content       : {resp.content!r}")
        print(f"  input_tokens  : {resp.usage.input_tokens}")
        print(f"  output_tokens : {resp.usage.output_tokens}")
        print(f"  latency_ms    : {dt}")
        return True
    except ProviderError as exc:
        print(f"  ProviderError: {exc}")
    except Exception as exc:
        print(f"  {type(exc).__name__}: {exc}")
    return False


def _direct_gemini():
    spec = next(m for m in MODEL_CHAIN if m.provider == "gemini")
    print(f"\n--- Gemini direct: {spec.name} ---")
    t0 = time.monotonic()
    try:
        resp = _call_gemini(spec, SYSTEM, MESSAGES, max_tokens=32, temperature=0.0)
        dt = int((time.monotonic() - t0) * 1000)
        print(f"  content       : {resp.content!r}")
        print(f"  input_tokens  : {resp.usage.input_tokens}")
        print(f"  output_tokens : {resp.usage.output_tokens}")
        print(f"  latency_ms    : {dt}")
        return True
    except ProviderError as exc:
        print(f"  ProviderError: {exc}")
    except Exception as exc:
        print(f"  {type(exc).__name__}: {exc}")
    return False


async def _via_complete():
    print("\n--- complete() — full chain w/ fallback ---")
    try:
        resp = await complete(SYSTEM, MESSAGES, max_tokens=32, temperature=0.0)
        print(f"  content       : {resp.content!r}")
        print(f"  input_tokens  : {resp.usage.input_tokens}")
        print(f"  output_tokens : {resp.usage.output_tokens}")
        print(f"  latency_ms    : {resp.latency_ms}")
        return True
    except Exception as exc:
        print(f"  {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    ok_g = _direct_gemini()
    ok_o = _direct_openai()
    ok_c = asyncio.run(_via_complete())
    print()
    print("Summary:")
    print(f"  gemini direct : {'OK' if ok_g else 'FAIL'}")
    print(f"  openai direct : {'OK' if ok_o else 'FAIL'}")
    print(f"  complete()    : {'OK' if ok_c else 'FAIL'}")
    return 0 if (ok_g and ok_o and ok_c) else 1


if __name__ == "__main__":
    sys.exit(main())
