import os
from datetime import datetime, timedelta, timezone

import responses

from src.feed import FEED_URL, fetch_recent, filter_recent, parse_feed

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "feed.xml")
UC = "UC" + "x" * 22
NOW = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)


def _xml():
    with open(FIXTURE, "rb") as f:
        return f.read()


def test_parse_feed_extracts_fields():
    videos = parse_feed(_xml())
    by_id = {v.video_id: v for v in videos}
    assert set(by_id) == {"VID_FRESH", "VID_OLD", "VID_SEEN"}
    fresh = by_id["VID_FRESH"]
    assert fresh.title == "Fresh Video"
    assert fresh.channel_title == "Test Channel"
    assert fresh.url == "https://www.youtube.com/watch?v=VID_FRESH"
    assert fresh.published == datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)


def test_filter_recent_window_and_seen():
    videos = parse_feed(_xml())
    since = NOW - timedelta(hours=24)
    kept = filter_recent(videos, since=since, seen_ids={"VID_SEEN"})
    ids = [v.video_id for v in kept]
    assert ids == ["VID_FRESH"]  # old dropped by window, seen dropped by state


def test_filter_recent_sorted_oldest_first():
    videos = parse_feed(_xml())
    since = NOW - timedelta(days=60)
    kept = filter_recent(videos, since=since)
    assert [v.video_id for v in kept] == ["VID_OLD", "VID_SEEN", "VID_FRESH"]


@responses.activate
def test_fetch_recent_http():
    responses.add(responses.GET, FEED_URL.format(UC), body=_xml(), status=200)
    kept = fetch_recent(UC, since=NOW - timedelta(hours=24), seen_ids={"VID_SEEN"})
    assert [v.video_id for v in kept] == ["VID_FRESH"]
    assert kept[0].channel_id == UC
