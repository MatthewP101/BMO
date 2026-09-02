import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.config import load_config
from app.llm.llm_client import LLMClient
from app.voice.controller import VoiceController
from app.voice.sentences import SpeechSentences
from app.voice.text_to_speech import TextToSpeech


class SentenceTests(unittest.TestCase):
    def speech(self, text, stride=1, limit=600):
        buffer = SpeechSentences(limit)
        parts = []
        for offset in range(0, len(text), stride):
            parts.extend(buffer.feed(text[offset:offset + stride]))
        return ' '.join(parts + buffer.feed('', final=True))

    def test_every_fence_split_hides_code(self):
        for fence in ('```', '~~~'):
            for stride in range(1, 10):
                source = f'Here is the fix.\n{fence}python\nSECRET.run()\n{fence}\nTry it now.'
                speech = self.speech(source, stride)
                self.assertNotIn('SECRET', speech)
                self.assertNotIn('python', speech)
                self.assertIn('Try it now.', speech)
                self.assertEqual(speech.count('The code is on screen.'), 1)

    def test_unclosed_code_is_never_spoken(self):
        self.assertNotIn('SECRET', self.speech('One thing. ```py\nSECRET'))

    def test_bound_and_final_fragment(self):
        self.assertEqual(self.speech('A small final thought'), 'A small final thought')
        self.assertLess(len(self.speech('Sentence. ' * 1000, limit=100)), 150)

    def test_sentence_arrives_before_generation_finishes(self):
        buffer = SpeechSentences()
        self.assertEqual(buffer.feed('Hello, Matthew. Let'), ['Hello, Matthew.'])


class FastControllerTests(unittest.TestCase):
    def controller(self):
        agent = Mock()
        agent.last_mode = 'companion'
        agent.last_expression = 'neutral'
        agent.llm.last_metrics = {}
        speaker = Mock()
        return VoiceController(agent, {}, speaker=speaker, recogniser=Mock()), speaker

    def finished(self, controller):
        events = []
        while True:
            event = controller.events.get(timeout=3)
            events.append(event)
            if event == ('state', 'Ready'):
                return events

    def test_audio_starts_while_model_is_still_generating(self):
        c, speaker = self.controller()
        audio_started = threading.Event()
        def speak(text, stop, begin, end, audio, mode):
            begin()
            audio_started.set()
            end()
        speaker.speak.side_effect = speak
        def respond(message, **kw):
            kw['on_token']('Hello, Matthew. Here')
            if not audio_started.wait(2):
                raise RuntimeError('Speech incorrectly waited for the full response')
            kw['on_token'](' is another thought.')
            return 'Hello, Matthew. Here is another thought.'
        c.agent.respond.side_effect = respond
        c.start('hello')
        events = self.finished(c)
        self.assertLess(events.index(('state', 'Speaking')), events.index(('reply', 'Hello, Matthew. Here is another thought.')))
        self.assertEqual([x.args[0] for x in speaker.speak.call_args_list], ['Hello, Matthew.', 'Here is another thought.'])
        self.assertTrue(any(k == 'metrics' and 'first_audio_seconds' in v for k,v in events))

    def test_stop_keeps_next_turn_out_until_audio_worker_finishes(self):
        c, speaker = self.controller()
        entered, release = threading.Event(), threading.Event()
        def speak(*args):
            entered.set()
            release.wait(2)
        speaker.speak.side_effect = speak
        c.agent.respond.side_effect = lambda message, **kw: (kw['on_token']('One sentence. Two more.'), 'One sentence. Two more.')[1]
        c.start('hello')
        self.assertTrue(entered.wait(2))
        c.stop()
        self.assertFalse(c.start('overlap'))
        release.set()
        self.finished(c)
        self.assertEqual(speaker.speak.call_count, 1)

    def test_voice_failure_does_not_corrupt_streamed_reply(self):
        c, speaker = self.controller()
        speaker.load.side_effect = RuntimeError('voice offline')
        def respond(message, **kw):
            kw['on_token']('The answer.')
            return 'The answer.'
        c.agent.respond.side_effect = respond
        c.start('hello')
        events = self.finished(c)
        self.assertLess(events.index(('reply', 'The answer.')), events.index(('error', 'voice offline')))

    def test_muting_does_not_even_load_speech_model(self):
        c, speaker = self.controller()
        c.agent.respond.return_value = 'Hello.'
        c.start('hello', speak=False)
        self.finished(c)
        speaker.load.assert_not_called()
        speaker.speak.assert_not_called()


class ConfigurationTests(unittest.TestCase):
    def test_legacy_kokoro_migrates_but_preserves_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config').mkdir()
            (root / 'config/config.example.json').write_text(json.dumps({'llm': {}, 'voice': {'backend': 'pocket'}, 'ui': {}}))
            personal = json.dumps({'voice': {'backend': 'kokoro', 'input_device': 3}})
            (root / 'config/config.json').write_text(personal)
            with patch('app.config.ROOT', root):
                config = load_config()
            self.assertEqual(config['voice']['backend'], 'pocket')
            self.assertEqual(config['voice']['input_device'], 3)
            self.assertEqual((root / 'config/config.json').read_text(), personal)

    def test_reference_access_failure_is_actionable(self):
        with tempfile.NamedTemporaryFile(suffix='.wav') as source:
            speaker = TextToSpeech({'reference_voice': source.name})
            speaker.model = Mock(has_voice_cloning=False)
            with self.assertRaisesRegex(RuntimeError, 'hf auth login'):
                speaker.load()
            speaker.model.get_state_for_audio_prompt.assert_not_called()

    def test_old_large_limits_are_reduced_in_fast_profile(self):
        import io
        payloads = []
        def response(req, **kwargs):
            payloads.append(json.loads(req.data))
            return io.BytesIO(b'{"message":{"content":"Hello"}}')
        client = LLMClient({'model':'test', 'num_ctx':8192, 'chat_tokens':360})
        with patch('urllib.request.urlopen', side_effect=response):
            client.generate('Hi', history=[('user','old')] * 16)
        payload = payloads[0]
        self.assertEqual(payload['options']['num_ctx'], 4096)
        self.assertEqual(payload['options']['num_predict'], 160)
        self.assertEqual(len(payload['messages']), 4)


class ReferenceTests(unittest.TestCase):
    def test_silent_reference_does_not_change_settings(self):
        import wave
        from app.voice.__main__ import use_reference
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'silent.wav'
            with wave.open(str(source), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b'\0\0' * 24000 * 8)
            with patch.dict(sys.modules, {'pocket_tts': Mock()}), patch('app.voice.__main__.save_preferences') as save:
                with self.assertRaisesRegex(ValueError, 'silent or too quiet'):
                    use_reference(source, {})
                save.assert_not_called()

    def test_missing_model_access_keeps_existing_voice(self):
        import wave
        import numpy as np
        from app.voice.__main__ import use_reference
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'reference.wav'
            samples = (np.sin(np.arange(24000 * 8) * .1) * 10000).astype('<i2')
            with wave.open(str(source), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(samples.tobytes())
            settings = {'pocket_voice': 'azelma'}
            with patch.dict(sys.modules, {'pocket_tts': Mock()}), patch('app.voice.__main__.TextToSpeech') as cls, patch('app.voice.__main__.save_preferences') as save:
                cls.return_value.load.side_effect = RuntimeError('model access needed')
                with self.assertRaisesRegex(RuntimeError, 'model access needed'):
                    use_reference(source, settings)
                self.assertEqual(settings, {'pocket_voice': 'azelma'})
                save.assert_not_called()
