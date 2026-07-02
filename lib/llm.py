"""LLM provider abstraction — Groq, Gemini (free tier), or local Ollama."""

from __future__ import annotations

import json
import time
from typing import Literal

import httpx
from groq import Groq

from lib.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    SCRIPT_PROVIDER,
)

Provider = Literal["groq", "gemini", "ollama"]

_PLACEHOLDER_KEYS = {"your_groq_key_here", "your_gemini_key_here", ""}


def _log(msg: str) -> None:
    from datetime import datetime

    print(f"[{datetime.now().strftime('%H:%M:%S')}] llm: {msg}")


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    provider: Provider | None = None,
) -> str:
    """Route a chat completion to the configured script provider."""
    provider = provider or SCRIPT_PROVIDER  # type: ignore[assignment]

    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, max_tokens, temperature)
    if provider == "ollama":
        return _call_ollama(system_prompt, user_prompt, max_tokens, temperature)
    return _call_groq(system_prompt, user_prompt, max_tokens, temperature)


def _call_groq(
    system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
) -> str:
    if not GROQ_API_KEY or GROQ_API_KEY in _PLACEHOLDER_KEYS:
        raise ValueError("GROQ_API_KEY not configured in config.env")
    client = Groq(api_key=GROQ_API_KEY)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            if "rate_limit" in str(exc).lower() and attempt < 2:
                wait = 2 ** attempt * 5
                _log(f"Groq rate limit — retrying in {wait}s")
                time.sleep(wait)
                continue
            raise


def _call_gemini(
    system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
) -> str:
    if not GEMINI_API_KEY or GEMINI_API_KEY in _PLACEHOLDER_KEYS:
        raise ValueError(
            "GEMINI_API_KEY not configured. Get a free key at https://aistudio.google.com/apikey"
        )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload)
        if response.status_code == 429:
            time.sleep(10)
            response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data)[:300]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts)


def _call_ollama(
    system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "format": "json",
    }
    with httpx.Client(timeout=300.0) as client:
        response = client.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")
