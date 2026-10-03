"""Detect YouTube Shorts via the ``/shorts/<id>`` redirect behaviour.

Requesting ``https://www.youtube.com/shorts/<id>`` without following redirects:

* HTTP ``200``  -> the video really is a Short.
* HTTP ``30x``  -> it is a normal video (YouTube redirects to ``/watch?v=``).

On any network error we *keep* the video (return ``False``) so a flaky check
never silently drops a real upload.
"""
from __future__ import annotations

from typing import Optional

import requests

SHORTS_URL = "https://www.youtube.com/shorts/{}"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def is_short(video_id: str, session: Optional[requests.Session] = None) -> bool:
    get = (session or requests).get
    try:
        resp = get(
            SHORTS_URL.format(video_id),
            headers={"User-Agent": _UA},
            allow_redirects=False,
            timeout=20,
        )
    except requests.RequestException:
        return False  # fail open: treat as a normal video
    return resp.status_code == 200
