# SOP – Daily Twitter Digest (twitter-digest skill)

_Last updated: 2026-03-25_

## Overview
Three cron jobs run daily using OpenClaw native scheduling:
- **00:05 PT** — `/twitter-capture`: Fetch yesterday's tweets into `captures/YYYY-MM-DD.json`
- **06:30 PT** — `/twitter-digest`: Score tweets, summarize links (NotebookLM → LLM fallback), compose email draft
- **07:00 PT** — `/twitter-send`: Send digest email via `gog gmail`

Workspace root (relative to OpenClaw agent workspace): `twitter_assistant/`

---

## Step 1 – Twitter Capture (`/twitter-capture`, 00:05 PT)

Use the OpenClaw **browser tool** targeting the `user` profile (Chrome DevTools MCP existing-session).

- Keep `chrome://inspect/#remote-debugging` open in Chrome and click **Allow remote debugging for this browser instance** (leave that tab parked; closing it tears down the MCP session).
- Before scrolling, run `openclaw browser --browser-profile user start` and confirm `running: true`.
- Never launch a separate Chrome instance — always reuse the signed-in session exposed via MCP.

1. With the `user` profile selected, open the browser tool and navigate to `https://twitter.com/home`. Switch to the **Following** tab.
2. Target: **yesterday's calendar day** (00:00–23:59 America/Los_Angeles). Stop when tweet timestamps fall before that window.
3. Scroll from newest to oldest. Track a running count of every tweet card visible on screen (including those outside the target date window). **Skip and do not save** any tweet where the only outbound URLs are GenAI media generators (e.g. `grok.com/imagine`, `x.com/i/grok`, `labs.openai.com`, `imagine.meta.ai`, `bing.com/images/create`, or similar image/video generation tools) — these produce no summarizable article content. Count skipped tweets separately in `tweets_skipped_genai` in the meta file. For each tweet in the target day that passes the filter, record:
   - `tweet_id`, `author_handle`, `author_name`, `timestamp_pt`, `full_text`
   - Engagement: `replies`, `reposts`, `likes` (+ bookmarks/views if visible)
   - All outbound URLs (expand `t.co` → canonical URLs)
   - Media type indicator (image/video/poll) if present
4. Save tweets to `twitter_assistant/captures/YYYY-MM-DD.json` as a JSON array sorted newest-first. Include a `collected_at` timestamp.
5. Save scroll metrics to `twitter_assistant/captures/YYYY-MM-DD.meta.json` with these fields:
   ```json
   {
     "target_date": "YYYY-MM-DD",
     "timezone": "America/Los_Angeles",
     "collected_at": "<ISO timestamp>",
     "tweets_scrolled": <total tweet cards seen on screen>,
     "tweets_in_window": <tweets within target date range>,
     "tweets_skipped_genai": <tweets dropped due to GenAI-only URLs>,
     "tweets_found": <tweets saved (after dedup and filter)>,
     "scroll_passes": <number of scroll actions performed>,
     "stopped_at_timestamp": "<timestamp of oldest tweet seen>",
     "notes": [],
     "errors": []
   }
   ```
6. On Twitter rate-limit: pause 15 minutes, then resume from the last logged timestamp. The 00:05–06:30 window gives ample time.
7. On browser session lost: attempt re-attach via OpenClaw browser tool. If unrecoverable, log the error in `errors` field of the meta file and proceed to Step 2 with whatever was captured.

**Output:** `twitter_assistant/captures/YYYY-MM-DD.json` + `twitter_assistant/captures/YYYY-MM-DD.meta.json`

---

## Step 2 – Morning Digest Compilation (`/twitter-digest`, 06:30 PT)

