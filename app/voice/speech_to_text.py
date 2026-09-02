from app.config import ROOT


class SpeechToText:
    def __init__(self, settings):
        self.settings, self.model = settings, None

    def load(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.settings.get('whisper_model', 'base.en'),
                                     device='cpu', compute_type='int8', cpu_threads=4,
                                     download_root=str(ROOT / 'models/whisper'))

    def transcribe(self, audio):
        import numpy as np
        if len(audio) < 4000 or float(np.sqrt(np.mean(audio ** 2))) < 0.003:
            return ''
        self.load()
        segments, _ = self.model.transcribe(audio, language=self.settings.get('language', 'en'),
                                           beam_size=1, vad_filter=True, condition_on_previous_text=False)
        return ' '.join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()


def record_audio(stop_event, settings, on_ready, on_level=None):
    import numpy as np
    import sounddevice as sd
    chunks, audio_error = [], []
    sample_rate = 16000
    max_seconds = min(60, max(1, float(settings.get('max_record_seconds', 30))))
    max_frames = int(sample_rate * max_seconds)
    captured, voiced, silent = 0, 0, 0
    threshold = min(0.2, max(0.003, float(settings.get('speech_threshold', 0.012))))
    silence_limit = sample_rate * max(0.7, float(settings.get('silence_seconds', 1.4)))

    def callback(indata, frames, time_info, status):
        nonlocal captured, voiced, silent
        if status and len(audio_error) < 3:
            audio_error.append(str(status))
        remaining = max_frames - captured
        if remaining > 0:
            block = indata[:remaining, 0].copy()
            chunks.append(block)
            captured += len(block)
            rms = float(np.sqrt(np.mean(block ** 2))) if len(block) else 0
            if on_level:
                on_level(min(1.0, rms * 12))
            if rms >= threshold:
                voiced += len(block)
                silent = 0
            else:
                silent += len(block)
        auto_end = settings.get('auto_finish', True) and voiced >= sample_rate * 0.25 and silent >= silence_limit
        if stop_event.is_set() or captured >= max_frames or auto_end:
            stop_event.set()
            raise sd.CallbackStop
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', blocksize=800,
                            device=settings.get('input_device'), callback=callback):
            on_ready()
            stop_event.wait(max_seconds + 1)
    except sd.PortAudioError as exc:
        raise RuntimeError("Microphone unavailable. Check Ubuntu Settings > Sound; run 'python -m app.voice --devices'.") from exc
    if audio_error:
        raise RuntimeError('Microphone audio dropped out. Close other audio apps and try again.')
    return np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)
