"""Diagnose the Gemini 'Multiple authentication credentials' error.

Tries three transports against the same endpoint + key:
  (1) raw httpx with only Bearer header
  (2) openai SDK default
  (3) openai SDK with explicit empty default_headers + default_query
"""

import asyncio
import httpx
from app.services.llm import settings

BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
KEY = settings.GEMINI_API_KEY
MODELS_TO_TRY = [
    "gemini-3.1-pro-preview",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
]
PAYLOAD = {
    "model": "PLACEHOLDER",
    "messages": [{"role": "user", "content": "Say pong."}],
    "max_tokens": 16,
}


async def raw_httpx(model: str):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{BASE}/chat/completions",
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
            json={**PAYLOAD, "model": model},
        )
    return r.status_code, r.text[:200]


def via_openai_sdk(model: str):
    from openai import OpenAI
    try:
        client = OpenAI(api_key=KEY, base_url=BASE + "/")
        r = client.chat.completions.create(model=model, messages=PAYLOAD["messages"], max_tokens=16)
        return 200, r.choices[0].message.content
    except Exception as e:
        return type(e).__name__, str(e)[:200]


async def main():
    print(f"key prefix: {KEY[:8]}... len={len(KEY)}\n")
    for m in MODELS_TO_TRY:
        print(f"--- model: {m} ---")
        s, t = await raw_httpx(m)
        print(f"  raw httpx     : {s} | {t}")
        s, t = via_openai_sdk(m)
        print(f"  openai SDK    : {s} | {t}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
