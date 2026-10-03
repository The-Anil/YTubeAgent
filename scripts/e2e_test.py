"""Manual end-to-end test on a REAL latest non-Short video.

Unlike the scheduled job this ignores the 24h window and the processed-state
dedup, so it always has real content to run through the full pipeline:

    resolve channels -> pick latest non-Short upload per channel
    -> transcript -> summarize -> build digest -> post to Discord/Slack

Usage:
    python -m scripts.e2e_test            # post using webhooks from .env
    python -m scripts.e2e_test --dry-run  # print payload, do not post

Set real DISCORD_WEBHOOK_URL / SLACK_WEBHOOK_URL in .env to post for real.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from src import channels as channels_mod
from src import feed as feed_mod
from src import notify as notify_mod
from src import shorts as shorts_mod
from src import summarize as summarize_mod
from src import transcript as transcript_mod
from src.digest import DigestItem, build_digest
from src.main import CACHE_FILE, CHANNELS_FILE, load_dotenv

log = logging.getLogger("e2e")

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def latest_non_short(channel_id):
    """Return the newest non-Short Video for a channel, or None."""
    videos = feed_mod.fetch_recent(channel_id, since=EPOCH, seen_ids=None)
    for v in sorted(videos, key=lambda x: x.published, reverse=True):
        if shorts_mod.is_short(v.video_id):
            log.info("skip short %s (%s)", v.video_id, v.title)
            continue
        return v
    return None


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:  # Windows consoles default to cp1252 and choke on emoji in the digest
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print payload, do not post")
    args = ap.parse_args()

    load_dotenv()
    channel_map = channels_mod.resolve_channels(CHANNELS_FILE, cache_path=CACHE_FILE)
    log.info("channels: %s", channel_map)

    items = []
    for entry, cid in channel_map.items():
        v = latest_non_short(cid)
        if not v:
            log.warning("no non-Short video found for %s", entry)
            continue
        log.info("processing %s | %s | %s", entry, v.video_id, v.title)
        text = transcript_mod.fetch_transcript(v.video_id)
        log.info("transcript: %s chars", len(text) if text else 0)
        summary = summarize_mod.summarize(v.title, text or (v.description or v.title))
        if not text:
            summary += "\n_(no transcript — summarized from title/description)_"
        items.append(DigestItem(v.channel_title or entry, v.title, v.url, summary))

    if not items:
        log.warning("nothing to post")
        return

    body = build_digest(items, day=datetime.now(timezone.utc).date())
    print("\n===== DIGEST =====\n" + body + "\n==================\n")

    from src.main import notify_config_from_env
    config = notify_config_from_env()
    if args.dry_run:
        log.info("dry-run: not posting. discord_bot=%s slack_bot=%s",
                 bool(config.discord_bot_token and config.discord_channel_id),
                 bool(config.slack_bot_token and config.slack_channel_id))
        return
    posted = notify_mod.notify(body, config)
    log.info("posted to: %s", posted or "nowhere")


if __name__ == "__main__":
    main()
