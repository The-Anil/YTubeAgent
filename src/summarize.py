"""Summarize a video transcript with a free OpenRouter model."""
from __future__ import annotations

import os
import time
from typing import Optional

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

# Keep the prompt well under the model's context window.
MAX_TRANSCRIPT_CHARS = 12000

_SYSTEM = (
    "You summarize YouTube videos for a daily digest. Be concise and factual. "
    "Reply with a 2-4 sentence summary, then up to 3 '- ' bullet key points. "
    "No preamble, no markdown headers."
)


def truncate(text: str, limit: int = MAX_TRANSCRIPT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " ..."


def _build_prompt(title: str, transcript: str, had_transcript: bool) -> str:
    if had_transcript:
        return (
            f"Video title: {title}\n\n"
            f"Transcript:\n{truncate(transcript)}\n\n"
            "Summarize this video."
        )
    return (
        f"Video title: {title}\n\n"
        f"Only the title/description is available (no transcript):\n{truncate(transcript)}\n\n"
        "Give a best-effort summary from the title/description."
    )


def summarize(
    title: str,
    transcript: Optional[str],
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    session: Optional[requests.Session] = None,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> str:
    """Return a short summary string. Raises ``RuntimeError`` if the key is missing."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    model = model or os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL

    had_transcript = bool(transcript and transcript.strip())
    content = _build_prompt(title, transcript or "", had_transcript)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": content},
        ],
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    post = (session or requests).post

    last_err = None
    for attempt in range(max_retries):
        resp = post(API_URL, json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        if resp.status_code == 429 or resp.status_code >= 500:
            last_err = f"HTTP {resp.status_code}"
            if attempt < max_retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            break  # retries exhausted -> fall through to RuntimeError
        # Non-retryable client error: surface it directly.
        resp.raise_for_status()
        last_err = f"HTTP {resp.status_code}"
    raise RuntimeError(f"OpenRouter request failed after {max_retries} attempts: {last_err}")
