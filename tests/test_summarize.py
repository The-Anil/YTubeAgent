import pytest
import responses

from src import summarize as S
from src.summarize import API_URL, DEFAULT_MODEL, summarize, truncate


def _ok_body(text="A summary.\n- point"):
    return {"choices": [{"message": {"content": text}}]}


def test_truncate_shortens_long_text():
    out = truncate("x " * 10000, limit=100)
    assert len(out) <= 110
    assert out.endswith("...")


def test_truncate_keeps_short_text():
    assert truncate("short") == "short"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        summarize("title", "transcript")


@responses.activate
def test_summarize_success_sends_model_and_returns_text():
    responses.add(responses.POST, API_URL, json=_ok_body("Hello summary"), status=200)
    out = summarize("My Title", "the transcript", api_key="k")
    assert out == "Hello summary"
    sent = responses.calls[0].request
    assert DEFAULT_MODEL.encode() in sent.body
    assert b"Bearer k" in sent.headers["Authorization"].encode()


@responses.activate
def test_summarize_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(S.time, "sleep", lambda *_: None)  # no real waiting
    responses.add(responses.POST, API_URL, json={"e": 1}, status=429)
    responses.add(responses.POST, API_URL, json=_ok_body("recovered"), status=200)
    out = summarize("t", "x", api_key="k", backoff=0)
    assert out == "recovered"
    assert len(responses.calls) == 2


@responses.activate
def test_summarize_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(S.time, "sleep", lambda *_: None)
    responses.add(responses.POST, API_URL, json={"e": 1}, status=500)
    responses.add(responses.POST, API_URL, json={"e": 1}, status=500)
    with pytest.raises(RuntimeError, match="failed after"):
        summarize("t", "x", api_key="k", max_retries=2, backoff=0)


@responses.activate
def test_no_transcript_uses_best_effort_prompt():
    responses.add(responses.POST, API_URL, json=_ok_body(), status=200)
    summarize("Title Only", None, api_key="k")
    body = responses.calls[0].request.body
    assert b"no transcript" in body
