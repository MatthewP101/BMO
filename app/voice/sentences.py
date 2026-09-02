"""Incremental speech extraction. Fenced code never enters the audio queue."""
import re
from app.voice.text_to_speech import spoken_text


class SpeechSentences:
    def __init__(self, limit=600, chunk_size=180):
        self.limit = max(0, min(2000, limit))
        self.chunk_size = chunk_size
        self.pending = ''
        self.prose = ''
        self.fence = None
        self.has_code = False
        self.used = 0
        self.truncated = False

    def feed(self, text, final=False):
        self.pending += text
        # Retain two characters so a fence split across tokens is recognised.
        while len(self.pending) >= 3 or (final and self.pending):
            marker = self.pending[:3]
            if marker in ('```', '~~~') and (self.fence is None or marker == self.fence):
                self.fence = None if self.fence else marker
                self.has_code = True
                self.pending = self.pending[3:]
                self.prose += ' '
                continue
            if self.fence is None:
                self.prose += self.pending[0]
            self.pending = self.pending[1:]
        out = []
        while self.prose:
            match = re.search(r'[.!?][\"\')]*(?=\s)', self.prose)
            end = match.end() if match else 0
            # Keep markdown link labels/targets together until they close.
            if end and self.prose[:end].count('[') > self.prose[:end].count(']'):
                end = 0
            if not end and len(self.prose) > self.chunk_size:
                end = self.prose.rfind(' ', 0, self.chunk_size)
                if end < 1:
                    end = self.chunk_size
            if not end and final:
                end = len(self.prose)
            if not end:
                break
            raw, self.prose = self.prose[:end], self.prose[end:].lstrip()
            cleaned = spoken_text(raw, 10000)
            if not cleaned:
                continue
            remaining = self.limit - self.used
            if len(cleaned) > remaining:
                self.truncated = True
                cleaned = cleaned[:remaining].rsplit(' ', 1)[0] if remaining > 24 else ''
            if cleaned:
                out.append(cleaned)
                self.used += len(cleaned)
            if self.truncated:
                self.used = self.limit
        if final and self.limit:
            if self.has_code:
                out.append('The code is on screen.')
            elif self.truncated:
                out.append('The rest is in our conversation.')
        return out
