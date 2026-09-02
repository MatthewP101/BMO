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
        # Retain incomplete marker runs across token boundaries. A four-tick
        # outer fence must stay closed around a quoted three-tick code example.
        while len(self.pending) >= 3 or (final and self.pending):
            first = self.pending[0]
            if first in ('`', '~'):
                count = len(self.pending) - len(self.pending.lstrip(first))
                if count == len(self.pending) and not final:
                    break
                if count >= 3:
                    if self.fence is None:
                        self.fence = (first, count)
                        self.has_code = True
                    elif first == self.fence[0] and count >= self.fence[1]:
                        self.fence = None
                    self.pending = self.pending[count:]
                    self.prose += ' '
                    continue
            if self.fence is None:
                self.prose += first
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
