# Requirements – Daily Twitter Following Summary (OpenClaw Edition)

## Overview
Daily at 07:00 America/Los_Angeles, send an email digest covering every tweet the agent sees in the **Following** feed during the **previous calendar day** (00:00 → 23:59 PT). Runs as an OpenClaw skill with native cron scheduling, OpenClaw's browser tool for Twitter capture, the default LLM (with automatic failover) for link summarization, and Gmail for delivery.

---

## 0. Prerequisites
- OpenClaw installed and running with `openclaw status` showing healthy.
- Google Chrome 144+ with **Chrome DevTools MCP auto-connect** allowed (open `chrome://inspect/#remote-debugging`, click **Allow remote debugging for this browser instance**, and leave that tab open). Chrome must be logged into Twitter and Gmail as your agent account.
- OpenClaw browser tool enabled (`browser.enabled: true` in `~/.openclaw/openclaw.json`).
- Gmail skill or `gog` CLI authenticated for your agent Gmail account.
- Workspace: `twitter_assistant/` at the OpenClaw agent workspace root.
  - `twitter_assistant/captures/` — raw JSON per day
  - `twitter_assistant/reports/` — processed markdown + email drafts
  - `twitter_assistant/templates/email.md` — email template
  - `twitter_assistant/skills/twitter-digest/SKILL.md` — this skill

---

## 1. OpenClaw Skill Definition

Create `twitter_assistant/skills/twitter-digest/SKILL.md`:

```markdown
---
name: twitter-digest
description: Captures yesterday's Twitter Following feed, scores tweets, summarizes links via LLM, and emails a digest to {{config.recipient_email}} at {{config.cron_send}} PT.
metadata: {"openclaw":{"requires":{"config":["browser.enabled"]},"emoji":"🐦"}}
---

Run the daily Twitter digest workflow. Capture tweets, score them, summarize links, and send the email. Follow the SOP in twitter_assistant/SOP.md.
```

---

## 2. Cron Schedule (OpenClaw Native)

Register via OpenClaw cron (not system cron), so OpenClaw manages timing, retries, and alerting:

```
00:05 PT  — /twitter-capture   (Step 3: fetch tweets into captures/YYYY-MM-DD.json)
06:30 PT  — /twitter-digest    (Steps 4–6: score, summarize, compose email)
07:00 PT  — /twitter-send      (Step 7: send via Gmail)
```

Use `openclaw cron add` or configure in `~/.openclaw/openclaw.json` under the `cron` key. Each job sends a message to the agent triggering the named slash command.

---

## 3. Twitter Capture (00:05 PT)

Use the OpenClaw **browser tool** targeting the `user` profile (Chrome DevTools MCP existing-session). Before scrolling:
- Keep `chrome://inspect/#remote-debugging` open in Chrome and click **Allow remote debugging for this browser instance** (leave that tab parked so the MCP session stays alive).
- Run `openclaw browser --browser-profile user start` to confirm the attach reports `running: true`.

Never launch a separate Chrome window; always reuse the signed-in session that Chrome MCP exposes.

1. Use the `browser` tool (profile `user`) to navigate to `https://twitter.com/home`, switch to the **Following** tab.
2. Target: yesterday's calendar day (00:00–23:59 PT). Stop when timestamps fall before that window.
3. Scroll oldest-to-newest. For each tweet in range, record:
   - `tweet_id`, `author_handle`, `author_name`, `timestamp_pt`, `full_text`
   - Engagement: `replies`, `reposts`, `likes` (+ bookmarks/views if visible)
   - All outbound URLs (expand `t.co` → canonical)
   - Media type indicator (image/video/poll) if present
4. Save to `captures/YYYY-MM-DD.json` as a JSON array, sorted newest-first. Include `collected_at` timestamp.
5. On Twitter rate-limit: pause 15 minutes, resume from last logged timestamp. The 00:05–06:30 window gives ample time.
6. On browser session lost: attempt re-attach via OpenClaw browser login tool. If unrecoverable, log the error and proceed to Step 4 with whatever was captured.

---

## 4. Morning Digest Compilation (06:30 PT)