1. Load `twitter_assistant/captures/YYYY-MM-DD.json` (yesterday's date). If missing or fewer than 10 tweets, fall back to a live browser scroll using Step 1 first.
   - Automation helper: `python3 twitter_assistant/scripts/run_digest.py YYYY-MM-DD` builds `reports/YYYY-MM-DD.md` + `reports/YYYY-MM-DD-top.json`, applies the keyword/handle filters in `twitter_assistant/config/filters.json`, and records how many tweets were removed. Update that config anytime you need to tweak topics (e.g., block additional political phrases or require tech-focused keywords).
2. Copy raw tweets into `twitter_assistant/reports/YYYY-MM-DD.md` under `## Raw Feed`, preserving chronological order with permalink URLs (the helper script does this automatically once the capture exists).
3. Score each tweet:
   ```
   score = (replies × 3) + (reposts × 2) + (likes × 1)
   ```
   Break ties by recency (newer = higher rank).
4. Rank all tweets; select **top 10**. Flag every tweet containing an external URL for link summarization in Step 3.
5. Log to the report header: total tweets scrolled, tweets in target window, tweets saved, scroll passes, and run timestamp. Example:
   ```
   Scrolled: 142 tweets | In window: 38 | Skipped (GenAI): 4 | Saved: 34 | Scroll passes: 12 | Captured at: 00:47 PT
   ```

---

## Step 3 – Link Summarization (during `/twitter-digest`)

For each of the top 10 tweets that contain an external URL, attempt summarization in this order:

### 3a. NotebookLM (primary — free, higher quality)
1. Use the browser tool to open `https://notebooklm.google.com/` (logged in as `{{config.notebooklm_account}}`).
2. Create or reuse a notebook titled `Twitter Digest - YYYY-MM-DD`.
3. Click **Add source → Link**, paste the article URL, wait for ingestion.
4. Use NotebookLM's Notes panel to generate a 4–5 sentence summary covering the main thesis and key takeaways. Copy the text.
5. Append the summary to `twitter_assistant/reports/YYYY-MM-DD.md` under `## Summaries`, tagged `[via NotebookLM]`.

### 3b. LLM fallback (if NotebookLM fails)
Use this when: NotebookLM is unavailable, the URL fails to ingest, or the browser session is lost.

1. Use the browser tool to fetch the page content directly.
2. Pass content to OpenClaw's LLM with this prompt:
   > "Summarize this article in 4–5 sentences covering the main thesis and key takeaways."
3. Append the summary tagged `[via LLM]`.

### 3c. Skip
If both methods fail (paywalled, unscrapable, timeout), note it as `[summary unavailable]` and include the tweet in the digest without a summary.

OpenClaw's model failover handles LLM unavailability in 3b automatically.

---

## Step 4 – Email Composition (during `/twitter-digest`)

1. Load `twitter_assistant/templates/email.md`. Populate:
   - `{{date}}` → e.g., `Saturday, March 7, 2026`
   - `{{top_tweets}}` → markdown bullets: author, metrics, key insight/quote, permalink
   - `{{link_summaries}}` → bullets from Step 3 output
2. Save the composed email to `twitter_assistant/reports/YYYY-MM-DD-email.txt`.

---

## Step 5 – Send Email (`/twitter-send`, 07:00 PT)

1. Build the body after summaries are finalized:
   ```bash
   python3 twitter_assistant/scripts/build_email.py YYYY-MM-DD
   ```
2. Send via the helper script (reads `config/settings.json` for all addresses/account IDs):
   ```bash
   python3 twitter_assistant/scripts/send_email.py YYYY-MM-DD [--subject-suffix "(Tech Filter)"]
   ```
   - Add `--dry-run` if you just want to preview the `gog gmail send` command.
3. On failure: save the body to `twitter_assistant/drafts/YYYY-MM-DD-email.txt` and notify Alex via Telegram.

---

## Step 6 – Logging & Memory

- Write a brief entry to OpenClaw memory noting trends, recurring authors, or anomalies worth tracking across days.
- Optionally commit `reports/YYYY-MM-DD.md` and `reports/YYYY-MM-DD-email.txt` for traceability.

---

## Failure Recovery

| Failure | Response |
|---|---|
| Twitter unreachable | Log it; send abbreviated email noting the outage |
| Chrome MCP attach disabled (inspect tab closed) | Reopen `chrome://inspect/#remote-debugging`, click **Allow remote debugging**, rerun `openclaw browser --browser-profile user start`, then resume |
| NotebookLM unavailable | Fall back to LLM summarization (Step 3b) |
| LLM unavailable | OpenClaw failover handles automatically |
| Gmail send fails | Save to `drafts/`; alert Alex via Telegram |
| Cron job missed | OpenClaw heartbeat detects missed jobs; alert Alex and allow manual trigger via `/twitter-capture`, `/twitter-digest`, or `/twitter-send` |

---

## File Layout

```
twitter_assistant/
├── SOP.md                          ← this file
├── REQUIREMENTS.md                 ← original spec
├── captures/
│   └── YYYY-MM-DD.json             ← raw tweet capture (Step 1 output)
├── reports/
│   ├── YYYY-MM-DD.md               ← scored feed + summaries (Step 2–3 output)
│   └── YYYY-MM-DD-email.txt        ← composed email ready to send (Step 4 output)
├── drafts/
│   └── YYYY-MM-DD-email.txt        ← fallback if send fails
├── templates/
│   └── email.md                    ← email template with {{placeholders}}
└── skills/
    └── twitter-digest/
        └── SKILL.md                ← OpenClaw skill definition
```
