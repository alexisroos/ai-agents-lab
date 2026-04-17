# SOP – Daily Twitter Digest (twitter-digest skill)

_Last updated: 2026-03-25_

## Configuration

All user-specific values live in `skills/twitter-digest/config.json`. Edit that file before using the skill:

| Key | Description | Example |
|-----|-------------|---------|
| `recipient_email` | Who receives the digest email | `you@example.com` |
| `sender_account` | Gmail account used to send (via `gog gmail`) | `your-agent@gmail.com` |
| `notebooklm_account` | Google account for NotebookLM | `your-agent@gmail.com` |
| `workspace_root` | Project folder path (relative to agent workspace) | `twitter_assistant` |
| `timezone` | Timezone for determining "yesterday" | `America/Los_Angeles` |
| `alert_recipient_name` | Your name, used in Telegram failure alerts | `Alex` |
| `cron_capture` | Time to run capture step (24h, PT) | `00:05` |
| `cron_digest` | Time to run digest step | `06:30` |
| `cron_send` | Time to send email | `07:00` |

---

## Overview
Three cron jobs run daily using OpenClaw native scheduling:
- **{{config.cron_capture}} PT** — `/twitter-capture`: Fetch yesterday's tweets into `captures/YYYY-MM-DD.json`
- **{{config.cron_digest}} PT** — `/twitter-digest`: Score tweets, summarize links (NotebookLM → LLM fallback), compose email draft
- **{{config.cron_send}} PT** — `/twitter-send`: Send digest email via `gog gmail`

Workspace root (relative to OpenClaw agent workspace): `{{config.workspace_root}}/`

---

## Step 1 – Twitter Capture (`/twitter-capture`, 00:05 PT)

Use the OpenClaw **browser tool** targeting the `user` profile (Chrome DevTools MCP existing-session).

- Keep `chrome://inspect/#remote-debugging` open in Chrome and click **Allow remote debugging for this browser instance**. That tab must stay open; closing it drops the MCP session.
- Before scrolling, run `openclaw browser --browser-profile user start` and confirm `running: true`.
- Never launch a separate Chrome window — always reuse the signed-in session exposed via MCP.

**If the MCP attach fails:** Reopen `chrome://inspect/#remote-debugging`, click **Allow remote debugging**, rerun `openclaw browser --browser-profile user start`, and only continue once `status` shows `running: true`.

1. Check if a Twitter tab is already open in the MCP session. If yes, reuse it. If no tabs exist, open `https://twitter.com/home` in a new tab (Twitter credentials live in the signed-in Chrome profile). Switch to the **Following** tab. Click the down arrow (⌄) next to "Following" and set **Sort by → Recent** to ensure chronological order.
2. **Refresh the page** (reload `https://twitter.com/home`) and wait for it to fully load. This ensures the feed is not stale.
3. Look for a **"See new posts"** button at the top of the feed (only present when new posts are available). If present, click it **once** before scrolling to load fresh content. Do not click it again even if it reappears — proceed directly to scrolling.
4. Target: **yesterday's calendar day** (00:00–23:59 {{config.timezone}}). Stop when tweet timestamps fall before that window.
5. Scroll from newest to oldest. Track a running count of every tweet card visible on screen (including those outside the target date window). **Skip and do not save** any tweet where the only outbound URLs are GenAI media generators (e.g. `grok.com/imagine`, `x.com/i/grok`, `labs.openai.com`, `imagine.meta.ai`, `bing.com/images/create`, or similar image/video generation tools) — these produce no summarizable article content. Count skipped tweets separately in `tweets_skipped_genai` in the meta file. For each tweet in the target day that passes the filter, record:
   - `tweet_id`, `author_handle`, `author_name`, `timestamp_pt`, `full_text`
   - Engagement: `replies`, `reposts`, `likes` (+ bookmarks/views if visible)
   - All outbound URLs (expand `t.co` → canonical URLs)
   - Media type indicator (image/video/poll) if present
