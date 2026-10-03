from datetime import datetime, timezone

from src import main as main_mod
from src.feed import Video
from src.state import State

NOW = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
UC = "UC" + "x" * 22


def _video(vid, title, pub_hour=11):
    return Video(
        video_id=vid,
        channel_id=UC,
        channel_title="Test Channel",
        title=title,
        url=f"https://www.youtube.com/watch?v={vid}",
        published=datetime(2026, 1, 31, pub_hour, 0, tzinfo=timezone.utc),
    )


def _wire(monkeypatch, videos, shorts=(), fail_ids=()):
    monkeypatch.setattr(main_mod.channels_mod, "resolve_channels",
                        lambda *a, **k: {"@test": UC})
    monkeypatch.setattr(main_mod.feed_mod, "fetch_recent",
                        lambda cid, since, seen_ids=None, **k:
                        [v for v in videos if v.video_id not in set(seen_ids or ())])
    monkeypatch.setattr(main_mod.shorts_mod, "is_short",
                        lambda vid, **k: vid in shorts)

    def fake_transcript(vid):
        if vid in fail_ids:
            raise RuntimeError("boom")
        return "transcript text"
    monkeypatch.setattr(main_mod.transcript_mod, "fetch_transcript", fake_transcript)
    monkeypatch.setattr(main_mod.summarize_mod, "summarize",
                        lambda title, text, **k: f"summary of {title}")
    posted = {}
    monkeypatch.setattr(main_mod.notify_mod, "notify",
                        lambda body, config, **k:
                        posted.update(body=body) or ["discord"])
    return posted


def test_end_to_end_happy_path(tmp_path, monkeypatch):
    state_file = str(tmp_path / "processed.json")
    posted = _wire(monkeypatch, [_video("v1", "Vid One"), _video("v2", "Vid Two")])

    count = main_mod.run(state_file=state_file, now=NOW)
    assert count == 2
    assert "Vid One" in posted["body"] and "Vid Two" in posted["body"]

    # State persisted -> second run finds nothing new (dedup).
    st = State.load(state_file)
    assert st.contains("v1") and st.contains("v2")
    posted2 = _wire(monkeypatch, [_video("v1", "Vid One"), _video("v2", "Vid Two")])
    count2 = main_mod.run(state_file=state_file, now=NOW)
    assert count2 == 0
    assert "body" not in posted2


def test_short_is_skipped_but_marked(tmp_path, monkeypatch):
    state_file = str(tmp_path / "processed.json")
    _wire(monkeypatch, [_video("normal", "Normal"), _video("short1", "Short")],
          shorts={"short1"})
    count = main_mod.run(state_file=state_file, now=NOW)
    assert count == 1
    st = State.load(state_file)
    assert st.contains("short1")  # marked so it isn't rechecked


def test_one_bad_video_does_not_abort(tmp_path, monkeypatch):
    state_file = str(tmp_path / "processed.json")
    _wire(monkeypatch, [_video("good", "Good"), _video("bad", "Bad")],
          fail_ids={"bad"})
    count = main_mod.run(state_file=state_file, now=NOW)
    assert count == 1
    st = State.load(state_file)
    assert st.contains("good")
    assert not st.contains("bad")  # failed -> not marked, retried next run


def test_no_videos_no_post(tmp_path, monkeypatch):
    state_file = str(tmp_path / "processed.json")
    posted = _wire(monkeypatch, [])
    count = main_mod.run(state_file=state_file, now=NOW)
    assert count == 0
    assert "body" not in posted
