from queue import Queue, Empty, Full
from threading import Event, Lock, Thread
from time import monotonic

from app.agent.character import choose_mode
from app.llm.llm_client import TurnCancelled
from app.voice.speech_to_text import SpeechToText, record_audio
from app.voice.text_to_speech import TextToSpeech
from app.voice.sentences import SpeechSentences


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
        speech_queue = Queue(maxsize=32)
        generation_done = Event()
        worker = None
        speech_errors = []
        audio_metrics = {}
        streamed = False
        queue_full = False
        sentences = None

        def enqueue(parts):
            nonlocal queue_full
            if not speak or self.speech_stop.is_set() or queue_full:
                return
            for part in parts:
                try:
                    speech_queue.put_nowait(part)
                except Full:
                    queue_full = True
                    break

        def token(piece):
            nonlocal streamed
            streamed = True
            self.emit('token', piece)
            if speak:
                enqueue(sentences.feed(piece))

        def begin_audio():
            if 'first_audio_seconds' not in audio_metrics:
                audio_metrics['first_audio_seconds'] = round(monotonic() - started, 3)
            self.emit('state', 'Speaking')

        def speak_queued():
            try:
                # Load concurrently with Ollama's prefill, only for spoken turns.
                self.speaker.load()
                while not self.speech_stop.is_set():
                    try:
                        text = speech_queue.get(timeout=0.05)
                    except Empty:
                        if generation_done.is_set():
                            break
                        continue
                    self.emit('state', 'Preparing voice')
                    self.speaker.speak(text, self.speech_stop, begin_audio,
                                       lambda: self.emit('state', 'Preparing voice'),
                                       lambda shape: self.emit('audio', shape), active_mode)
            except Exception as exc:
                speech_errors.append(str(exc) or type(exc).__name__)

        try:
            sentences = SpeechSentences(int(self.settings.get('max_spoken_chars', 600)))
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
            if speak and not self.speech_stop.is_set():
                worker = Thread(target=speak_queued, daemon=True)
                worker.start()
            response = self.agent.respond(message, mode=mode, on_token=token, cancel_event=self.cancelled)
            if self.cancelled.is_set():
                return
            self.emit('reply', response)
            self.emit('expression', self.agent.last_expression)
            if speak:
                enqueue(sentences.feed('' if streamed else response, final=True))
            generation_done.set()
            if worker is not None:
                worker.join()
            metrics = getattr(self.agent.llm, 'last_metrics', {})
            metrics = dict(metrics) if isinstance(metrics, dict) else {}
            metrics.update(audio_metrics)
            self.emit('metrics', metrics)
            if metrics.get('truncated'):
                self.emit('notice', 'Reply reached its length limit. Ask BMO to continue.')
            if queue_full:
                self.emit('notice', 'The rest of the answer is in the conversation.')
            for error in speech_errors:
                self.emit('error', error)
        except TurnCancelled:
            self.emit('notice', 'Stopped. The unfinished answer was not saved.')
        except Exception as exc:
            self.emit('error', str(exc) or type(exc).__name__)
        finally:
            generation_done.set()
            self.speech_stop.set()
            if worker is not None:
                worker.join()
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