6. Save tweets to `{{config.workspace_root}}/captures/YYYY-MM-DD.json` as a JSON array sorted newest-first. Include a `collected_at` timestamp.
7. Save scroll metrics to `{{config.workspace_root}}/captures/YYYY-MM-DD.meta.json` with these fields:
   ```json
   {
     "target_date": "YYYY-MM-DD",
     "timezone": "{{config.timezone}}",
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
8. On Twitter rate-limit: pause 15 minutes, then resume from the last logged timestamp. The 00:05–06:30 window gives ample time.
9. On browser session lost: attempt re-attach via OpenClaw browser tool. If unrecoverable, log the error in `errors` field of the meta file and proceed to Step 2 with whatever was captured.

**Output:** `{{config.workspace_root}}/captures/YYYY-MM-DD.json` + `{{config.workspace_root}}/captures/YYYY-MM-DD.meta.json`

---

## Step 2 – Morning Digest Compilation (`/twitter-digest`, 06:30 PT)

1. Load `{{config.workspace_root}}/captures/YYYY-MM-DD.json` (yesterday's date). If missing or fewer than 10 tweets, fall back to a live browser scroll using Step 1 first.
2. Copy raw tweets into `{{config.workspace_root}}/reports/YYYY-MM-DD.md` under `## Raw Feed`, preserving chronological order with permalink URLs.
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
1. Reuse the existing browser window (do NOT open a new one). Navigate to `https://notebooklm.google.com/` (logged in as {{config.notebooklm_account}}).
2. Create or reuse a notebook titled `Twitter Digest - YYYY-MM-DD`.
3. Click **Add source → Link**, paste the article URL, wait for ingestion.
4. Use NotebookLM's Notes panel to generate a 7–8 sentence summary covering the main thesis, key arguments, supporting evidence, and notable implications or conclusions. Copy the text.
5. Append the summary to `{{config.workspace_root}}/reports/YYYY-MM-DD.md` under `## Summaries`, tagged `[via NotebookLM]`.

### 3b. LLM fallback (if NotebookLM fails)
Use this when: NotebookLM is unavailable, the URL fails to ingest, or the browser session is lost.

1. Use the browser tool to fetch the page content directly.
2. Pass content to OpenClaw's LLM with this prompt:
   > "Summarize this article in 7–8 sentences covering the main thesis, key arguments, supporting evidence, and notable implications or conclusions."
3. Append the summary to `{{config.workspace_root}}/reports/YYYY-MM-DD.md` tagged `[via LLM]`.

### 3c. Skip
If both methods fail (paywalled, unscrapable, timeout), note it as `[summary unavailable]` and include the tweet in the digest without a summary.

OpenClaw's model failover handles LLM unavailability in 3b automatically.

---

## Step 4 – Email Composition (during `/twitter-digest`)

1. Load `{{config.workspace_root}}/templates/email.md`. Populate:
   - `{{date}}` → e.g., `Saturday, March 7, 2026`
   - `{{top_tweets}}` → for each of the top 10 tweets, a section with:
     - **Author** (`@handle`) and a permalink
     - 2–3 sentences expanding on what the tweet says, why it matters, and any relevant context (do NOT include the engagement score or raw metrics)
   - `{{link_summaries}}` → the 7–8 sentence summaries from Step 3, one per linked article, each preceded by the tweet author and article title as a header
2. Save the composed email to `{{config.workspace_root}}/reports/YYYY-MM-DD-email.txt`.

---

## Step 5 – Send Email (`/twitter-send`, 07:00 PT)

```bash
gog gmail send \
  --account {{config.sender_account}} \
  --to {{config.recipient_email}} \
  --subject "Daily Twitter Highlights - {{date}}" \
  --body-file {{config.workspace_root}}/reports/{{YYYY-MM-DD}}-email.txt
```

- Confirm `status: sent` in output.
- On failure: save to `{{config.workspace_root}}/drafts/YYYY-MM-DD-email.txt` and send an alert via OpenClaw's Telegram channel to notify {{config.alert_recipient_name}}.

---

## Step 6 – Logging & Memory

- Write a brief entry to OpenClaw memory noting trends, recurring authors, or anomalies worth tracking across days.
- Optionally commit `{{config.workspace_root}}/reports/YYYY-MM-DD.md` and `{{config.workspace_root}}/reports/YYYY-MM-DD-email.txt` for traceability.

---

## Failure Recovery

| Failure | Response |
|---|---|
| Twitter unreachable | Log it; send abbreviated email noting the outage |
| No tabs open in MCP session | Open `https://twitter.com/home` in a new tab within the existing Chrome window; proceed normally |
| Chrome MCP attach disabled / connection refused | Reopen `chrome://inspect/#remote-debugging`, click **Allow remote debugging**, rerun `openclaw browser --browser-profile user start`. If it still fails, alert {{config.alert_recipient_name}} and abort. |
| Chrome MCP session dropped mid-run | Re-enable remote debugging (see above) and rerun `openclaw browser --browser-profile user start`; if it still fails, log it and proceed with whatever was captured |
| NotebookLM unavailable | Fall back to LLM summarization (Step 3b) |
| LLM unavailable | OpenClaw failover handles automatically |
| Gmail send fails | Save to `drafts/`; alert {{config.alert_recipient_name}} via Telegram |
| Cron job missed | OpenClaw heartbeat detects missed jobs; alert {{config.alert_recipient_name}} and allow manual trigger via `/twitter-capture`, `/twitter-digest`, or `/twitter-send` |

---

## File Layout

```
{{config.workspace_root}}/
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
        ├── config.json             ← user configuration (edit before using)
        ├── SKILL.md                ← OpenClaw skill definition
        └── references/
            └── SOP.md              ← this file
```
