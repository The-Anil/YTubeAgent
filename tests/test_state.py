import json
from datetime import datetime, timedelta, timezone

from src.state import State


def test_missing_file_gives_empty_state(tmp_path):
    st = State.load(str(tmp_path / "nope.json"))
    assert len(st) == 0
    assert not st.contains("abc")


def test_round_trip(tmp_path):
    path = str(tmp_path / "s.json")
    st = State()
    st.add("vid1")
    st.add("vid2")
    st.save(path)

    reloaded = State.load(path)
    assert reloaded.contains("vid1")
    assert reloaded.contains("vid2")
    assert len(reloaded) == 2


def test_add_is_idempotent():
    st = State()
    st.add("x")
    st.add("x")
    assert len(st) == 1


def test_legacy_ids_only_file(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"ids": ["old1", "old2"]}), encoding="utf-8")
    st = State.load(str(path))
    assert st.contains("old1") and st.contains("old2")


def test_prune_removes_old_keeps_recent():
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    st = State()
    st.add("old", when=now - timedelta(days=40))
    st.add("fresh", when=now - timedelta(days=5))
    removed = st.prune(max_age_days=30, now=now)
    assert removed == 1
    assert st.contains("fresh")
    assert not st.contains("old")


def test_saved_payload_has_ids_and_ts(tmp_path):
    path = str(tmp_path / "s.json")
    st = State()
    st.add("a", when=datetime(2026, 1, 1, tzinfo=timezone.utc))
    st.save(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["ids"] == ["a"]
    assert "a" in data["ts"]
