import sys
import threading
import unittest
from queue import Empty
from unittest.mock import Mock, MagicMock, patch
import numpy as np
from app.voice.controller import VoiceController
from app.voice.speech_to_text import SpeechToText, record_audio
from app.voice.text_to_speech import TextToSpeech


def collect(controller):
    events = []
    while True:
        event = controller.events.get(timeout=3)
        events.append(event)
        if event == ("state", "Ready"):
            return events


class TestVoice(unittest.TestCase):
    def controller(self, **kwargs):
        agent = Mock()
        agent.respond.return_value = "Hello!"
        recogniser = Mock()
        recogniser.transcribe.return_value = "My Voice"
        speaker = Mock()
        speaker.speak.side_effect = lambda text, stop, begin, end: (begin(), end())
        values = dict(recogniser=recogniser, speaker=speaker,
                      recorder=lambda stop, settings, ready: (ready(), np.ones(16000))[1])
        values.update(kwargs)
        return VoiceController(agent, {}, **values)

    def test_voice_turn_order(self):
        c = self.controller()
        self.assertTrue(c.start())
        events = collect(c)
        states = [v for k, v in events if k == "state"]
        self.assertEqual(states, ["Preparing microphone", "Listening", "Transcribing", "Thinking", "Preparing voice", "Speaking", "Finishing", "Ready"])
        c.agent.respond.assert_called_once_with("My Voice")
        self.assertLess(events.index(("reply", "Hello!")), events.index(("state", "Speaking")))

    def test_muted_text_has_no_microphone_or_speech(self):
        recorder = Mock()
        c = self.controller(recorder=recorder)
        c.start("Typed", speak=False)
        collect(c)
        recorder.assert_not_called()
        c.recogniser.transcribe.assert_not_called()
        c.speaker.speak.assert_not_called()

    def test_empty_transcript_never_calls_model(self):
        c = self.controller()
        c.recogniser.transcribe.return_value = ""
        c.start()
        events = collect(c)
        c.agent.respond.assert_not_called()
        self.assertTrue(any(k == "notice" for k, _ in events))

    def test_audio_failure_recovers_and_preserves_text(self):
        c = self.controller()
        c.speaker.speak.side_effect = RuntimeError("speaker disconnected")
        c.start("hello")
        events = collect(c)
        self.assertIn(("reply", "Hello!"), events)
        self.assertIn(("error", "speaker disconnected"), events)
        self.assertFalse(c.busy)
        self.assertTrue(c.start("again", speak=False))
        collect(c)

    def test_single_turn_and_close_while_listening(self):
        entered = threading.Event()
        finished = threading.Event()
        def record(stop, settings, ready):
            ready()
            entered.set()
            stop.wait(2)
            finished.set()
            return np.ones(16000)
        c = self.controller(recorder=record)
        c.start()
        self.assertTrue(entered.wait(2))
        self.assertFalse(c.start("overlap"))
        c.close()
        self.assertTrue(finished.wait(2))
        c.agent.respond.assert_not_called()
        self.assertFalse(c.start("closed"))

    def test_stop_voice_does_not_stop_response(self):
        c = self.controller()
        entered, release = threading.Event(), threading.Event()
        def respond(message):
            entered.set()
            release.wait(2)
            return "Finished"
        c.agent.respond.side_effect = respond
        c.start("hello")
        self.assertTrue(entered.wait(2))
        c.stop_speaking()
        release.set()
        self.assertIn(("reply", "Finished"), collect(c))
        c.speaker.speak.assert_not_called()

    def test_silence_skips_whisper_loading(self):
        recogniser = SpeechToText({})
        recogniser.load = Mock()
        self.assertEqual(recogniser.transcribe(np.zeros(16000, dtype=np.float32)), "")
        recogniser.load.assert_not_called()

    def test_low_confidence_segments_ignored(self):
        recogniser = SpeechToText({})
        recogniser.model = Mock()
        recogniser.model.transcribe.return_value = ([Mock(text="hello", no_speech_prob=0.1),
                                                     Mock(text="false", no_speech_prob=0.9)], None)
        self.assertEqual(recogniser.transcribe(np.ones(16000, dtype=np.float32)), "hello")

    def test_missing_espeak_is_actionable(self):
        with patch.dict(sys.modules, {"sounddevice": Mock()}), patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "sudo apt install espeak-ng"):
                TextToSpeech({}).speak("hello", threading.Event(), Mock(), Mock())

class TestAudioLifecycle(unittest.TestCase):
    def test_speech_passes_text_as_data_and_brackets_playback(self):
        import wave
        from pathlib import Path
        order = []
        sd = MagicMock()
        sd.PortAudioError = type('PortAudioError', (Exception,), {})
        stream = sd.RawOutputStream.return_value.__enter__.return_value
        stream.write.side_effect = lambda block: order.append('write')
        stream.stop.side_effect = lambda: order.append('drained')
        malicious_text = 'Hello; $(touch /tmp/should-not-exist) --help'
        def synthesise(args, **kwargs):
            self.assertEqual(kwargs['input'], malicious_text)
            self.assertNotIn(malicious_text, args)
            self.assertFalse(kwargs.get('shell', False))
            output = args[args.index('-w') + 1]
            with wave.open(str(output), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(22050)
                wav.writeframes(b'\x01\x00' * 2500)
        with patch.dict(sys.modules, {'sounddevice': sd}), patch('shutil.which', return_value='/usr/bin/espeak-ng'), patch('subprocess.run', side_effect=synthesise):
            TextToSpeech({}).speak(malicious_text, threading.Event(),
                                  lambda: order.append('start'), lambda: order.append('end'))
        self.assertEqual(order[0], 'start')
        self.assertEqual(order[-2:], ['drained', 'end'])
        self.assertIn('write', order)

    def test_speech_stop_aborts_output(self):
        import wave
        stop = threading.Event()
        sd = MagicMock()
        sd.PortAudioError = type('PortAudioError', (Exception,), {})
        stream = sd.RawOutputStream.return_value.__enter__.return_value
        stream.write.side_effect = lambda block: stop.set()
        def synthesise(args, **kwargs):
            with wave.open(args[args.index('-w') + 1], 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(22050)
                wav.writeframes(b'\x01\x00' * 5000)
        ended = Mock()
        with patch.dict(sys.modules, {'sounddevice': sd}), patch('shutil.which', return_value='/usr/bin/espeak-ng'), patch('subprocess.run', side_effect=synthesise):
            TextToSpeech({}).speak('hello', stop, Mock(), ended)
        stream.write.assert_called_once()
        stream.abort.assert_called_once()
        ended.assert_called_once()

    def test_recording_is_bounded_and_closes_input(self):
        sd = MagicMock()
        sd.CallbackStop = type('CallbackStop', (Exception,), {})
        sd.PortAudioError = type('PortAudioError', (Exception,), {})
        stop = threading.Event()
        closed = Mock()
        def stream(**kwargs):
            class Input:
                def __enter__(self):
                    try:
                        kwargs['callback'](np.ones((20000, 1), dtype=np.float32), 20000, None, None)
                    except sd.CallbackStop:
                        pass
                    return self
                def __exit__(self, *args):
                    closed()
            return Input()
        sd.InputStream.side_effect = stream
        with patch.dict(sys.modules, {'sounddevice': sd}):
            audio = record_audio(stop, {'max_record_seconds': 1}, Mock())
        self.assertEqual(audio.shape, (16000,))
        self.assertTrue(stop.is_set())
        closed.assert_called_once()
