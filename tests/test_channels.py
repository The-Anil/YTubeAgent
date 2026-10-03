import responses

from src import channels
from src.channels import read_channel_file, resolve_entry, resolve_channels

UC = "UC" + "x" * 22
UC2 = "UC" + "y" * 22


def test_read_channel_file_skips_comments_and_blanks(tmp_path):
    p = tmp_path / "channels.txt"
    p.write_text("# comment\n\n@mkbhd\n  @mkbhd  \nUC" + "x" * 22 + "\n", encoding="utf-8")
    entries = read_channel_file(str(p))
    assert entries == ["@mkbhd", UC]  # dedup + trim


def test_resolve_raw_channel_id():
    assert resolve_entry(UC) == UC


def test_resolve_channel_url():
    assert resolve_entry(f"https://www.youtube.com/channel/{UC}") == UC


@responses.activate
def test_resolve_handle_by_scraping():
    responses.add(
        responses.GET,
        "https://www.youtube.com/@mkbhd",
        body=f'<html>... "channelId":"{UC}" ...</html>',
        status=200,
    )
    assert resolve_entry("@mkbhd") == UC


@responses.activate
def test_resolve_handle_falls_back_to_ytdlp(monkeypatch):
    responses.add(responses.GET, "https://www.youtube.com/@ghost", body="no id here", status=200)
    monkeypatch.setattr(channels, "_ytdlp_channel_id", lambda url: UC2)
    assert resolve_entry("@ghost") == UC2


@responses.activate
def test_resolve_channels_uses_and_writes_cache(tmp_path):
    chan = tmp_path / "channels.txt"
    chan.write_text("@mkbhd\n", encoding="utf-8")
    cache = tmp_path / "cache.json"

    responses.add(
        responses.GET,
        "https://www.youtube.com/@mkbhd",
        body=f'"channelId":"{UC}"',
        status=200,
    )
    first = resolve_channels(str(chan), cache_path=str(cache))
    assert first == {"@mkbhd": UC}
    assert cache.exists()

    # Second call: no new HTTP registered — must come from cache.
    responses.reset()
    second = resolve_channels(str(chan), cache_path=str(cache))
    assert second == {"@mkbhd": UC}
