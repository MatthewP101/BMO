import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from threading import RLock, Lock
from collections import OrderedDict
from app.voice.audio_effects import transform_chunks

from app.config import ROOT


def strip_fenced_code(text):
    parts, start, fence, has_code = [], 0, None, False
    for match in re.finditer(r'`{3,}|~{3,}', text):
        marker = match.group()
        if fence is None:
            parts.append(text[start:match.start()])
            fence = marker
            has_code = True
        elif marker[0] == fence[0] and len(marker) >= len(fence):
            parts.append(' ')
            start = match.end()
            fence = None
    if fence is None:
        parts.append(text[start:])
    return ''.join(parts), has_code


def spoken_text(text, limit=900):
    # keep executable material on screen instead of reading punctuation aloud
    text, has_code = strip_fenced_code(text)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+', 'the link on screen', text)
    text = re.sub(r'(?m)^\s*(?:#{1,6}\s*|[-*+]\s+|\d+\.\s+)', '', text)
    text = re.sub(r'[`*_]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > limit:
        cut = text[:limit]
        match = list(re.finditer(r'[.!?](?:\s|$)', cut))
        text = cut[:match[-1].end()].strip() if match else cut.rsplit(' ', 1)[0] + '.'
        text += ' The rest is in our conversation.'
    if has_code:
        text += ' The code is on screen.'
    return text.strip()


def audio_shape(samples):
    import numpy as np
    if not len(samples):
        return (0.0, 0.0)
    rms = float(np.sqrt(np.mean(np.square(samples))))
    level = min(1.0, max(0.0, (rms - 0.006) * 9.0))
    crossings = float(np.mean(np.diff(np.signbit(samples)))) if len(samples) > 1 else 0.0
    return (level, min(1.0, crossings * 5))


class TextToSpeech:
    """One persistent CPU model and voice state, shared by sequential turns."""
    def __init__(self, settings):
        self.settings = settings
        self.model = None
        self.voice_state = None
        self.voice_key = None
        self._lock = RLock()
        self._generation_lock = Lock()
        self._cache = OrderedDict()

    def load(self):
        with self._lock:
            self._load()

    def _load(self):
        if self.settings.get('backend', 'pocket') == 'espeak':
            return
        if self.model is None:
            try:
                import torch
                from pocket_tts import TTSModel
            except ImportError as exc:
                raise RuntimeError('Install the voice packages: python -m pip install -r requirements.txt') from exc
            torch.set_num_threads(min(4, max(1, int(self.settings.get('cpu_threads', 2)))))
            try:
                self.model = TTSModel.load_model(language='english')
            except Exception as exc:
                raise RuntimeError('Cannot load Pocket TTS. Connect to the internet for the first download, then run '
                                   'python -m app.voice --download-voice. Details: ' + str(exc)) from exc
        reference = self.settings.get('reference_voice', '').strip()
        source = str((ROOT / reference).resolve()) if reference else self.settings.get('pocket_voice', 'azelma')
        if reference:
            path = Path(source)
            if not path.is_file():
                raise RuntimeError('Reference voice file is missing. Choose another saved voice in Settings or prepare it again with python -m app.voice --reference.')
            if path.suffix.lower() != '.safetensors' and not self.model.has_voice_cloning:
                raise RuntimeError('Reference voices need access to kyutai/pocket-tts on Hugging Face and hf auth login. '
                                   'See docs/FAST_VOICE.md. Clear the reference to use a bundled voice.')
            key = (source, path.stat().st_mtime_ns)
        else:
            key = (source,)
        if self.voice_key != key:
            self.voice_state = self.model.get_state_for_audio_prompt(source)
            self.voice_key = key

    def audio_chunks(self, text, mode='companion'):
        pace = min(1.1,max(.9,float(self.settings.get('pace',1.))))
        pitch = min(1.5,max(-1.5,float(self.settings.get('pitch_shift',0.))))
        # Own serialization here: the tuning producer resumes the source on a
        # worker, so the source must never hold a thread-owned lock across yield.
        with self._generation_lock:
            source = self._generate_chunks(text,mode)
            if abs(pace-1.)<.0001 and abs(pitch)<.0001:
                yield from source
            else:
                yield from transform_chunks(source,pace,pitch)

    def _generate_chunks(self, text, mode='companion'):
        import numpy as np
        backend = self.settings.get('backend', 'pocket')
        volume = min(1.0, max(0.0, float(self.settings.get('volume', 0.85))))
        if backend == 'espeak':
            samples, rate = self._espeak(text)
            yield np.clip(samples * volume, -1, 1), rate
            return
        if backend != 'pocket':
            raise RuntimeError(f'Unknown voice backend: {backend}')
        self.load()
        cache_key = (text,self.voice_key,volume)
        if cache_key in self._cache:
            samples,rate = self._cache[cache_key]
            self._cache.move_to_end(cache_key)
            yield samples,rate
            return
        saved=[]
        saved_samples=0
        # The API copies the cached state; speech must not accumulate a new history.
        chunks = self.model.generate_audio_stream(self.voice_state, text, copy_state=True)
        try:
            for chunk in chunks:
                samples = chunk.detach().cpu().numpy().astype(np.float32, copy=False).reshape(-1)
                samples = np.clip(samples * volume, -1, 1)
                if len(text)<=240 and saved_samples<=self.model.sample_rate*20:
                    saved_samples+=len(samples)
                    saved.append(samples.copy())
                yield samples, self.model.sample_rate
        finally:
            # Pocket's decoder runs in a worker. Drain before reusing the model;
            # otherwise Stop followed by Talk could overlap non-thread-safe calls.
            for _ in chunks:
                pass
        if saved and saved_samples<=self.model.sample_rate*20:
            self._cache[cache_key] = (np.concatenate(saved),self.model.sample_rate)
            while len(self._cache)>6:
                self._cache.popitem(last=False)

    def synthesise(self, text, mode='companion'):
        """File/benchmark API. Live playback uses audio_chunks instead."""
        import numpy as np
        chunks, rate = [], 24000
        for samples, rate in self.audio_chunks(text, mode):
            chunks.append(samples)
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32), rate

    def speak(self, text, stop_event, on_start, on_end, on_audio=None, mode='companion'):
        try:
            import sounddevice as sd
        except (OSError, ImportError) as exc:
            raise RuntimeError('Audio output needs sounddevice and PortAudio: '
                               'python -m pip install -r requirements.txt; sudo apt install libportaudio2') from exc
        from contextlib import ExitStack
        if stop_event.is_set():
            return
        started, aborted = False, False
        chunks = self.audio_chunks(text, mode)
        try:
            with ExitStack() as stack:
                stream = None
                for samples, rate in chunks:
                    if stop_event.is_set():
                        if stream is not None and not aborted:
                            stream.abort()
                            aborted = True
                        continue
                    if stream is None:
                        stream = stack.enter_context(sd.OutputStream(
                            samplerate=rate, channels=1, dtype='float32', blocksize=480,
                            latency='low', device=self.settings.get('output_device')))
                        on_start()
                        started = True
                    for offset in range(0, len(samples), 480):
                        if stop_event.is_set():
                            stream.abort()
                            aborted = True
                            break
                        block = samples[offset:offset + 480]
                        stream.write(block.reshape(-1, 1))
                        if on_audio is not None:
                            on_audio(audio_shape(block))
        except sd.PortAudioError as exc:
            raise RuntimeError('Speaker unavailable. Check Ubuntu Settings > Sound and the selected output device.') from exc
        finally:
            chunks.close()
            if on_audio is not None:
                on_audio((0.0, 0.0))
            if started:
                on_end()

    def _espeak(self, text):
        import numpy as np
        executable = shutil.which('espeak-ng')
        if not executable:
            raise RuntimeError('eSpeak output needs: sudo apt install espeak-ng')
        with tempfile.TemporaryDirectory(prefix='bmo-speech-') as directory:
            path = Path(directory) / 'reply.wav'
            subprocess.run([executable, '-v', self.settings.get('espeak_voice', 'en+f3'),
                            '-p', str(self.settings.get('pitch', 65)), '-s', str(self.settings.get('speed', 155)),
                            '-w', str(path), '--stdin'], input=text, text=True,
                           encoding='utf-8', capture_output=True, check=True, timeout=30)
            with wave.open(str(path), 'rb') as wav:
                rate = wav.getframerate()
                if wav.getsampwidth() != 2:
                    raise RuntimeError('Unsupported eSpeak sample format.')
                samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
            return samples, rate
