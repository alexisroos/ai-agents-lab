# Audio Assistant

A local real-time ASR assistant with LLM integration for Mac M4 (Apple Silicon).

## Installation

1. Ensure Python 3.11+ is installed.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## First Run

1. The app will download the MLX model `mlx-community/Qwen3-ASR-1.7B-8bit` on first launch.
2. Grant microphone permissions in macOS System Preferences > Security & Privacy > Microphone.

## Usage

Run the app:
```
python main.py
```

- The app captures audio in real-time and transcribes it.
- Use manual send buttons to send recent transcript to ChatGPT via clipboard.
- Configure trigger phrases for auto-send.

## Known Limitations

- Requires manual paste into ChatGPT web UI after copying prompt.
- Only one auto-capture session at a time.
- Mac M4 only.

## Authors

- Alexis Roos — Main Author
- Claude Sonnet 4.5 — Co-Author