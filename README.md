# YouTube Daily Digest Agent

Runs entirely on **GitHub Actions** every day at **3 PM IST**. Tracks a list of
YouTube channels, finds normal videos (not Shorts) uploaded in the last 24h,
pulls their subtitles, summarizes each with a free OpenRouter model, groups the
summaries per channel, and posts a digest to **Discord** and/or **Slack**.
Already-processed videos are remembered so they are never summarized twice.

No paid APIs: channel discovery uses YouTube's public RSS feeds, transcripts use
[`youtube-transcript-api`](https://pypi.org/project/youtube-transcript-api/) with
a [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) subtitle fallback.

## How it works

```
channels.txt ─▶ resolve to channel IDs ─▶ RSS feed (last 24h, unseen)
            ─▶ drop Shorts (/shorts/<id> redirect check)
            ─▶ transcript (api → yt-dlp → title/desc)
            ─▶ summarize (OpenRouter) ─▶ group by channel ─▶ Discord + Slack
            ─▶ save processed video IDs (committed back to the repo)
```

Source modules live in [src/](src/): `channels`, `feed`, `shorts`, `transcript`,
`summarize`, `digest`, `notify`, `state`, wired together by
[src/main.py](src/main.py).

## Setup

### 1. Channels

Edit [channels.txt](channels.txt) — one channel per line. Any of these forms work
(blank lines and `#` comments are ignored):

```
@torahulj
https://www.youtube.com/@torahulj
https://www.youtube.com/channel/UCc6CmEbFkEIHJKzZYCshKEQ
UCc6CmEbFkEIHJKzZYCshKEQ
```

### 2. Secrets (repo → Settings → Secrets and variables → Actions)

| Secret | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | OpenRouter API key for summaries |
| `DISCORD_WEBHOOK_URL` | optional | Discord channel incoming webhook |
| `SLACK_WEBHOOK_URL` | optional | Slack incoming webhook |

At least one of the two webhook URLs should be set; set both to post to both. An
optional repository **variable** `OPENROUTER_MODEL` overrides the default model
(`nvidia/nemotron-3-ultra-550b-a55b:free`).

### 3. Enable Actions

The schedule in [.github/workflows/digest.yml](.github/workflows/digest.yml) fires
at `30 9 * * *` UTC (= 15:00 IST). You can also trigger it manually from the
**Actions** tab (**Run workflow**). The job commits the updated
`state/processed.json` back to the repo after each run.

## Run locally

```bash
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...
export DISCORD_WEBHOOK_URL=...        # optional
export SLACK_WEBHOOK_URL=...          # optional
python -m src.main
```

With no webhook URLs set, the digest is printed to stdout for manual copy.

## Tests

Pure unit tests — all network, `yt-dlp`, and the transcript API are mocked, and
the clock is injected, so nothing hits the network.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

CI runs the suite on every push via
[.github/workflows/tests.yml](.github/workflows/tests.yml).

## Notes

- **Dedup signature** is the YouTube video ID. State is pruned to ~30 days to cap
  file size.
- GitHub runner IPs are occasionally rate-limited by YouTube; the `yt-dlp`
  fallback and a "no transcript" degradation keep the digest useful regardless.
- GitHub `schedule` triggers can be delayed several minutes under load — fine for
  a daily digest.
