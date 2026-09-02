from app.config import ROOT


class SpeechToText:
    def __init__(self, settings):
        self.settings = settings
        self.model = None

    def load(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                self.settings.get("whisper_model", "base.en"),
                device="cpu", compute_type="int8", cpu_threads=4,
                download_root=str(ROOT / "models/whisper"),
            )

    def transcribe(self, audio):
        import numpy as np
        if len(audio) < 4000 or float(np.sqrt(np.mean(audio ** 2))) < 0.003:
            return ""
        self.load()
        segments, _ = self.model.transcribe(
            audio, language=self.settings.get("language", "en"),
            beam_size=1, vad_filter=True, condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments
                        if segment.no_speech_prob < 0.6).strip()


def record_audio(stop_event, settings, on_ready):
    import numpy as np
    import sounddevice as sd

    chunks = []
    audio_error = []
    sample_rate = 16000
    max_seconds = min(60, max(1, float(settings.get("max_record_seconds", 30))))
    max_frames = int(sample_rate * max_seconds)
    captured = 0

    def callback(indata, frames, time_info, status):
        nonlocal captured
        if status:
            audio_error.append(str(status))
        remaining = max_frames - captured
        if remaining > 0:
            chunks.append(indata[:remaining, 0].copy())
            captured += min(frames, remaining)
        if captured >= max_frames:
            stop_event.set()
            raise sd.CallbackStop

    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32",
                            device=settings.get("input_device"), callback=callback):
            on_ready()
            stop_event.wait(max_seconds + 1)
    except sd.PortAudioError as exc:
        raise RuntimeError("Microphone unavailable. Choose an input in Ubuntu Settings > Sound; use 'python -m app.voice --devices' to list devices.") from exc
    if audio_error:
        raise RuntimeError("Microphone audio dropped out. Close other audio apps and try again.")
    return np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)
