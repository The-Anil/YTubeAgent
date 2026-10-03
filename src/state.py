"""Persisted set of already-processed YouTube video IDs.

The on-disk format is JSON:

    {"ids": ["<videoId>", ...], "ts": {"<videoId>": "<iso8601-utc>", ...}}

`ids` is the canonical membership list (used for dedup); `ts` records when each
ID was first seen so old entries can be pruned to cap the file size. A legacy
file containing only `ids` is still readable.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


class State:
    def __init__(self, seen: Optional[Dict[str, str]] = None):
        # maps video id -> ISO8601 UTC timestamp of first sighting
        self._seen: Dict[str, str] = dict(seen or {})

    # ---- construction -----------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "State":
        if not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = data.get("ids", []) or []
        ts = data.get("ts", {}) or {}
        seen = {vid: ts.get(vid, _now().isoformat()) for vid in ids}
        # include any ts-only entries too (defensive)
        for vid, when in ts.items():
            seen.setdefault(vid, when)
        return cls(seen)

    # ---- queries ----------------------------------------------------------
    def contains(self, video_id: str) -> bool:
        return video_id in self._seen

    def __contains__(self, video_id: str) -> bool:
        return self.contains(video_id)

    @property
    def ids(self):
        return set(self._seen)

    def __len__(self) -> int:
        return len(self._seen)

    # ---- mutation ---------------------------------------------------------
    def add(self, video_id: str, when: Optional[datetime] = None) -> None:
        if video_id in self._seen:
            return
        self._seen[video_id] = (when or _now()).isoformat()

    def add_all(self, video_ids: Iterable[str], when: Optional[datetime] = None) -> None:
        for vid in video_ids:
            self.add(vid, when)

    def prune(self, max_age_days: int, now: Optional[datetime] = None) -> int:
        """Drop entries first seen more than ``max_age_days`` ago.

        Returns the number of removed entries. Entries with an unparseable
        timestamp are kept.
        """
        now = now or _now()
        cutoff = now - timedelta(days=max_age_days)
        removed = 0
        for vid, when in list(self._seen.items()):
            try:
                seen_at = datetime.fromisoformat(when)
            except (ValueError, TypeError):
                continue
            if seen_at.tzinfo is None:
                seen_at = seen_at.replace(tzinfo=timezone.utc)
            if seen_at < cutoff:
                del self._seen[vid]
                removed += 1
        return removed

    # ---- persistence ------------------------------------------------------
    def save(self, path: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload = {
            "ids": sorted(self._seen),
            "ts": {vid: self._seen[vid] for vid in sorted(self._seen)},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
