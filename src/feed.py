"""Fetch a channel's public RSS feed and pick out recent, unseen videos.

YouTube publishes a keyless Atom feed per channel at
``https://www.youtube.com/feeds/videos.xml?channel_id=UC...`` listing the most
recent ~15 uploads with publish timestamps. We parse it with ``feedparser``,
keep entries published within a time window, and drop ones already processed.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import feedparser
import requests

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class Video:
    video_id: str
    channel_id: str
    channel_title: str
    title: str
    url: str
    published: datetime
    description: str = ""


def _to_utc(struct_time) -> Optional[datetime]:
    if not struct_time:
        return None
    return datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc)


def parse_feed(content) -> List[Video]:
    """Parse raw Atom XML (str/bytes) into ``Video`` objects."""
    parsed = feedparser.parse(content)
    channel_title = parsed.feed.get("title", "") if getattr(parsed, "feed", None) else ""
    channel_id = ""
    if getattr(parsed, "feed", None):
        # feedparser maps <yt:channelId> to yt_channelid
        channel_id = parsed.feed.get("yt_channelid", "") or ""

    videos: List[Video] = []
    for e in parsed.entries:
        vid = e.get("yt_videoid") or ""
        if not vid:
            continue
        published = _to_utc(e.get("published_parsed"))
        if published is None:
            continue
        videos.append(
            Video(
                video_id=vid,
                channel_id=channel_id or e.get("yt_channelid", "") or "",
                channel_title=channel_title or e.get("author", ""),
                title=e.get("title", ""),
                url=e.get("link", f"https://www.youtube.com/watch?v={vid}"),
                published=published,
                description=e.get("summary", "") or "",
            )
        )
    return videos


def filter_recent(
    videos: Iterable[Video],
    since: datetime,
    seen_ids: Optional[Iterable[str]] = None,
) -> List[Video]:
    """Keep videos published at/after ``since`` and not in ``seen_ids``."""
    seen = set(seen_ids or ())
    out = [v for v in videos if v.published >= since and v.video_id not in seen]
    out.sort(key=lambda v: v.published)
    return out


def fetch_recent(
    channel_id: str,
    since: datetime,
    seen_ids: Optional[Iterable[str]] = None,
    session: Optional[requests.Session] = None,
) -> List[Video]:
    """HTTP-fetch a channel feed and return its recent, unseen videos."""
    get = (session or requests).get
    resp = get(FEED_URL.format(channel_id), headers={"User-Agent": _UA}, timeout=20)
    resp.raise_for_status()
    videos = parse_feed(resp.content)
    # The feed omits channel_id in some edge cases; backfill from the argument.
    for v in videos:
        if not v.channel_id:
            v.channel_id = channel_id
    return filter_recent(videos, since=since, seen_ids=seen_ids)
