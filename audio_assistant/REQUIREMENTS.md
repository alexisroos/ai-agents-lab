# Audio Assistant - Requirements Document

## Project Overview

The Audio Assistant is a real-time speech transcription application that automatically captures audio, transcribes it using on-device ML models, and integrates with ChatGPT for intelligent question answering during live conversations.

**Primary Use Case**: Assist users during live conversations by transcribing questions, automatically sending them to ChatGPT, and providing answers in real-time.

**Target Platform**: macOS (Apple Silicon with MLX support)

---

## Functional Requirements

### FR-1: Audio Capture
- **FR-1.1**: Application shall capture audio from selectable microphone devices
- **FR-1.2**: Microphone selection shall be immediate without confirmation dialogs
- **FR-1.3**: Microphone list shall be dynamically populated from available input devices
- **FR-1.4**: Audio capture shall use 16kHz sample rate with 1-second chunks
- **FR-1.5**: Application shall maintain audio capture state across device changes

### FR-2: Speech Transcription
- **FR-2.1**: Application shall transcribe speech in real-time using MLX-based ASR models
- **FR-2.2**: Transcription shall use Qwen3-ASR-1.7B model (with 8-bit fallback)
- **FR-2.3**: Transcription shall filter common filler words: "okay", "thank you", "um", "uh", "oh"
- **FR-2.4**: Transcription shall ignore repeated identical text
- **FR-2.5**: Transcription shall only process audio above amplitude threshold (0.002)
- **FR-2.6**: Audio shall be normalized before transcription for quality

### FR-3: Transcript Display
- **FR-3.1**: Transcript shall be displayed in editable text field with light yellow highlight
- **FR-3.2**: Application shall insert line breaks after 3+ second pauses in speech
- **FR-3.3**: Transcript text shall be editable before sending
- **FR-3.4**: Transcript shall maintain last 5 minutes of content (300 seconds)
- **FR-3.5**: Separate display shall show sent messages with timestamps

### FR-4: Trigger-Based Auto-Send
- **FR-4.1**: Application shall monitor for configurable start trigger phrases (default: "the question", "the problem")
- **FR-4.2**: Application shall monitor for configurable end trigger phrases (default: "that right?", "that correct?")
- **FR-4.3**: Upon detecting start phrase, application shall begin capturing mode
- **FR-4.4**: Upon detecting end phrase, application shall automatically send captured text
- **FR-4.5**: There shall be NO time limit between start and end triggers
- **FR-4.6**: User shall be able to add/edit/remove trigger phrases via UI

### FR-5: Manual Send Operations
- **FR-5.1**: "Send" button shall send all text in transcript box
- **FR-5.2**: "Send Selected" button shall send only highlighted text
- **FR-5.3**: If transcript is empty, "Send" shall resend last sent text (cached)
- **FR-5.4**: "Clear All" button shall clear transcript, sent history, and clipboard

### FR-6: ChatGPT Integration
- **FR-6.1**: Application shall send text to ChatGPT via Chrome with URL parameters
- **FR-6.2**: Requires Chrome extension: "Prompt ChatGPT via URL param"
- **FR-6.3**: Application shall format prompts for live conversation context
- **FR-6.4**: Application shall auto-submit to ChatGPT after 0.5 second delay
- **FR-6.5**: Application shall activate Chrome window and press return to submit

### FR-7: User Interface
- **FR-7.1**: UI shall use white background with black text for macOS visibility
- **FR-7.2**: UI shall display status indicator: "○ Idle" or "● Listening"
- **FR-7.3**: UI shall show three main buttons: Send, Send Selected, Clear All
- **FR-7.4**: UI shall display current trigger phrases
- **FR-7.5**: UI shall provide microphone selector dropdown
- **FR-7.6**: UI shall separate transcript view from sent messages view

### FR-8: Configuration & Persistence
- **FR-8.1**: Settings shall persist to `~/.audio_assistant/settings.json`
- **FR-8.2**: Trigger phrases shall persist to `~/.audio_assistant/triggers.json`
- **FR-8.3**: Window size and position shall be saved and restored
- **FR-8.4**: Selected microphone device shall be saved
- **FR-8.5**: Application shall create config directory on first run

### FR-9: Logging
- **FR-9.1**: Application shall log to `~/.audio_assistant/app.log`
- **FR-9.2**: Log files shall rotate at 5MB with 3 backups
- **FR-9.3**: Logs shall include timestamps, log levels, and messages
- **FR-9.4**: Errors shall be logged with full exception traces

---

## Non-Functional Requirements

### NFR-1: Performance
- **NFR-1.1**: Transcription latency shall be < 2 seconds per 1-second audio chunk
- **NFR-1.2**: UI shall remain responsive during transcription
- **NFR-1.3**: Model loading shall complete within 10 seconds on Apple Silicon

### NFR-2: Reliability
- **NFR-2.1**: Audio capture errors shall not crash the application
- **NFR-2.2**: Model loading failures shall provide clear error messages
- **NFR-2.3**: Application shall gracefully handle microphone disconnection

### NFR-3: Usability
- **NFR-3.1**: All UI text shall be clearly visible on macOS (both light and dark modes)
- **NFR-3.2**: Microphone changes shall take effect immediately
- **NFR-3.3**: Transcript shall be editable for manual corrections

### NFR-4: Compatibility
- **NFR-4.1**: Application shall run on macOS with Apple Silicon (M1/M2/M3)
- **NFR-4.2**: Application shall require Python 3.9+
- **NFR-4.3**: Application shall use PyQt6 for cross-platform GUI

