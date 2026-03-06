import sys
import threading
import queue
import collections
import subprocess
from datetime import datetime
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit,
    QPushButton, QLabel, QStatusBar, QMessageBox, QDialog, QLineEdit, QListWidget,
    QInputDialog, QComboBox
)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor

from config import load_triggers, save_triggers, load_settings, save_settings
from audio_capture import AudioCapture
from transcription import TranscriptionEngine
from triggers import TriggerMatcher

class WorkerSignals(QObject):
    update_transcript = pyqtSignal(str, str, str)  # text, timestamp, source
    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str)

class AudioAssistant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Assistant")
        self.resize(800, 600)

        # Signals
        self.signals = WorkerSignals()
        self.signals.update_transcript.connect(self.on_update_transcript)
        self.signals.status_message.connect(self.on_status_message)
        self.signals.error_message.connect(self.on_error_message)

        # Load config
        self.triggers = load_triggers()
        self.settings = load_settings()
        self.resize(*self.settings["window_size"])
        self.move(*self.settings["window_pos"])

        # Select mic if not set
        if self.settings["mic_device"] is None:
            import sounddevice as sd
            try:
                devices = sd.query_devices()
                input_devices = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
                if input_devices:
                    dialog = QDialog(self)
                    dialog.setWindowTitle("Select Microphone")
                    layout = QVBoxLayout(dialog)
                    combo = QComboBox()
                    for idx in input_devices:
                        combo.addItem(f"{idx}: {devices[idx]['name']}", idx)
                    layout.addWidget(combo)
                    btn = QPushButton("Select")
                    btn.clicked.connect(lambda: self.set_mic(combo.currentData(), dialog))
                    layout.addWidget(btn)
                    dialog.exec()
                else:
                    QMessageBox.warning(self, "No Microphone", "No input devices found.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to query devices: {e}")

        # Components
        self.audio_capture = AudioCapture(overlap=0.0, device=self.settings["mic_device"])
        self.transcript_buffer = collections.deque()
        self.buffer_lock = threading.Lock()
        self.transcription_engine = TranscriptionEngine(
            self.audio_capture.audio_queue, self.buffer_lock, self.transcript_buffer, self.signals
        )
        self.trigger_matcher = TriggerMatcher(self.triggers["start"], self.triggers["end"])
        self.current_line_start = None  # Track start of current live line
        self.last_sent_text = None  # Cache last sent text for resending when buffer is empty
        self.last_transcript_time = None  # Track last transcription time for pause detection

        # UI
        self.init_ui()

        # Start
        self.start_app()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Set stylesheet for visibility on macOS
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: white;
                color: black;
            }
            QTextEdit {
                background-color: white;
                color: black;
                border: 1px solid #ccc;
            }
            QPushButton {
                background-color: #f0f0f0;
                color: black;
                border: 1px solid #999;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QLabel {
                color: black;
            }
            QComboBox {
                background-color: white;
                color: black;
                border: 1px solid #999;
                padding: 3px;
            }
        """)

        layout = QVBoxLayout(central)

        # Status
        self.status_label = QLabel("Status: ○ Idle")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_send = QPushButton("Send")
        self.btn_selected = QPushButton("Send Selected")
        self.btn_clear = QPushButton("Clear All")
        self.btn_send.clicked.connect(self.send_all)
        self.btn_selected.clicked.connect(self.send_selected)
        self.btn_clear.clicked.connect(self.clear_all)
        button_layout.addWidget(self.btn_send)
        button_layout.addWidget(self.btn_selected)
        button_layout.addWidget(self.btn_clear)
        layout.addLayout(button_layout)

        # Transcript
        layout.addWidget(QLabel("Transcript:"))
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setReadOnly(False)  # Editable so user can fix text before sending
        layout.addWidget(self.transcript_edit)

        # Sent text display
        layout.addWidget(QLabel("Sent to ChatGPT:"))
        self.sent_edit = QTextEdit()
        self.sent_edit.setReadOnly(True)
        self.sent_edit.setMaximumHeight(150)  # Limit height
        layout.addWidget(self.sent_edit)

        # Mic selector
        mic_layout = QHBoxLayout()
        mic_layout.addWidget(QLabel("Microphone:"))
        self.mic_combo = QComboBox()
        self.update_mic_list()
        self.mic_combo.currentIndexChanged.connect(self.set_mic_ui)
        mic_layout.addWidget(self.mic_combo)
        layout.addLayout(mic_layout)

        # Triggers
        trigger_layout = QVBoxLayout()
        trigger_layout.addWidget(QLabel("Monitoring for:"))
        self.start_label = QLabel("START: " + " | ".join(self.triggers["start"]))
        self.end_label = QLabel("END: " + " | ".join(self.triggers["end"]))
        trigger_layout.addWidget(self.start_label)
        trigger_layout.addWidget(self.end_label)
        btn_layout = QHBoxLayout()
        self.btn_add_phrase = QPushButton("+ Add phrase")
        self.btn_edit = QPushButton("Edit")
        self.btn_add_phrase.clicked.connect(self.add_phrase)
        self.btn_edit.clicked.connect(self.edit_phrases)
        btn_layout.addWidget(self.btn_add_phrase)
        btn_layout.addWidget(self.btn_edit)
        trigger_layout.addLayout(btn_layout)
        layout.addLayout(trigger_layout)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Timer for toast
        self.toast_timer = QTimer()
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.clear_status)

        # Timer for periodic clipboard cleaning (every 10 minutes)
        self.clipboard_clean_timer = QTimer()
        self.clipboard_clean_timer.timeout.connect(self.clean_clipboard)
        self.clipboard_clean_timer.start(600000)  # 10 minutes in milliseconds

    def start_app(self):
        if not self.transcription_engine.load_model():
            QMessageBox.critical(self, "Error", "Failed to load model. Check installation.")
            return
        self.audio_capture.start()
        if not self.transcription_engine.start():
            QMessageBox.critical(self, "Error", "Failed to start transcription.")
            return
        self.status_label.setText("Status: ● Listening")

    def on_update_transcript(self, text, timestamp, source):
        if source == "auto":
            # For auto transcriptions, append to current line with space
            cursor = self.transcript_edit.textCursor()
            format = QTextCharFormat()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            format.setBackground(QColor("lightyellow"))

            # Check for pause (3+ seconds since last transcription)
            current_time = datetime.fromisoformat(timestamp)
            should_start_new_line = False

            if self.last_transcript_time is not None:
                time_diff = (current_time - self.last_transcript_time).total_seconds()
                if time_diff > 3:
                    should_start_new_line = True

            self.last_transcript_time = current_time

            if self.current_line_start is None or should_start_new_line:
                # Start new line for first auto text or after pause
                if cursor.position() > 0:
                    cursor.insertText("\n")
                self.current_line_start = cursor.position()
            else:
                # Append with space
                cursor.insertText(" ")

            cursor.insertText(text, format)
            self.transcript_edit.setTextCursor(cursor)
            self.transcript_edit.ensureCursorVisible()
        else:
            # For sent messages, show in sent_edit instead of transcript_edit
            cursor = self.sent_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            if cursor.position() > 0:
                cursor.insertText("\n\n")
            cursor.insertText(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
            self.sent_edit.setTextCursor(cursor)
            self.sent_edit.ensureCursorVisible()
            self.current_line_start = None  # Reset for next auto line
            self.last_transcript_time = None  # Reset pause detection

        # Check triggers
        try:
            action = self.trigger_matcher.process_segment(text, timestamp)
            if action == "start":
                self.signals.status_message.emit("Auto-capture active")
                self.current_line_start = None  # Start new line for capture
            elif action == "end":
                try:
                    start_time = self.trigger_matcher.start_time
                    with self.buffer_lock:
                        extracted_text = "\n".join(s["text"] for s in self.transcript_buffer if datetime.fromisoformat(s["timestamp"]) >= start_time)
                    threading.Thread(target=self.send_to_chatgpt, args=(extracted_text, "auto"), daemon=True).start()
                    self.current_line_start = None  # Reset after send
                except Exception as e:
                    self.signals.error_message.emit(f"Auto-send error: {e}")
            elif action == "timeout":
                self.signals.status_message.emit("Auto-capture timed out")
                self.current_line_start = None  # Reset on timeout
        except Exception as e:
            self.signals.error_message.emit(f"Trigger processing error: {e}")

    def on_status_message(self, msg):
        self.status_bar.showMessage(msg, 3000)

    def on_error_message(self, msg):
        QMessageBox.warning(self, "Error", msg)

    def send_all(self):
        """Send all text from the transcript"""
        try:
            from config import logger
            text = self.transcript_edit.toPlainText().strip()

            if not text:
                # Use cached last sent text if box is empty
                if self.last_sent_text:
                    logger.info("Box empty, resending last sent text")
                    self.signals.status_message.emit("Resending last text")
                    self.send_to_chatgpt(self.last_sent_text, "manual")
                    return
                else:
                    self.signals.status_message.emit("No text to send")
                    logger.warning("No text in box to send")
                    return

            logger.info(f"Sending all text (length: {len(text)})")
            self.current_line_start = None  # Reset for next line
            self.send_to_chatgpt(text, "manual")
        except Exception as e:
            from config import logger
            logger.error(f"Send all error: {e}", exc_info=True)
            self.signals.error_message.emit(f"Send all error: {e}")

    def send_selected(self):
        """Send only the selected text from the transcript"""
        try:
            from config import logger
            cursor = self.transcript_edit.textCursor()
            selected_text = cursor.selectedText()

            if not selected_text.strip():
                self.signals.status_message.emit("No text selected")
                logger.warning("No text selected to send")
                return

            logger.info(f"Sending selected text (length: {len(selected_text)})")
            self.current_line_start = None  # Reset for next line
            self.send_to_chatgpt(selected_text, "selected")
        except Exception as e:
            from config import logger
            logger.error(f"Send selected error: {e}", exc_info=True)
            self.signals.error_message.emit(f"Send selected error: {e}")

    def send_to_chatgpt(self, text, source):
        try:
            from config import logger
            from urllib.parse import quote
            logger.info(f"Attempting to send text (length: {len(text)}): {text[:100]}...")

            # Cache this text for potential resending
            self.last_sent_text = text

            prompt = f"Help me find and answer the question in this text. Give a high-level answer first and then additional structured information at most one page, suitable for responding live in a conversation.\n\n---\n{text}"

            # URL encode the prompt
            encoded_prompt = quote(prompt)

            # Open ChatGPT with prompt in URL (requires Chrome extension)
            url = f"https://chat.openai.com/?q={encoded_prompt}"
            logger.info(f"Opening ChatGPT with URL parameter (prompt length: {len(prompt)})")
            webbrowser.open(url)

            self.signals.status_message.emit(f"Sent {len(text)} chars to ChatGPT via URL - auto-submitting...")

            # Auto-submit after delay for page to load and extension to populate
            threading.Thread(target=self._auto_submit, daemon=True).start()

            # Highlight in transcript
            timestamp = datetime.now().isoformat()
            with self.buffer_lock:
                self.transcript_buffer.append({"timestamp": timestamp, "text": f"[Sent {source}] {text}", "source": source})
            self.signals.update_transcript.emit(f"[Sent {source}] {text}", timestamp, source)
        except Exception as e:
            from config import logger
            logger.error(f"Send error: {e}", exc_info=True)
            self.signals.error_message.emit(f"Send error: {e}")

    def _auto_submit(self):
        """Auto-submit the ChatGPT prompt after extension populates it"""
        try:
            from config import logger
            import pyautogui
            import time

            # Minimal wait for extension to populate
            logger.info("Waiting briefly for extension to populate...")
            time.sleep(0.5)

            # Activate Chrome
            script = '''
                tell application "Google Chrome"
                    activate
                end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True)
            time.sleep(0.5)

            # Press return to submit
            logger.info("Pressing return to submit...")
            pyautogui.press('return')

            logger.info("Auto-submit completed successfully")

        except Exception as e:
            from config import logger
            logger.error(f"Auto-submit error: {e}", exc_info=True)

    def add_phrase(self):
        # Dialog to add phrase
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Phrase")
        layout = QVBoxLayout(dialog)
        combo = QComboBox()
        combo.addItems(["START", "END"])
        layout.addWidget(combo)
        edit = QLineEdit()
        layout.addWidget(edit)
        btn = QPushButton("Add")
        btn.clicked.connect(lambda: self.do_add_phrase(combo.currentText(), edit.text(), dialog))
        layout.addWidget(btn)
        dialog.exec()

    def do_add_phrase(self, type, phrase, dialog):
        if type == "START":
            self.triggers["start"].append(phrase)
        else:
            self.triggers["end"].append(phrase)
        save_triggers(self.triggers)
        self.update_trigger_labels()
        self.trigger_matcher.update_phrases(self.triggers["start"], self.triggers["end"])
        dialog.accept()

    def edit_phrases(self):
        # Simple edit: remove
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Phrases")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for p in self.triggers["start"] + self.triggers["end"]:
            list_widget.addItem(p)
        layout.addWidget(list_widget)
        btn = QPushButton("Remove Selected")
        btn.clicked.connect(lambda: self.do_remove_phrase(list_widget.currentItem(), dialog))
        layout.addWidget(btn)
        dialog.exec()

    def do_remove_phrase(self, item, dialog):
        if item:
            phrase = item.text()
            if phrase in self.triggers["start"]:
                self.triggers["start"].remove(phrase)
            if phrase in self.triggers["end"]:
                self.triggers["end"].remove(phrase)
            save_triggers(self.triggers)
            self.update_trigger_labels()
            self.trigger_matcher.update_phrases(self.triggers["start"], self.triggers["end"])
            dialog.accept()

    def update_trigger_labels(self):
        self.start_label.setText("START: " + " | ".join(self.triggers["start"]))
        self.end_label.setText("END: " + " | ".join(self.triggers["end"]))

    def update_mic_list(self):
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            self.mic_combo.clear()
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    self.mic_combo.addItem(f"{i}: {d['name']}", i)
            # Set current
            if self.settings["mic_device"] is not None:
                index = self.mic_combo.findData(self.settings["mic_device"])
                if index >= 0:
                    self.mic_combo.setCurrentIndex(index)
        except Exception as e:
            self.mic_combo.addItem(f"Error: {e}")

    def set_mic(self, device_index, dialog):
        if device_index is not None:
            self.settings["mic_device"] = device_index
            save_settings(self.settings)
            dialog.accept()

    def set_mic_ui(self):
        index = self.mic_combo.currentData()
        if index is not None and index != self.settings["mic_device"]:
            self.settings["mic_device"] = index
            save_settings(self.settings)

            # Stop current transcription and audio capture
            self.transcription_engine.stop()
            self.audio_capture.stop()

            # Create new audio capture with new device
            self.audio_capture = AudioCapture(overlap=0.0, device=index)

            # Recreate transcription engine with new audio queue
            self.transcription_engine = TranscriptionEngine(
                self.audio_capture.audio_queue, self.buffer_lock, self.transcript_buffer, self.signals
            )

            # Load model for new transcription engine
            if not self.transcription_engine.load_model():
                QMessageBox.critical(self, "Error", "Failed to load model for new microphone")
                return

            # Restart everything
            self.audio_capture.start()
            if not self.transcription_engine.start():
                QMessageBox.critical(self, "Error", "Failed to restart transcription with new microphone")

    def clear_status(self):
        self.status_bar.clearMessage()

    def clear_all(self):
        """Clear transcript and clipboard"""
        self.transcript_edit.clear()
        self.sent_edit.clear()
        with self.buffer_lock:
            self.transcript_buffer.clear()
        self.current_line_start = None
        self.last_sent_text = None  # Clear cached text
        self.last_transcript_time = None  # Reset pause detection
        self.clean_clipboard()
        self.signals.status_message.emit("Cleared transcript and clipboard")

    def clean_clipboard(self):
        """Periodically clean clipboard to avoid leftover content"""
        try:
            subprocess.run(['pbcopy'], input=b'', check=False)
        except Exception:
            pass

    def closeEvent(self, event):
        self.settings["window_size"] = [self.width(), self.height()]
        self.settings["window_pos"] = [self.x(), self.y()]
        save_settings(self.settings)
        self.audio_capture.stop()
        self.transcription_engine.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioAssistant()
    window.show()
    sys.exit(app.exec())