from queue import Queue
from threading import Event, Lock, Thread

from app.voice.speech_to_text import SpeechToText, record_audio
from app.voice.text_to_speech import TextToSpeech


class VoiceController:
    """one active turn; workers report events and never touch tkinter"""
    def __init__(self, agent, settings, recogniser=None, speaker=None, recorder=None):
        self.agent = agent
        self.settings = settings
        self.recogniser = recogniser if recogniser is not None else SpeechToText(settings)
        self.speaker = speaker if speaker is not None else TextToSpeech(settings)
        self.recorder = recorder if recorder is not None else record_audio
        self.events = Queue()
        self.record_stop = Event()
        self.speech_stop = Event()
        self.closed = Event()
        self.lock = Lock()
        self.busy = False

    def emit(self, kind, value):
        if not self.closed.is_set():
            self.events.put((kind, value))

    def start(self, message=None, speak=True):
        with self.lock:
            if self.busy or self.closed.is_set():
                return False
            self.busy = True
            self.record_stop.clear()
            self.speech_stop.clear()
        Thread(target=self._turn, args=(message, speak), daemon=True).start()
        return True

    def _turn(self, message, speak):
        try:
            if message is None:
                self.emit("state", "Preparing microphone")
                audio = self.recorder(self.record_stop, self.settings,
                                      lambda: self.emit("state", "Listening"))
                if self.closed.is_set():
                    return
                self.emit("state", "Transcribing")
                message = self.recogniser.transcribe(audio)
                if not message:
                    self.emit("notice", "I didn't catch any speech. Click Talk and try again.")
                    return
            if self.closed.is_set():
                return
            self.emit("heard", message)
            self.emit("state", "Thinking")
            response = self.agent.respond(message)
            if self.closed.is_set():
                return
            self.emit("reply", response)
            if speak and not self.speech_stop.is_set():
                self.emit("state", "Preparing voice")
                self.speaker.speak(response, self.speech_stop,
                                   lambda: self.emit("state", "Speaking"),
                                   lambda: self.emit("state", "Finishing"))
        except Exception as exc:
            self.emit("error", str(exc) or type(exc).__name__)
        finally:
            with self.lock:
                self.busy = False
                self.emit("state", "Ready")

    def stop_recording(self):
        self.record_stop.set()

    def stop_speaking(self):
        self.speech_stop.set()

    def close(self):
        with self.lock:
            self.closed.set()
            self.record_stop.set()
            self.speech_stop.set()