---

## Technical Architecture

### Components

1. **AudioCapture** (`audio_capture.py`)
   - Handles microphone input using sounddevice
   - Queues audio chunks for processing
   - Runs in background thread

2. **TranscriptionEngine** (`transcription.py`)
   - Loads MLX ASR model
   - Processes audio chunks
   - Filters filler words
   - Emits transcription signals

3. **TriggerMatcher** (`triggers.py`)
   - State machine (IDLE/CAPTURING)
   - Matches start/end trigger phrases
   - No timeout between triggers

4. **MainWindow** (`main.py`)
   - PyQt6 GUI application
   - Signal/slot architecture
   - Handles user interactions
   - Manages component lifecycle

5. **Config** (`config.py`)
   - Loads/saves settings and triggers
   - Manages application directory
   - Configures logging

### Data Flow

```
Microphone → AudioCapture → Queue → TranscriptionEngine →
  → Signal → MainWindow → TriggerMatcher → ChatGPT Integration
```

### Threading Model
- **Main Thread**: PyQt6 UI event loop
- **Audio Thread**: sounddevice input stream (daemon)
- **Transcription Thread**: MLX model processing (daemon)
- **Auto-submit Thread**: Chrome activation and keypress (daemon)

---

## Dependencies

### Python Packages
```
mlx-audio          # MLX-based speech recognition
pyqt6             # GUI framework
sounddevice       # Audio capture
numpy             # Audio processing
pyperclip         # Clipboard operations
pyautogui         # Keyboard automation
pygetwindow       # Window management
```

### External Requirements
- macOS with Apple Silicon (for MLX)
- Google Chrome browser
- Chrome extension: "Prompt ChatGPT via URL param"
- Microphone input device

### ML Models
- Primary: `mlx-community/Qwen3-ASR-1.7B`
- Fallback: `mlx-community/Qwen3-ASR-1.7B-8bit`

---

## Installation Requirements

### System Requirements
- macOS 12.0+ (Monterey or later)
- Apple Silicon processor (M1/M2/M3)
- 4GB+ RAM
- 5GB+ disk space (for models)
- Microphone device

### Setup Steps
1. Clone repository
2. Install Python dependencies: `pip install -r requirements.txt`
3. Install Chrome extension: "Prompt ChatGPT via URL param"
4. Run application: `python main.py`
5. Select microphone on first launch
6. Configure trigger phrases (optional)

---

## Configuration Files

### settings.json
```json
{
  "mic_device": 0,
  "window_size": [800, 600],
  "window_pos": [100, 100]
}
```

### triggers.json
```json
{
  "start": ["the question", "the problem"],
  "end": ["that right?", "that correct?"]
}
```

---

## User Workflow

### Typical Use Case: Live Conversation Assistance

1. **Setup**
   - User launches application
   - Application loads ASR model
   - User selects microphone if needed

2. **Listening Mode**
   - Application continuously transcribes speech
   - Transcript appears in yellow-highlighted text
   - Line breaks inserted after 3-second pauses

3. **Trigger-Based Capture** (Automatic)
   - User says: "So the question is..."
   - Application detects start trigger
   - Captures all subsequent speech
   - User says: "Is that right?"
   - Application detects end trigger
   - Automatically sends to ChatGPT
   - ChatGPT response appears in browser

4. **Manual Send** (Alternative)
   - User reviews transcript
   - Optionally edits text
   - Clicks "Send" or "Send Selected"
   - Text sent to ChatGPT

5. **Cleanup**
   - User clicks "Clear All" to reset
   - Transcript and sent history cleared

---

## Future Enhancements (Out of Scope)

- Multi-language support
- Speaker diarization
- Offline ChatGPT integration
- Custom prompt templates
- Export transcript history
- Voice activity detection
- Noise cancellation
- Windows/Linux support

---

## Acceptance Criteria

### Must Have (MVP)
- ✅ Real-time speech transcription
- ✅ Automatic ChatGPT integration
- ✅ Trigger-based auto-send
- ✅ Manual send options
- ✅ Editable transcript
- ✅ macOS GUI visibility

### Should Have
- ✅ Configurable trigger phrases
- ✅ Persistent settings
- ✅ Separate sent messages view
- ✅ Pause detection (line breaks)
- ✅ Last text resend capability

### Could Have (Future)
- ⬜ Multiple language support
- ⬜ Custom prompt templates
- ⬜ Transcript export
- ⬜ Voice activity detection

---

## Testing Requirements

### Unit Testing
- Audio capture initialization
- Trigger phrase matching state machine
- Config load/save operations

### Integration Testing
- End-to-end transcription flow
- ChatGPT auto-submit sequence
- Microphone switching

### Manual Testing
- Verify UI visibility on macOS
- Test trigger phrase detection accuracy
- Validate Chrome extension integration
- Check transcript editing functionality

---

## Glossary

- **ASR**: Automatic Speech Recognition
- **MLX**: Apple's machine learning framework for Apple Silicon
- **Trigger Phrase**: User-defined phrase that activates auto-send
- **Chunk**: Fixed-duration segment of audio (1 second)
- **Amplitude Threshold**: Minimum audio level to process (0.002)
- **Filler Words**: Common speech patterns filtered out (um, uh, okay)

---

**Document Version**: 1.0
**Last Updated**: 2026-03-05
**Authors**: Alexis Roos (Main Author), Claude Sonnet 4.5
