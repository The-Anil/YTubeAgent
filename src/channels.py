"""Read channels.txt and resolve every entry to a YouTube channel id (UC...).

Accepted input forms (one per line; blank lines and ``#`` comments ignored):

* ``UCxxxxxxxxxxxxxxxxxxxxxx``            raw channel id
* ``https://www.youtube.com/channel/UC...``
* ``@handle`` / ``https://www.youtube.com/@handle``
* ``https://www.youtube.com/c/Name`` or ``/user/Name`` (legacy custom URLs)

Handle/custom resolution scrapes the public channel page for the embedded
``"channelId":"UC..."`` (no API key). ``yt-dlp`` is a last-resort fallback.
Resolved mappings are cached so we do not re-scrape every day.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Dict, List, Optional

import requests

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_CHANNEL_ID_RE = re.compile(r"UC[0-9A-Za-z_-]{22}")
_PAGE_ID_RE = re.compile(r'"(?:channelId|externalId)":"(UC[0-9A-Za-z_-]{22})"')


def read_channel_file(path: str) -> List[str]:
    """Return the raw, de-duplicated channel entries from ``path``."""
    entries: List[str] = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in seen:
                seen.add(line)
                entries.append(line)
    return entries


def _channel_url(entry: str) -> str:
    """Build a canonical channel URL for scraping/yt-dlp from any entry."""
    if entry.startswith("http://") or entry.startswith("https://"):
        return entry
    if entry.startswith("@"):
        return f"https://www.youtube.com/{entry}"
    return f"https://www.youtube.com/@{entry.lstrip('@')}"


def _scrape_channel_id(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    get = (session or requests).get
    resp = get(url, headers={"User-Agent": _UA}, timeout=20)
    resp.raise_for_status()
    m = _PAGE_ID_RE.search(resp.text)
    return m.group(1) if m else None


def _ytdlp_channel_id(url: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["yt-dlp", "--skip-download", "--playlist-items", "0",
             "--print", "channel_id", url],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = _CHANNEL_ID_RE.search(out.stdout or "")
    return m.group(0) if m else None


def resolve_entry(entry: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Resolve a single channel entry to its ``UC...`` id, or ``None``."""
    # Already a bare channel id.
    if re.fullmatch(_CHANNEL_ID_RE, entry):
        return entry
    # /channel/UC... URL — id is right there in the path.
    if "/channel/" in entry:
        m = _CHANNEL_ID_RE.search(entry)
        if m:
            return m.group(0)
    url = _channel_url(entry)
    try:
        cid = _scrape_channel_id(url, session=session)
        if cid:
            return cid
    except requests.RequestException:
        pass
    return _ytdlp_channel_id(url)


def resolve_channels(
    path: str,
    cache_path: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, str]:
    """Resolve every entry in ``path`` to a channel id.

    Returns an ordered ``{entry: channel_id}`` map (entries that fail to
    resolve are omitted). Results are cached in ``cache_path`` as JSON.
    """
    cache: Dict[str, str] = {}
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = {}

    result: Dict[str, str] = {}
    changed = False
    for entry in read_channel_file(path):
        cid = cache.get(entry)
        if not cid:
            cid = resolve_entry(entry, session=session)
            if cid:
                cache[entry] = cid
                changed = True
        if cid:
            result[entry] = cid

    if cache_path and changed:
        parent = os.path.dirname(cache_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
            f.write("\n")

    return result
