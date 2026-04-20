"""Probe alternate auth methods for the AQ.* key against Gemini."""

import asyncio
import httpx
from app.services.llm import settings

KEY = settings.GEMINI_API_KEY
MODEL = "gemini-2.0-flash"

NATIVE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
OAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

NATIVE_BODY = {"contents": [{"parts": [{"text": "Say pong."}]}]}
OAI_BODY = {"model": MODEL, "messages": [{"role": "user", "content": "Say pong."}], "max_tokens": 16}


async def probe(label, url, headers, body, params=None):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, headers=headers, json=body, params=params)
    snippet = r.text.replace("\n", " ")[:180]
    print(f"  [{r.status_code}] {label}")
    print(f"      → {snippet}")


async def main():
    print(f"key prefix: {KEY[:6]}... len={len(KEY)}\n")

    print("=== Native Gemini endpoint ===")
    await probe("?key=<KEY> query param",         NATIVE_URL, {"Content-Type": "application/json"}, NATIVE_BODY, params={"key": KEY})
    await probe("x-goog-api-key header",          NATIVE_URL, {"x-goog-api-key": KEY, "Content-Type": "application/json"}, NATIVE_BODY)
    await probe("Authorization: Bearer header",   NATIVE_URL, {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}, NATIVE_BODY)

    print("\n=== OpenAI-compat endpoint ===")
    await probe("Authorization: Bearer (current)",OAI_URL,    {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}, OAI_BODY)
    await probe("x-goog-api-key header",          OAI_URL,    {"x-goog-api-key": KEY, "Content-Type": "application/json"}, OAI_BODY)
    await probe("?key=<KEY> query param",         OAI_URL,    {"Content-Type": "application/json"}, OAI_BODY, params={"key": KEY})


if __name__ == "__main__":
    asyncio.run(main())
