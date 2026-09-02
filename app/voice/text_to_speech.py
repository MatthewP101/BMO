import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


class TextToSpeech:
    def __init__(self, settings):
        self.settings = settings

    def speak(self, text, stop_event, on_start, on_end):
        import sounddevice as sd
        executable = shutil.which("espeak-ng")
        if not executable:
            raise RuntimeError("Voice output needs eSpeak NG: sudo apt install espeak-ng")
        if stop_event.is_set():
            return
        with tempfile.TemporaryDirectory(prefix="bmo-speech-") as directory:
            path = Path(directory) / "reply.wav"
            args = [executable, "-v", self.settings.get("espeak_voice", "en+f3"),
                    "-p", str(self.settings.get("pitch", 65)),
                    "-s", str(self.settings.get("speed", 155)),
                    "-w", str(path), "--stdin"]
            try:
                # text is stdin, never a shell command or a command-line option
                subprocess.run(args, input=text[:6000], text=True, encoding="utf-8",
                               capture_output=True, check=True, timeout=30)
            except (subprocess.SubprocessError, OSError) as exc:
                raise RuntimeError("Speech generation failed. Check your eSpeak voice settings.") from exc
            if stop_event.is_set():
                return
            try:
                with wave.open(str(path), "rb") as wav:
                    if wav.getsampwidth() != 2:
                        raise RuntimeError("Unsupported speech audio format.")
                    with sd.RawOutputStream(samplerate=wav.getframerate(),
                                            channels=wav.getnchannels(), dtype="int16",
                                            device=self.settings.get("output_device")) as stream:
                        on_start()
                        try:
                            while not stop_event.is_set():
                                block = wav.readframes(1024)
                                if not block:
                                    break
                                stream.write(block)
                            if stop_event.is_set():
                                stream.abort()
                            else:
                                stream.stop()
                        finally:
                            on_end()
            except sd.PortAudioError as exc:
                raise RuntimeError("Speaker unavailable. Check Ubuntu Settings > Sound and the configured output device.") from exc
