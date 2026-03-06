import re
from datetime import datetime, timedelta

class TriggerMatcher:
    def __init__(self, start_phrases, end_phrases):
        self.start_phrases = [p.lower() for p in start_phrases]
        self.end_phrases = [p.lower() for p in end_phrases]
        self.state = "IDLE"
        self.start_time = None

    def process_segment(self, segment_text, timestamp):
        text = segment_text.lower()
        if self.state == "IDLE":
            for phrase in self.start_phrases:
                if phrase in text:
                    self.state = "CAPTURING"
                    self.start_time = datetime.fromisoformat(timestamp)
                    return "start"
        elif self.state == "CAPTURING":
            for phrase in self.end_phrases:
                if phrase in text:
                    self.state = "IDLE"
                    return "end"
        return None

    def update_phrases(self, start, end):
        self.start_phrases = [p.lower() for p in start]
        self.end_phrases = [p.lower() for p in end]