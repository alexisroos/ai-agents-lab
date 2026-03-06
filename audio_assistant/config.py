import json
import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

CONFIG_DIR = Path.home() / ".audio_assistant"
CONFIG_DIR.mkdir(exist_ok=True)

TRIGGERS_FILE = CONFIG_DIR / "triggers.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LOG_FILE = CONFIG_DIR / "app.log"

# Setup logging
logger = logging.getLogger("audio_assistant")
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def load_triggers():
    if TRIGGERS_FILE.exists():
        with open(TRIGGERS_FILE, 'r') as f:
            return json.load(f)
    return {"start": ["the question", "the problem"], "end": ["that right?", "that correct?"]}

def save_triggers(triggers):
    with open(TRIGGERS_FILE, 'w') as f:
        json.dump(triggers, f, indent=2)

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {"mic_device": None, "window_size": [800, 600], "window_pos": [100, 100]}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)