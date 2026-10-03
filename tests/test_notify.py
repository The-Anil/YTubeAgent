import json

import responses

from src.notify import (
    DISCORD_API,
    SLACK_API,
    NotifyConfig,
    chunk_text,
    notify,
)

DISCORD_WH = "https://discord.test/webhook"
SLACK_WH = "https://slack.test/webhook"
CHAN = "123456789"


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
def test_notify_bot_mode_both_platforms():
    responses.add(responses.POST, DISCORD_API.format(channel_id=CHAN), status=200)
    responses.add(responses.POST, SLACK_API, json={"ok": True}, status=200)
    cfg = NotifyConfig(
        discord_bot_token="dtok", discord_channel_id=CHAN,
        slack_bot_token="xoxb-stok", slack_channel_id="C999",
    )
    posted = notify("hello digest", cfg)
    assert posted == ["discord", "slack"]
    disc = responses.calls[0].request
    assert disc.headers["Authorization"] == "Bot dtok"
    assert json.loads(disc.body) == {"content": "hello digest"}
    slack = responses.calls[1].request
    assert slack.headers["Authorization"] == "Bearer xoxb-stok"
    assert json.loads(slack.body) == {"channel": "C999", "text": "hello digest"}


@responses.activate
def test_notify_bot_takes_precedence_over_webhook():
    responses.add(responses.POST, DISCORD_API.format(channel_id=CHAN), status=200)
    cfg = NotifyConfig(discord_bot_token="t", discord_channel_id=CHAN,
                       discord_webhook=DISCORD_WH)
    posted = notify("hi", cfg)
    assert posted == ["discord"]
    assert responses.calls[0].request.url == DISCORD_API.format(channel_id=CHAN)


@responses.activate
def test_notify_webhook_fallback_when_no_bot():
    responses.add(responses.POST, DISCORD_WH, status=204)
    responses.add(responses.POST, SLACK_WH, status=200)
    cfg = NotifyConfig(discord_webhook=DISCORD_WH, slack_webhook=SLACK_WH)
    posted = notify("hi", cfg)
    assert posted == ["discord", "slack"]


@responses.activate
def test_notify_slack_error_is_swallowed():
    responses.add(responses.POST, SLACK_API, json={"ok": False, "error": "not_in_channel"}, status=200)
    cfg = NotifyConfig(slack_bot_token="x", slack_channel_id="C1")
    assert notify("hi", cfg) == []  # graceful: logged, not raised


@responses.activate
def test_notify_one_platform_fails_other_succeeds():
    responses.add(responses.POST, DISCORD_API.format(channel_id=CHAN), status=500)
    responses.add(responses.POST, SLACK_API, json={"ok": True}, status=200)
    cfg = NotifyConfig(discord_bot_token="t", discord_channel_id=CHAN,
                       slack_bot_token="x", slack_channel_id="C1")
    assert notify("hi", cfg) == ["slack"]  # discord failed, slack still posted


def test_notify_empty_text_posts_nothing():
    cfg = NotifyConfig(discord_bot_token="t", discord_channel_id=CHAN)
    assert notify("", cfg) == []


def test_notify_nothing_configured():
    assert notify("hi", NotifyConfig()) == []


@responses.activate
def test_notify_long_text_sends_multiple_discord_calls():
    responses.add(responses.POST, DISCORD_API.format(channel_id=CHAN), status=200)
    cfg = NotifyConfig(discord_bot_token="t", discord_channel_id=CHAN)
    long_text = "\n".join("l" * 100 for _ in range(60))  # ~6000 chars > 2000
    notify(long_text, cfg)
    assert len(responses.calls) >= 3
