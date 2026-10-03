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
| `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` | optional | Post via a Discord bot |
| `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` | optional | Post via a Slack bot (`xoxb-…`, `chat:write`) |
| `DISCORD_WEBHOOK_URL` | optional | Discord incoming webhook (used only if no bot token) |
| `SLACK_WEBHOOK_URL` | optional | Slack incoming webhook (used only if no bot token) |

Configure at least one platform. **Bot token + channel id takes precedence over
the webhook** for that platform. Each platform posts independently — if one
fails (bad token, bot not in channel) it is logged and skipped so the other
still goes out and the run exits cleanly. An optional repository **variable**
`OPENROUTER_MODEL` overrides the default model
(`nvidia/nemotron-3-ultra-550b-a55b:free`).

Discord bot needs **View Channel** + **Send Messages** on the target channel and
must be invited to the server. Slack bot needs the `chat:write` scope and to be
invited to the channel (`/invite @yourbot`).

### 3. Enable Actions

The schedule in [.github/workflows/digest.yml](.github/workflows/digest.yml) fires
at `30 9 * * *` UTC (= 15:00 IST). You can also trigger it manually from the
**Actions** tab (**Run workflow**). The job commits the updated
`state/processed.json` back to the repo after each run.

## Run locally

```bash
python -m pip install -r requirements.txt
cp .env.example .env     # then fill in your keys/tokens
python -m src.main
```

`src.main` auto-loads `.env` (gitignored). With no platform configured the
digest is printed to stdout for manual copy.

To test the full pipeline on a channel's **latest** normal video (ignoring the
24h window and dedup state):

```bash
python -m scripts.e2e_test --dry-run   # print only
python -m scripts.e2e_test             # also post to configured platforms
```

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
