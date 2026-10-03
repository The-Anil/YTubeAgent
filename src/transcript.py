"""Fetch a video's transcript text.

Primary source is ``youtube-transcript-api`` (v1.x instance API). If that yields
nothing (disabled transcripts, rate-limited runner IP, ...) we fall back to
``yt-dlp`` auto-subtitles downloaded as VTT and stripped to plain text. If both
fail the caller gets ``None`` and can degrade to title/description.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import tempfile
from typing import List, Optional

_LANGS = ["en", "en-US", "en-GB"]

_TS_LINE = re.compile(r"-->")
_INLINE_TAG = re.compile(r"<[^>]+>")           # <00:00:00.000>, <c>, </c>
_INDEX_LINE = re.compile(r"^\d+$")


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_vtt(content: str) -> str:
    """Convert WebVTT subtitle text into plain, de-duplicated transcript text."""
    lines: List[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE") or line.startswith("Kind:"):
            continue
        if line.startswith("Language:") or _TS_LINE.search(line) or _INDEX_LINE.match(line):
            continue
        line = _INLINE_TAG.sub("", line).strip()
        if not line:
            continue
        # auto-subs repeat the previous caption as it scrolls; drop consecutive dups
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return _collapse(" ".join(lines))


def _from_api(video_id: str) -> Optional[str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=_LANGS)
    except Exception:
        return None
    parts = []
    for snippet in fetched:
        text = getattr(snippet, "text", None)
        if text is None and isinstance(snippet, dict):
            text = snippet.get("text")
        if text:
            parts.append(text)
    joined = _collapse(" ".join(parts))
    return joined or None


def _from_ytdlp(video_id: str) -> Optional[str]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "%(id)s.%(ext)s")
        try:
            subprocess.run(
                ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
                 "--sub-lang", "en.*", "--sub-format", "vtt", "-o", out, url],
                capture_output=True, text=True, timeout=120,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        vtts = glob.glob(os.path.join(tmp, "*.vtt"))
        if not vtts:
            return None
        with open(vtts[0], "r", encoding="utf-8", errors="ignore") as f:
            return parse_vtt(f.read()) or None


def fetch_transcript(video_id: str) -> Optional[str]:
    """Return transcript text for ``video_id``, or ``None`` if unavailable."""
    return _from_api(video_id) or _from_ytdlp(video_id)
