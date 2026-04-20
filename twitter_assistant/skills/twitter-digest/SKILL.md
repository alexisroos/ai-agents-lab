---
name: twitter-digest
description: >-
  Daily Twitter/X Following feed pipeline: captures yesterday's tweets via browser,
  scores them by engagement, summarizes linked articles (NotebookLM → LLM fallback),
  composes a digest email, and sends it to {{config.recipient_email}}.
  Use this skill whenever the user mentions: running the Twitter digest, capturing
  tweets, checking what happened on Twitter/X, getting the morning report, summarizing
  the Twitter feed, sending the daily highlights email, or running any of the three
  cron jobs (/twitter-capture, /twitter-digest, /twitter-send). Also trigger if the
  user says things like "what did I miss on Twitter", "run the digest", "did the
  capture run last night", "check Twitter for me", or anything about yesterday's feed.
  When in doubt, trigger this skill — it owns everything Twitter-digest-related.
  Triggered automatically by three cron jobs at {{config.cron_capture}}, {{config.cron_digest}}, and {{config.cron_send}} PT.
metadata: {"openclaw":{"requires":{"config":["browser.enabled"]},"emoji":"🐦"}}
---

# twitter-digest

Daily Twitter Following feed digest — capture, score, summarize, and email.

> **Browser rule:** Use only `openclaw browser` CLI subcommands (`navigate`, `snapshot`, `click`, `scroll`). Never use `page.evaluate` or any Playwright/JavaScript injection — these are not supported and will fail.

## Overview

Three sequential steps, each with its own slash command and cron schedule:

| Step | Command | Cron (PT) | What it does |
|------|---------|-----------|--------------|
| 1 | `/twitter-capture` | {{config.cron_capture}} | Fetch yesterday's tweets → `captures/YYYY-MM-DD.json` |
| 2 | `/twitter-digest` | {{config.cron_digest}} | Score, summarize links, compose email draft |
| 3 | `/twitter-send` | {{config.cron_send}} | Send digest email via `gog gmail` |

Full procedural detail for every step is in `references/SOP.md` (bundled with this skill). **Always read the SOP before executing a step** — it contains the exact scrolling rules, scoring formula, NotebookLM instructions, and failure recovery table.

---

## Quick reference

### /twitter-capture
**Use the OpenClaw browser tool with profile `user` (Chrome DevTools MCP existing-session).**
**Before scrolling: keep `chrome://inspect/#remote-debugging` open, click **Allow remote debugging**, and run `openclaw browser --browser-profile user start` to confirm `running: true`.**
**If the MCP attach fails, re-run those steps; if it still fails, alert {{config.alert_recipient_name}} via Telegram and abort.**
1. Reuse or open a Twitter tab in the MCP session → navigate to `https://twitter.com/home` → Following tab → click ⌄ next to "Following" → set **Sort by: Recent**.
2. **Refresh the page** and wait for it to fully load.
3. If **"See new posts"** button is visible at the top, click it **once** to load fresh content — then proceed to scroll (do not click again).
4. Scroll and collect all tweets from yesterday (00:00–23:59 {{config.timezone}}). Stop when timestamps fall before the window.
5. Skip tweets whose only outbound URLs are GenAI image/video generators (Grok Imagine, OpenAI Labs, Meta Imagine, Bing Create, etc.).
6. Save to `{{config.workspace_root}}/captures/YYYY-MM-DD.json` (array, newest-first).
7. Save scroll metrics to `{{config.workspace_root}}/captures/YYYY-MM-DD.meta.json`.

### /twitter-digest
1. Load `{{config.workspace_root}}/captures/YYYY-MM-DD.json`. Fall back to live scroll if missing or < 10 tweets.
2. Score: `(replies × 3) + (reposts × 2) + (likes × 1)`. Select top 10; break ties by recency.
3. For tweets with external URLs: summarize via NotebookLM → LLM fallback → `[summary unavailable]`.
4. Compose email from `{{config.workspace_root}}/templates/email.md` → for each tweet write 2–3 sentences of context (no score/metrics); link summaries 7–8 sentences each → save to `{{config.workspace_root}}/reports/YYYY-MM-DD-email.txt`.

### /twitter-send
```bash
gog gmail send \
  --account {{config.sender_account}} \
  --to {{config.recipient_email}} \
  --subject "Daily Twitter Highlights - DATE" \
  --body-file {{config.workspace_root}}/reports/YYYY-MM-DD-email.txt
```
On failure: save to `{{config.workspace_root}}/drafts/YYYY-MM-DD-email.txt` and alert {{config.alert_recipient_name}} via Telegram.

---

## Examples

**Run capture manually:**
> "Run twitter-capture for yesterday"
→ Open Twitter Following tab, scroll, save `{{config.workspace_root}}/captures/YYYY-MM-DD.json` + `.meta.json`.

**Run full pipeline:**
> "Run the Twitter digest for today" / "What did I miss on Twitter?"
→ Execute `/twitter-capture` → `/twitter-digest` → `/twitter-send` in sequence.

**Send only (capture already done):**
> "Send today's Twitter digest email"
→ Execute `/twitter-send` using existing `reports/YYYY-MM-DD-email.txt`.

**Check last night's capture:**
> "How many tweets were captured yesterday?"
→ Read `captures/YYYY-MM-DD.meta.json`; report `tweets_found`, `tweets_scrolled`, `scroll_passes`.

**Digest only (skip send):**
> "Compile the digest but don't send it yet"
→ Execute `/twitter-digest` only; leave email in `reports/`.
