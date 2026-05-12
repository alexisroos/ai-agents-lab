# audio_assistant

Real-time speech transcription with automatic ChatGPT integration for live conversation assistance.

> **📋 Universal conventions:** See `../../CONVENTIONS.MD` for project-wide standards, Claude working guidelines, and task management practices.

---

## How it works

A PyQt6 desktop application that captures audio, transcribes speech using on-device MLX models, and automatically sends questions to ChatGPT during live conversations.

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Audio Capture | sounddevice | Captures microphone input (16kHz, 1-second chunks) |
| Transcription | MLX ASR (Qwen3-ASR-1.7B) | Real-time on-device speech-to-text |
| Trigger Detection | State machine | Monitors for start/end phrases to auto-send |
| ChatGPT Integration | Chrome + URL extension | Sends text via URL parameters, auto-submits |

**Workflow:**
1. User speaks → continuous transcription displayed in editable text field
2. **Auto mode:** Say trigger phrase ("the question is...") → captures text → say end trigger ("is that right?") → auto-sends to ChatGPT
3. **Manual mode:** Review transcript → edit if needed → click Send or Send Selected

See `REQUIREMENTS.md` for detailed functional requirements and architecture.

## File layout

```
audio_assistant/
├── main.py              ← PyQt6 GUI application (MainWindow)
├── audio_capture.py     ← Microphone input handling
├── transcription.py     ← MLX ASR model integration
├── triggers.py          ← Trigger phrase state machine
├── config.py            ← Settings and logging configuration
├── requirements.txt     ← Python dependencies
├── README.md            ← Quick start guide
├── REQUIREMENTS.md      ← Detailed functional requirements
└── ~/.audio_assistant/  ← runtime data, NOT committed
    ├── settings.json    ← persisted config (mic device, window size/pos)
    ├── triggers.json    ← custom trigger phrases
    └── app.log          ← rotating logs (5MB × 3 backups)
```

## Git rules

- Never commit `~/.audio_assistant/` — runtime data directory
- Never commit `__pycache__/` — use .gitignore
- Always test on Apple Silicon before committing (MLX requirement)

## Tools & dependencies

- **Platform:** macOS with Apple Silicon (M1/M2/M3/M4) — MLX requires Apple Silicon
- **Python:** 3.9+ (3.11+ recommended)
- **GUI:** PyQt6
- **Audio:** sounddevice, numpy
- **ASR Model:** mlx-audio with `mlx-community/Qwen3-ASR-1.7B-8bit` (~5GB, auto-downloaded on first run)
- **Automation:** pyautogui (keyboard), pygetwindow (window management), pyperclip (clipboard)
- **Chrome Extension:** "Prompt ChatGPT via URL param" (required for auto-submit)
- **Microphone:** Any audio input device with macOS permissions granted
