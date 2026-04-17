# twitter_assistant

Daily Twitter/X digest pipeline: capture → score → summarize → email.

## How it works

Three cron jobs run sequentially each day via OpenClaw native scheduling:

| Step | Command | Cron (PT) | Output |
|------|---------|-----------|--------|
| 1 | `/twitter-capture` | 00:05 | `captures/YYYY-MM-DD.json` + `.meta.json` |
| 2 | `/twitter-digest` | 06:30 | `reports/YYYY-MM-DD.md` + `YYYY-MM-DD-email.txt` |
| 3 | `/twitter-send` | 07:00 | Email sent via `gog gmail` |

Full procedural detail is in `skills/twitter-digest/references/SOP.md`.

## Skill

- Source: `skills/twitter-digest/` (SKILL.md + references/SOP.md + config.json + evals/)
- Bundle: `skills/twitter-digest.skill` (ZIP — rebuild after editing source files)
- Config: `skills/twitter-digest/config.json` — edit this to change recipient, sender, paths, timezone, cron times
- Rebuild bundle: `cd skills && zip -r twitter-digest.skill twitter-digest/`

## File layout

```
twitter_assistant/
├── captures/        ← runtime data, NOT committed
├── reports/         ← runtime data, NOT committed
├── drafts/          ← runtime data, NOT committed
├── templates/
│   └── email.md     ← email template with {{placeholders}}
└── skills/
    └── twitter-digest/
        ├── config.json
        ├── SKILL.md
        ├── evals/
        └── references/
            └── SOP.md
```

## Git rules

- Never commit `captures/`, `reports/`, or `drafts/` — these are runtime data dirs
- Always rebuild `skills/twitter-digest.skill` after editing skill source files

## Tools & dependencies

- **Browser:** OpenClaw browser tool, profile `user` (Chrome DevTools MCP existing-session; requires `chrome://inspect/#remote-debugging` to stay open)
- **Email send:** `gog gmail` CLI
- **Alerts:** OpenClaw Telegram channel
- **Summarization:** NotebookLM (primary) → LLM fallback
