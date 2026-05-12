# ai-agents-lab

Monorepo of OpenClaw-powered agentic assistants running on a local Mac mini.

> **📋 Universal conventions:** See `../CONVENTIONS.MD` for project-wide standards, Claude working guidelines, and task management practices.

---

## Projects

- `twitter_assistant/` — Browse Twitter following from past 24 hours, filter, score and send a daily email.
- `audio_assistant/` — The Audio Assistant is a real-time speech transcription application that automatically captures audio, transcribes it using on-device ML models, and integrates with ChatGPT for intelligent question answering during live conversations.

## Stack

- **Agent runtime:** OpenClaw (local gateway on Mac mini, LaunchAgent service)
- **Browser automation:** OpenClaw Chrome Relay (no Playwright)
- **Scheduling:** OpenClaw native cron jobs
- **Alerts:** Telegram channel
- **Email:** `gog gmail` CLI
- **Skills format:** OpenClaw `.skill` bundles (ZIP of SKILL.md + references/ + config.json)

## Sub-project documentation

Each assistant has its own detailed CLAUDE.MD:
- `twitter_assistant/CLAUDE.MD` - Daily Twitter digest pipeline
- `audio_assistant/CLAUDE.MD` - Real-time speech transcription with ChatGPT integration
