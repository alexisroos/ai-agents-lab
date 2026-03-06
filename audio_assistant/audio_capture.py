import sounddevice as sd
import numpy as np
import queue
import threading
import time
from config import logger

class AudioCapture:
    def __init__(self, sample_rate=16000, chunk_duration=1.0, overlap=0.0, device=None):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration)
        self.overlap_size = int(sample_rate * overlap)
        self.overlap_size = 0  # Force to 0
        self.audio_queue = queue.Queue()
        self.running = False
        self.thread = None
        self.device = device

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _capture_loop(self):
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32',
                                blocksize=self.chunk_size, device=self.device) as stream:
                while self.running:
                    data, overflowed = stream.read(self.chunk_size)
                    # Send only the new chunk, don't accumulate
                    self.audio_queue.put(data.flatten())
        except Exception as e:
            logger.error(f"Audio capture error: {e}", exc_info=True)
            self.running = False