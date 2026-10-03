import json

import responses

from src.notify import chunk_text, notify

DISCORD = "https://discord.test/webhook"
SLACK = "https://slack.test/webhook"


def test_chunk_text_respects_limit_on_line_boundaries():
    text = "\n".join(["line%d" % i for i in range(10)])
    chunks = chunk_text(text, limit=20)
    assert all(len(c) <= 20 for c in chunks)
    assert "\n".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_chunk_text_hard_splits_overlong_line():
    chunks = chunk_text("x" * 50, limit=20)
    assert all(len(c) <= 20 for c in chunks)
    assert "".join(chunks) == "x" * 50


def test_chunk_text_empty():
    assert chunk_text("", 100) == []


@responses.activate
def test_notify_posts_to_both_with_correct_payload_keys():
    responses.add(responses.POST, DISCORD, status=204)
    responses.add(responses.POST, SLACK, status=200)
    posted = notify("hello digest", discord_url=DISCORD, slack_url=SLACK)
    assert posted == ["discord", "slack"]
    bodies = [json.loads(c.request.body) for c in responses.calls]
    assert {"content": "hello digest"} in bodies
    assert {"text": "hello digest"} in bodies


@responses.activate
def test_notify_skips_unset_platform():
    responses.add(responses.POST, DISCORD, status=204)
    posted = notify("hi", discord_url=DISCORD, slack_url="")
    assert posted == ["discord"]


def test_notify_empty_text_posts_nothing():
    assert notify("", discord_url=DISCORD, slack_url=SLACK) == []


@responses.activate
def test_notify_long_text_sends_multiple_discord_calls():
    responses.add(responses.POST, DISCORD, status=204)
    long_text = "\n".join("l" * 100 for _ in range(60))  # ~6000 chars > 2000
    notify(long_text, discord_url=DISCORD)
    assert len(responses.calls) >= 3
