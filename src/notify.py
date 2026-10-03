"""Post the digest text to Discord and/or Slack incoming webhooks.

Each platform caps message length, so long digests are split into chunks on
line boundaries. A platform is skipped when its webhook URL is empty.
"""
from __future__ import annotations

from typing import List, Optional

import requests

DISCORD_LIMIT = 2000
SLACK_LIMIT = 3500


def chunk_text(text: str, limit: int) -> List[str]:
    """Split ``text`` into <=``limit`` chunks, preferring line boundaries."""
    if not text:
        return []
    chunks: List[str] = []
    current = ""
    for line in text.split("\n"):
        # A single over-long line is hard-split.
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else current + "\n" + line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _post_chunks(url, text, limit, payload_key, session):
    post = (session or requests).post
    for chunk in chunk_text(text, limit):
        resp = post(url, json={payload_key: chunk}, timeout=30)
        resp.raise_for_status()


def post_discord(url: str, text: str, session: Optional[requests.Session] = None) -> None:
    _post_chunks(url, text, DISCORD_LIMIT, "content", session)


def post_slack(url: str, text: str, session: Optional[requests.Session] = None) -> None:
    _post_chunks(url, text, SLACK_LIMIT, "text", session)


def notify(
    text: str,
    discord_url: Optional[str] = None,
    slack_url: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> List[str]:
    """Post to whichever webhooks are configured. Returns the platforms posted to."""
    posted: List[str] = []
    if not text:
        return posted
    if discord_url:
        post_discord(discord_url, text, session=session)
        posted.append("discord")
    if slack_url:
        post_slack(slack_url, text, session=session)
        posted.append("slack")
    return posted
