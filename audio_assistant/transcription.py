from mlx_audio import stt
import numpy as np
import tempfile
import os
import soundfile as sf
import queue
import threading
from datetime import datetime
import collections

class TranscriptionEngine:
    def __init__(self, audio_queue, buffer_lock, transcript_buffer, signals):
        self.audio_queue = audio_queue
        self.buffer_lock = buffer_lock
        self.transcript_buffer = transcript_buffer
        self.signals = signals
        self.model = None
        self.running = False
        self.thread = None
        self.last_text = ""

    def load_model(self):
        try:
            # Use the non-quantized model for better quality (will be slower but more accurate)
            # Try full model first, fallback to 8-bit if needed
            try:
                self.model = stt.load("mlx-community/Qwen3-ASR-1.7B")
            except:
                # Fallback to 8-bit if full model not available
                self.model = stt.load("mlx-community/Qwen3-ASR-1.7B-8bit")
            return True
        except Exception as e:
            self.signals.error_message.emit(f"Model load error: {e}")
            return False

    def start(self):
        if not self.model:
            return False
        self.running = True
        self.thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _transcribe_loop(self):
        while self.running:
            try:
                audio_chunk = self.audio_queue.get(timeout=1)
                # Check amplitude with better threshold
                amplitude = np.abs(audio_chunk).mean()
                if amplitude > 0.002:  # Slightly higher threshold to reduce noise
                    # Normalize audio for better quality
                    audio_normalized = audio_chunk / (np.max(np.abs(audio_chunk)) + 1e-8)

                    # Transcribe
                    result = self.model.generate(audio_normalized, language="English")
                    text = result.text.strip()

                    # Filter out common filler words and very short text
                    if text and len(text) > 2 and text.lower() not in ["okay.", "okay", "thank you.", "you", "hmm", "um", "uh", "oh.", "oh"] and text != self.last_text:
                        timestamp = datetime.now().isoformat()
                        with self.buffer_lock:
                            self.transcript_buffer.append({"timestamp": timestamp, "text": text, "source": "auto"})
                            # Evict old entries
                            cutoff = datetime.now().timestamp() - 300
                            while self.transcript_buffer and datetime.fromisoformat(self.transcript_buffer[0]["timestamp"]).timestamp() < cutoff:
                                self.transcript_buffer.popleft()
                        self.signals.update_transcript.emit(text, timestamp, "auto")
                        self.last_text = text
            except queue.Empty:
                continue
            except Exception as e:
                self.signals.error_message.emit(f"Transcription error: {e}")