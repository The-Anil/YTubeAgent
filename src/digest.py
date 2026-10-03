"""Group per-video summaries by channel and render a postable text digest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls
from typing import List, Optional


@dataclass
class DigestItem:
    channel_title: str
    title: str
    url: str
    summary: str


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


def build_digest(items: List[DigestItem], day: Optional[date_cls] = None) -> str:
    """Render grouped summaries into a single plain-text digest body."""
    if not items:
        return ""
    day = day or date_cls.today()
    n = len(items)
    header = f"🎬 YouTube digest — {day.isoformat()} ({n} new video{'s' if n != 1 else ''})"
    blocks = [header]
    for channel, vids in group_by_channel(items):
        lines = [f"\n📺 {channel}"]
        for v in vids:
            lines.append(f"\n• {v.title}\n{v.url}\n{v.summary.strip()}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks).strip()
