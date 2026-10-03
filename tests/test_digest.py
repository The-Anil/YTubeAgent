from datetime import date

from src.digest import (
    DigestItem,
    build_digest,
    build_discord_embeds,
    channel_color,
    group_by_channel,
)


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


def test_channel_color_stable_and_distinct():
    assert channel_color("Chan A") == channel_color("Chan A")  # stable
    assert channel_color("Chan A") != channel_color("Chan B")  # distinct
    assert 0 <= channel_color("Chan A") <= 0xFFFFFF  # valid RGB int


def test_build_discord_embeds_one_card_per_video():
    embeds = build_discord_embeds(_items())
    assert len(embeds) == 3
    # same-channel cards share color and are adjacent
    assert embeds[0]["color"] == embeds[1]["color"]      # both Chan A
    assert embeds[0]["color"] != embeds[2]["color"]      # Chan B differs
    assert embeds[0]["author"]["name"] == "Chan A"
    assert embeds[0]["title"] == "A1"
    assert embeds[0]["url"] == "http://a/1"
    assert "sum a1" in embeds[0]["description"]


def test_build_discord_embeds_truncates_long_title():
    long_title = "x" * 500
    embeds = build_discord_embeds([DigestItem("C", long_title, "u", "s")])
    assert len(embeds[0]["title"]) <= 256
    assert embeds[0]["title"].endswith("…")
