"""Post the digest to Discord and/or Slack.

Supports two posting modes per platform (bot token preferred over webhook):

* **Bot token** — Discord ``POST /channels/{id}/messages`` with an
  ``Authorization: Bot <token>`` header; Slack ``chat.postMessage`` with an
  ``Authorization: Bearer xoxb-<token>`` header. Requires the target channel id.
* **Incoming webhook** — a single webhook URL per platform.

Each platform caps message length, so long digests are split into chunks on
line boundaries. A platform is skipped when it has no usable config.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

log = logging.getLogger("ytubeagent.notify")

DISCORD_LIMIT = 2000
SLACK_LIMIT = 3500

DISCORD_API = "https://discord.com/api/v10/channels/{channel_id}/messages"
SLACK_API = "https://slack.com/api/chat.postMessage"


def chunk_text(text: str, limit: int) -> List[str]:
    """Split ``text`` into <=``limit`` chunks, preferring line boundaries."""
    if not text:
        return []
    chunks: List[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # a single over-long line is hard-split
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


# ---- low-level posters ----------------------------------------------------
def post_discord_webhook(url, text, session=None):
    post = (session or requests).post
    for chunk in chunk_text(text, DISCORD_LIMIT):
        post(url, json={"content": chunk}, timeout=30).raise_for_status()


def post_slack_webhook(url, text, session=None):
    post = (session or requests).post
    for chunk in chunk_text(text, SLACK_LIMIT):
        post(url, json={"text": chunk}, timeout=30).raise_for_status()


def post_discord_bot(token, channel_id, text, session=None):
    post = (session or requests).post
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    url = DISCORD_API.format(channel_id=channel_id)
    for chunk in chunk_text(text, DISCORD_LIMIT):
        post(url, json={"content": chunk}, headers=headers, timeout=30).raise_for_status()


def post_slack_bot(token, channel_id, text, session=None):
    post = (session or requests).post
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for chunk in chunk_text(text, SLACK_LIMIT):
        resp = post(SLACK_API, json={"channel": channel_id, "text": chunk},
                    headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            raise RuntimeError(f"Slack API error: {body.get('error')}")


# ---- config + dispatch ----------------------------------------------------
@dataclass
class NotifyConfig:
    discord_bot_token: str = ""
    discord_channel_id: str = ""
    slack_bot_token: str = ""
    slack_channel_id: str = ""
    discord_webhook: str = ""
    slack_webhook: str = ""


def notify(text: str, config: NotifyConfig, session: Optional[requests.Session] = None) -> List[str]:
    """Post the digest via whatever is configured. Returns platforms posted to.

    Per platform, a bot token + channel id takes precedence over a webhook URL.
    Each platform is attempted independently: a failure on one is logged and
    swallowed so the other still goes out and the process exits gracefully even
    when both fail (returns ``[]``).
    """
    posted: List[str] = []
    if not text:
        return posted

    def _try(platform: str, fn) -> None:
        try:
            fn()
            posted.append(platform)
        except Exception as e:  # noqa: BLE001 - never let a webhook abort the run
            log.warning("posting to %s failed: %s", platform, e)

    if config.discord_bot_token and config.discord_channel_id:
        _try("discord", lambda: post_discord_bot(
            config.discord_bot_token, config.discord_channel_id, text, session))
    elif config.discord_webhook:
        _try("discord", lambda: post_discord_webhook(config.discord_webhook, text, session))

    if config.slack_bot_token and config.slack_channel_id:
        _try("slack", lambda: post_slack_bot(
            config.slack_bot_token, config.slack_channel_id, text, session))
    elif config.slack_webhook:
        _try("slack", lambda: post_slack_webhook(config.slack_webhook, text, session))

    return posted
