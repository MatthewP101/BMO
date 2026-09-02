import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from app.config import ROOT


def spoken_text(text, limit=900):
    # keep executable material on screen instead of reading punctuation aloud
    has_code = '```' in text
    text = re.sub(r'```[\s\S]*?(?:```|$)', ' ', text)
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
    def __init__(self, settings):
        self.settings = settings
        self.model = None

    def load(self):
        if self.model is not None:
            return
        model = ROOT / self.settings.get('kokoro_model', 'models/kokoro/kokoro-v1.0.onnx')
        voices = ROOT / self.settings.get('kokoro_voices', 'models/kokoro/voices-v1.0.bin')
        if not model.is_file() or not voices.is_file():
            raise RuntimeError('Neural voice not downloaded. Run: python -m app.voice --download-voice')
        try:
            import onnxruntime as rt
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            raise RuntimeError('Install the updated voice packages: python -m pip install -r requirements.txt') from exc
        options = rt.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = rt.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
        self.model = Kokoro.from_session(session, str(voices))

    def synthesise(self, text, mode='companion'):
        import numpy as np
        backend = self.settings.get('backend', 'kokoro')
        if backend == 'espeak':
            return self._espeak(text)
        if backend != 'kokoro':
            raise RuntimeError(f'Unknown voice backend: {backend}')
        self.load()
        speed = min(1.3, max(0.7, float(self.settings.get('kokoro_speed', 0.96))))
        samples, rate = self.model.create(
            text, voice=self.settings.get('kokoro_voice', 'af_sky'),
            speed=speed if mode == 'focus' else speed * 1.015, lang='en-us')
        samples = np.asarray(samples, dtype=np.float32)
        pitch = min(4.0, max(-3.0, float(self.settings.get('pitch_semitones', 0))))
        if pitch:
            executable = shutil.which('ffmpeg')
            if not executable:
                raise RuntimeError('Pitch adjustment needs ffmpeg; set pitch_semitones to 0 or install ffmpeg.')
            ratio = 2 ** (pitch / 12)
            process = subprocess.run(
                [executable, '-hide_banner', '-loglevel', 'error', '-f', 'f32le', '-ar', str(rate),
                 '-ac', '1', '-i', 'pipe:0', '-af', f'asetrate={rate * ratio},aresample={rate},atempo={1 / ratio}',
                 '-f', 'f32le', 'pipe:1'], input=samples.astype('<f4').tobytes(),
                capture_output=True, check=True, timeout=30)
            samples = np.frombuffer(process.stdout, dtype='<f4').copy()
        volume = min(1.0, max(0.0, float(self.settings.get('volume', 0.85))))
        return np.clip(samples * volume, -1, 1), rate

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

    def speak(self, text, stop_event, on_start, on_end, on_audio=None, mode='companion'):
        import sounddevice as sd
        if stop_event.is_set():
            return
        # modest chunks bound synthesis latency and make stop work between chunks
        chunks = re.findall(r'.{1,280}(?:\s|$)|\S{1,280}', text)
        for chunk in chunks:
            if stop_event.is_set():
                break
            samples, rate = self.synthesise(chunk.strip(), mode)
            if stop_event.is_set():
                break
            started = False
            try:
                with sd.OutputStream(samplerate=rate, channels=1, dtype='float32',
                                     blocksize=480, latency='low', device=self.settings.get('output_device')) as stream:
                    on_start()
                    started = True
                    for offset in range(0, len(samples), 480):
                        if stop_event.is_set():
                            stream.abort()
                            break
                        block = samples[offset:offset + 480]
                        stream.write(block.reshape(-1, 1))
                        if on_audio is not None:
                            on_audio(audio_shape(block))
            except sd.PortAudioError as exc:
                raise RuntimeError('Speaker unavailable. Check Ubuntu Settings > Sound and the selected output device.') from exc
            finally:
                if on_audio is not None:
                    on_audio((0.0, 0.0))
                if started:
                    on_end()
