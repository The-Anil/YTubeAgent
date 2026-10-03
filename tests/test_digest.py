from datetime import date

from src.digest import DigestItem, build_digest, group_by_channel


def _items():
    return [
        DigestItem("Chan A", "A1", "http://a/1", "sum a1"),
        DigestItem("Chan B", "B1", "http://b/1", "sum b1"),
        DigestItem("Chan A", "A2", "http://a/2", "sum a2"),
    ]


def test_group_preserves_channel_order_and_groups():
    grouped = group_by_channel(_items())
    names = [name for name, _ in grouped]
    assert names == ["Chan A", "Chan B"]
    assert [v.title for v in grouped[0][1]] == ["A1", "A2"]


def test_build_digest_contains_header_channels_links():
    out = build_digest(_items(), day=date(2026, 1, 31))
    assert "2026-01-31" in out
    assert "3 new videos" in out
    assert "Chan A" in out and "Chan B" in out
    assert "http://a/1" in out and "sum b1" in out
    # Chan A appears once as a header even though it has two videos
    assert out.count("📺 Chan A") == 1


def test_build_digest_singular_count():
    out = build_digest([DigestItem("C", "T", "u", "s")], day=date(2026, 1, 31))
    assert "1 new video)" in out


def test_build_digest_empty():
    assert build_digest([]) == ""
