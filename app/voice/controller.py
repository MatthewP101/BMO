from queue import Queue
from threading import Event, Lock, Thread
from time import monotonic

from app.agent.character import choose_mode
from app.llm.llm_client import TurnCancelled
from app.voice.speech_to_text import SpeechToText, record_audio
from app.voice.text_to_speech import TextToSpeech, spoken_text


class VoiceController:
    """workers communicate through events; all tkinter work stays on the UI thread"""
    def __init__(self, agent, settings, recogniser=None, speaker=None, recorder=None):
        self.agent, self.settings = agent, settings
        self.recogniser = recogniser if recogniser is not None else SpeechToText(settings)
        self.speaker = speaker if speaker is not None else TextToSpeech(settings)
        self.recorder = recorder if recorder is not None else record_audio
        self.events = Queue()
        self.record_stop, self.speech_stop = Event(), Event()
        self.cancelled, self.closed = Event(), Event()
        self.lock = Lock()
        self.busy = False

    def emit(self, kind, value):
        if not self.closed.is_set():
            self.events.put((kind, value))

    def start(self, message=None, speak=True, mode='auto'):
        with self.lock:
            if self.busy or self.closed.is_set():
                return False
            self.busy = True
            for event in (self.record_stop, self.speech_stop, self.cancelled):
                event.clear()
        Thread(target=self._turn, args=(message, speak, mode), daemon=True).start()
        return True

    def _turn(self, message, speak, mode):
        started = monotonic()
        try:
            if message is None:
                self.emit('state', 'Preparing microphone')
                audio = self.recorder(self.record_stop, self.settings,
                                      lambda: self.emit('state', 'Listening'),
                                      lambda value: self.emit('input_level', value))
                if self.cancelled.is_set():
                    return
                self.emit('state', 'Transcribing')
                message = self.recogniser.transcribe(audio)
                if not message:
                    self.emit('notice', "I didn't catch any speech. Tap Talk to try again.")
                    return
            if self.cancelled.is_set():
                return
            self.emit('heard', message)
            active_mode = choose_mode(message, mode, getattr(self.agent, 'last_mode', 'companion'))
            self.emit('mode', active_mode)
            self.emit('state', 'Thinking')
            response = self.agent.respond(message, mode=mode,
                                          on_token=lambda token: self.emit('token', token),
                                          cancel_event=self.cancelled)
            if self.cancelled.is_set():
                return
            self.emit('reply', response)
            self.emit('expression', self.agent.last_expression)
            metrics = getattr(self.agent.llm, 'last_metrics', {})
            self.emit('metrics', metrics if isinstance(metrics, dict) else {})
            if isinstance(metrics, dict) and metrics.get('truncated'):
                self.emit('notice', 'Reply reached its length limit. Ask BMO to continue.')
            if speak and not self.speech_stop.is_set():
                text = spoken_text(response, int(self.settings.get('max_spoken_chars', 900)))
                if text:
                    self.emit('state', 'Preparing voice')
                    self.speaker.speak(text, self.speech_stop,
                                       lambda: self.emit('state', 'Speaking'),
                                       lambda: self.emit('state', 'Preparing voice'),
                                       lambda shape: self.emit('audio', shape), active_mode)
        except TurnCancelled:
            self.emit('notice', 'Stopped. The unfinished answer was not saved.')
        except Exception as exc:
            self.emit('error', str(exc) or type(exc).__name__)
        finally:
            self.emit('audio', (0.0, 0.0))
            self.emit('elapsed', monotonic() - started)
            with self.lock:
                self.busy = False
                self.emit('state', 'Ready')

    def stop_recording(self):
        self.record_stop.set()

    def stop_speaking(self):
        self.speech_stop.set()

    def stop(self):
        self.cancelled.set()
        self.record_stop.set()
        self.speech_stop.set()
        self.emit('state', 'Stopping')

    def close(self):
        self.closed.set()
        self.stop()
