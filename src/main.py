"""Orchestrate the daily YouTube digest pipeline.

Steps: load state -> resolve channels -> fetch last-24h unseen videos per
channel -> drop Shorts -> fetch transcript -> summarize -> group + format ->
post to Discord/Slack -> persist processed IDs. Per-video failures are logged
and skipped so one bad video never aborts the whole digest.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src import channels as channels_mod
from src import feed as feed_mod
from src import notify as notify_mod
from src import shorts as shorts_mod
from src import summarize as summarize_mod
from src import transcript as transcript_mod
from src.digest import DigestItem, build_digest
from src.state import State

log = logging.getLogger("ytubeagent")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS_FILE = os.path.join(ROOT, "channels.txt")
STATE_FILE = os.path.join(ROOT, "state", "processed.json")
CACHE_FILE = os.path.join(ROOT, "state", "channels_cache.json")
ENV_FILE = os.path.join(ROOT, ".env")


def load_dotenv(path: str = ENV_FILE) -> None:
    """Load KEY=VALUE lines from a local .env (if present) into os.environ.

    Zero-dependency; existing environment variables win. Used for local runs;
    GitHub Actions injects the same vars from repo secrets instead.
    """
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

WINDOW_HOURS = 24
PRUNE_DAYS = 30


def collect_items(
    channel_map: dict,
    since: datetime,
    state: State,
) -> List[DigestItem]:
    """Build digest items for all new, non-Short videos across channels."""
    items: List[DigestItem] = []
    for entry, channel_id in channel_map.items():
        try:
            videos = feed_mod.fetch_recent(channel_id, since=since, seen_ids=state.ids)
        except Exception as e:  # noqa: BLE001 - never let one channel abort the run
            log.warning("feed fetch failed for %s (%s): %s", entry, channel_id, e)
            continue

        for v in videos:
            try:
                if shorts_mod.is_short(v.video_id):
                    log.info("skip short: %s %s", v.video_id, v.title)
                    state.add(v.video_id, when=v.published)  # mark so we don't recheck
                    continue
                text = transcript_mod.fetch_transcript(v.video_id)
                summary = summarize_mod.summarize(
                    v.title, text or (v.description or v.title)
                )
                if not text:
                    summary = f"{summary}\n_(no transcript — summarized from title/description)_"
                items.append(
                    DigestItem(
                        channel_title=v.channel_title or entry,
                        title=v.title,
                        url=v.url,
                        summary=summary,
                    )
                )
                state.add(v.video_id, when=v.published)
            except Exception as e:  # noqa: BLE001
                log.warning("failed processing %s (%s): %s", v.video_id, v.title, e)
    return items


def _env(name: str) -> str:
    """Read an env var, treating unfilled ``REPLACE_`` placeholders as empty."""
    value = os.environ.get(name, "").strip()
    return "" if "REPLACE_" in value else value


def notify_config_from_env() -> notify_mod.NotifyConfig:
    return notify_mod.NotifyConfig(
        discord_bot_token=_env("DISCORD_BOT_TOKEN"),
        discord_channel_id=_env("DISCORD_CHANNEL_ID"),
        slack_bot_token=_env("SLACK_BOT_TOKEN"),
        slack_channel_id=_env("SLACK_CHANNEL_ID"),
        discord_webhook=_env("DISCORD_WEBHOOK_URL"),
        slack_webhook=_env("SLACK_WEBHOOK_URL"),
    )


def _window_hours() -> int:
    """Lookback window; overridable via WINDOW_HOURS env for manual test runs."""
    raw = os.environ.get("WINDOW_HOURS", "").strip()
    try:
        return int(raw) if raw else WINDOW_HOURS
    except ValueError:
        return WINDOW_HOURS


def run(
    channels_file: str = CHANNELS_FILE,
    state_file: str = STATE_FILE,
    cache_file: str = CACHE_FILE,
    now: Optional[datetime] = None,
    config: Optional[notify_mod.NotifyConfig] = None,
    window_hours: Optional[int] = None,
) -> int:
    """Run one digest cycle. Returns the number of videos summarized."""
    now = now or datetime.now(timezone.utc)
    window = window_hours if window_hours is not None else _window_hours()
    since = now - timedelta(hours=window)
    config = config if config is not None else notify_config_from_env()

    state = State.load(state_file)
    channel_map = channels_mod.resolve_channels(channels_file, cache_path=cache_file)
    if not channel_map:
        log.warning("no channels resolved from %s", channels_file)

    items = collect_items(channel_map, since=since, state=state)

    if items:
        body = build_digest(items, day=now.date())
        posted = notify_mod.notify(body, config)
        log.info("posted digest with %d videos to: %s", len(items), posted or "nowhere")
        if not posted:
            print(body)  # nothing configured -> emit for manual copy
    else:
        log.info("no new videos in the last %dh", window)

    state.prune(PRUNE_DAYS, now=now)
    state.save(state_file)
    return len(items)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:  # Windows consoles default to cp1252 and choke on emoji in the digest
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    load_dotenv()
    count = run()
    logging.getLogger("ytubeagent").info("done; %d videos summarized", count)


if __name__ == "__main__":
    main()
