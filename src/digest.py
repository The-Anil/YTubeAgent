"""Group per-video summaries by channel and render postable digests.

Two renderers:
* ``build_digest`` — a plain-text body (used for Slack and stdout fallback).
* ``build_discord_embeds`` — one compact embed "card" per video, colored per
  channel (color derived from the channel name so it is stable and distinct).
"""
from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass
from datetime import date as date_cls
from typing import List, Optional

# Discord embed field limits.
_TITLE_MAX = 256
_AUTHOR_MAX = 256
_DESC_MAX = 4000  # hard limit 4096; leave headroom


@dataclass
class DigestItem:
    channel_title: str
    title: str
    url: str
    summary: str


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def channel_color(name: str) -> int:
    """Stable, vivid 0xRRGGBB color derived from a channel name."""
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    hue = (int(digest, 16) % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.65)  # fixed L/S -> vivid, readable
    return (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)


def group_by_channel(items: List[DigestItem]) -> "list[tuple[str, list[DigestItem]]]":
    """Group items by channel, preserving first-seen channel order."""
    order: List[str] = []
    groups: dict[str, List[DigestItem]] = {}
    for it in items:
        if it.channel_title not in groups:
            groups[it.channel_title] = []
            order.append(it.channel_title)
        groups[it.channel_title].append(it)
    return [(name, groups[name]) for name in order]


def digest_header(items: List[DigestItem], day: Optional[date_cls] = None) -> str:
    """One-line header, e.g. '🎬 YouTube digest — 2026-10-04 (3 new videos)'."""
    day = day or date_cls.today()
    n = len(items)
    return f"🎬 YouTube digest — {day.isoformat()} ({n} new video{'s' if n != 1 else ''})"


def build_digest(items: List[DigestItem], day: Optional[date_cls] = None) -> str:
    """Render grouped summaries into a single plain-text digest body."""
    if not items:
        return ""
    blocks = [digest_header(items, day)]
    for channel, vids in group_by_channel(items):
        lines = [f"\n📺 {channel}"]
        for v in vids:
            lines.append(f"\n• {v.title}\n{v.url}\n{v.summary.strip()}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks).strip()


def build_discord_embeds(items: List[DigestItem]) -> List[dict]:
    """One compact embed-card per video, colored per channel.

    Cards are ordered so same-channel videos are adjacent and share a color.
    """
    embeds: List[dict] = []
    for channel, vids in group_by_channel(items):
        color = channel_color(channel)
        for v in vids:
            embeds.append({
                "author": {"name": _truncate(channel, _AUTHOR_MAX)},
                "title": _truncate(v.title, _TITLE_MAX),
                "url": v.url,
                "description": _truncate(v.summary, _DESC_MAX),
                "color": color,
            })
    return embeds