1. Load `captures/YYYY-MM-DD.json` (yesterday). If missing or fewer than 10 tweets, fall back to a live browser scroll using Step 3.
2. Copy raw tweets into `reports/YYYY-MM-DD.md` under `## Raw Feed`, preserving chronological order with permalink URLs.
3. Score each tweet:
   ```
   score = (replies × 3) + (reposts × 2) + (likes × 1)
   ```
   Break ties by recency (newer = higher).
4. Rank all tweets; select **top 10**. Flag every tweet containing an external URL for link summarization.
5. Log to the report: total tweets reviewed, run timestamp, any anomalies.

---

## 5. Link Summarization (06:30 PT, during digest)

For each of the top 10 tweets that contain an external URL, summarize in this order:

### 5a. NotebookLM (primary)
1. Open `https://notebooklm.google.com/` (signed in as your agent Google account) inside the `user` browser profile.
2. Create or reuse a notebook named `Twitter Digest - YYYY-MM-DD`.
3. Click **Add source → Link**, paste the article URL, and wait for ingestion to finish.
4. In the Notes panel, ask NotebookLM for a 4–5 sentence summary covering the main thesis and key takeaways. Copy the response.
5. Append the summary to `reports/YYYY-MM-DD.md` under `## Summaries`, tagged `[via NotebookLM]`.

### 5b. LLM fallback (only if NotebookLM fails)
1. Use the browser tool to fetch the article content.
2. Run the default OpenClaw LLM with the prompt: *"Summarize this article in 4–5 sentences covering the main thesis and key takeaways."*
3. Append the summary tagged `[via LLM]`.

### 5c. Skip
If both NotebookLM and the fallback fail (paywall, timeout, etc.), mark `[summary unavailable]` and include the tweet without a summary.

OpenClaw's failover handles LLM outages automatically.

---

## 6. Email Composition (06:30 PT)

1. Load `templates/email.md`. Populate:
   - `{{date}}` → e.g., `Friday, March 6, 2026`
   - `{{top_tweets}}` → markdown bullets: author, metrics, key insight/quote, permalink
   - `{{link_summaries}}` → table or bullets from Step 5 output
2. Save to `reports/YYYY-MM-DD-email.txt`.

---

## 7. Send Email (07:00 PT)

```bash
gog gmail send \
  --account {{config.sender_account}} \
  --to {{config.recipient_email}} \
  --subject "Daily Twitter Highlights - {{date}}" \
  --body-file twitter_assistant/reports/{{YYYY-MM-DD}}-email.txt
```

Confirm `status: sent` in output. On failure, save to `drafts/YYYY-MM-DD-email.txt` and send an alert via OpenClaw's messaging channel (Telegram/WhatsApp/etc.) to notify Alex.

---

## 8. Logging & Memory

- Commit `reports/YYYY-MM-DD.md` and `reports/YYYY-MM-DD-email.txt` for traceability.
- Write a brief entry to OpenClaw memory (via the memory tool) noting trends, recurring authors, or anomalies worth tracking across days.

---

## 9. Failure Recovery

| Failure | Response |
|---|---|
| Twitter unreachable | Log it; send abbreviated email noting the outage |
| Chrome MCP attach disabled (remote debugging tab closed) | Reopen `chrome://inspect/#remote-debugging`, click **Allow remote debugging**, rerun `openclaw browser --browser-profile user start`, then resume capture |
| LLM unavailable | OpenClaw failover handles this automatically |
| Gmail send fails | Save to `drafts/`; alert Alex via OpenClaw messaging channel |
| Cron job missed | OpenClaw heartbeat detects missed jobs; alert Alex and allow manual trigger via `/twitter-digest` slash command |

---

## 10. Technical Stack (Revised)

| Layer | Choice |
|---|---|
| Platform | OpenClaw (local, on your machine) |
| Scheduling | OpenClaw native cron (`openclaw cron`) |
| Browser automation | OpenClaw browser tool (profile `user`) via Chrome DevTools MCP existing-session |
| Link summarization | NotebookLM (primary) → OpenClaw LLM fallback |
| LLM | OpenClaw default (Anthropic/OpenAI/local) with automatic failover |
| Email | `gog gmail send` CLI |
| Skills | `twitter-digest` skill in `twitter_assistant/skills/` |
| Storage | `twitter_assistant/` (captures, reports, templates) |
| Alerts | OpenClaw messaging channel (Telegram/WhatsApp/etc.) |
