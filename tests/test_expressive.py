import json
import math
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from app.agent.character import choose_mode, prompt_for
from app.config import merge_settings
from app.llm.llm_client import LLMClient, TurnCancelled
from app.voice.text_to_speech import audio_shape, spoken_text, TextToSpeech
from ui.face import FaceMotion, FaceRenderer, geometry, layout_for


class TestCharacter(unittest.TestCase):
    def test_serious_needs_override_play(self):
        for text in ['Debug this Python', 'I am overwhelmed', 'No jokes please', 'My exam is tomorrow']:
            with self.subTest(text=text):
                self.assertEqual(choose_mode(text, 'play'), 'focus')
        self.assertEqual(choose_mode('tell me a joke', 'focus'), 'focus')

    def test_focus_followup_and_return_to_play(self):
        self.assertEqual(choose_mode('It still fails', previous='focus'), 'focus')
        self.assertEqual(choose_mode("Let's play", previous='focus'), 'play')
        self.assertIn('No teasing', prompt_for('focus'))

    def test_old_settings_get_new_defaults_without_losing_device(self):
        defaults = {'voice': {'backend': 'kokoro', 'input_device': None}, 'ui': {'fps': 40}}
        merged = merge_settings(defaults, {'voice': {'input_device': 4}})
        self.assertEqual(merged['voice'], {'backend': 'kokoro', 'input_device': 4})
        self.assertIsNone(defaults['voice']['input_device'])


class TestFace(unittest.TestCase):
    def test_panels_fit_and_never_overlap(self):
        for width, height in [(360, 640), (720, 1560), (1560, 720), (800, 480), (1920, 1080), (360, 300)]:
            layout = layout_for(width, height)
            a, b = layout.face, layout.conversation
            with self.subTest(size=(width, height)):
                for x, y, w, h in [a, b]:
                    self.assertGreater(w, 0)
                    self.assertGreater(h, 0)
                    self.assertLessEqual(x + w, width)
                    self.assertLessEqual(y + h, height)
                self.assertTrue(a[0] + a[2] <= b[0] or a[1] + a[3] <= b[1])

    def test_face_geometry_stays_in_panel_during_animation(self):
        for width, height in [(270, 120), (720, 700), (1020, 640), (340, 82)]:
            motion = FaceMotion(123)
            motion.state = 'Speaking'
            for index in range(320):
                now = index / 40
                motion.audio((.8, .4), now)
                shapes = geometry(width, height, motion.step(now))
                for path in shapes['eyes'] + shapes['cheeks'] + [shapes['closed'], shapes['mouth']]:
                    for x, y in zip(path[::2], path[1::2]):
                        self.assertTrue(0 <= x <= width and 0 <= y <= height)

    def test_audio_opens_mouth_and_stale_audio_closes_it(self):
        motion = FaceMotion(2)
        motion.state = 'Speaking'
        for i in range(20):
            now = i / 40
            motion.audio((.8, .3), now)
            motion.step(now)
        self.assertGreater(motion.values['mouth'], .7)
        for i in range(20, 80):
            motion.step(i / 40)
        self.assertLess(motion.values['mouth'], .01)

    def test_reduced_motion_removes_sway_and_lean(self):
        motion = FaceMotion(4)
        motion.reduced = True
        motion.state = 'Listening'
        for i in range(40):
            values = motion.step(i / 40)
        self.assertEqual((values['x'], values['y'], values['tilt'], values['lean']), (0., 0., 0., 1.))

    def test_render_updates_existing_items(self):
        canvas = Mock()
        canvas.winfo_width.return_value = 800
        canvas.winfo_height.return_value = 480
        renderer = FaceRenderer(canvas)
        count = canvas.create_polygon.call_count + canvas.create_line.call_count
        for i in range(80):
            renderer.draw(i / 40)
        self.assertEqual(canvas.create_polygon.call_count + canvas.create_line.call_count, count)
        canvas.delete.assert_not_called()


class TestSpeechPresentation(unittest.TestCase):
    def test_code_stays_on_screen_and_links_are_readable(self):
        text = 'Use this example.\n```python\nprint("secret syntax")\n```\nSee [the docs](https://example.com).'
        spoken = spoken_text(text)
        self.assertNotIn('print', spoken)
        self.assertNotIn('https', spoken)
        self.assertIn('the docs', spoken)
        self.assertIn('code is on screen', spoken)

    def test_long_speech_is_bounded(self):
        text = 'A complete sentence. ' * 300
        speech = spoken_text(text, 120)
        self.assertLess(len(speech), 175)
        self.assertTrue(speech.endswith('conversation.'))

    def test_audio_energy_is_zero_during_silence(self):
        self.assertEqual(audio_shape(np.zeros(480)), (0., 0.))
        samples = np.sin(np.linspace(0, 20, 480)) * .2
        self.assertGreater(audio_shape(samples)[0], 0)

    def test_missing_neural_package_has_setup_instruction(self):
        import sys
        with patch.dict(sys.modules, {'pocket_tts': None, 'torch': Mock()}):
            with self.assertRaisesRegex(RuntimeError, 'requirements.txt'):
                TextToSpeech({}).load()

    def test_neural_backend_reuses_configured_voice(self):
        speaker = TextToSpeech({'pocket_voice': 'cosette', 'volume': .5})
        speaker.model = Mock()
        speaker.model.sample_rate = 24000
        chunk = Mock()
        chunk.detach.return_value.cpu.return_value.numpy.return_value = np.ones(2400, dtype=np.float32) * .2
        speaker.model.generate_audio_stream.side_effect = lambda *a, **k: iter([chunk])
        for _ in range(2):
            samples, rate = speaker.synthesise('Hello', 'focus')
            self.assertEqual(rate, 24000)
            np.testing.assert_allclose(samples, .1)
        speaker.model.get_state_for_audio_prompt.assert_called_once_with('cosette')
        self.assertTrue(speaker.model.generate_audio_stream.call_args.kwargs['copy_state'])


class TestStreaming(unittest.TestCase):
    def response(self, chunks):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.__iter__ = Mock(return_value=iter([json.dumps(c).encode() + b'\n' for c in chunks]))
        return response

    def test_stream_emits_text_not_hidden_thinking(self):
        chunks = [{'message': {'thinking': 'hidden', 'content': ''}},
                  {'message': {'content': 'Hello '}}, {'message': {'content': 'Matthew.'}},
                  {'done': True, 'done_reason': 'stop', 'eval_count': 4, 'eval_duration': 1000000000}]
        heard = []
        client = LLMClient({'model': 'test'})
        with patch('urllib.request.urlopen', return_value=self.response(chunks)):
            self.assertEqual(client.generate('Hi', on_token=heard.append), 'Hello Matthew.')
        self.assertEqual(heard, ['Hello ', 'Matthew.'])
        self.assertEqual(client.last_metrics['tokens_per_second'], 4.)

    def test_disconnect_is_not_success(self):
        with patch('urllib.request.urlopen', return_value=self.response([{'message': {'content': 'Partial'}}])):
            with self.assertRaisesRegex(RuntimeError, 'before the reply finished'):
                LLMClient({'model': 'test'}).generate('Hi', on_token=lambda text: None)

    def test_cancellation_stops_stream(self):
        cancelled = threading.Event()
        def token(text):
            cancelled.set()
        chunks = [{'message': {'content': 'One'}}, {'message': {'content': 'Two'}}, {'done': True}]
        with patch('urllib.request.urlopen', return_value=self.response(chunks)):
            with self.assertRaises(TurnCancelled):
                LLMClient({'model': 'test'}).generate('Hi', on_token=token, cancel_event=cancelled)

    def test_truncation_is_reported(self):
        chunks = [{'message': {'content': 'Partial'}, 'done': True, 'done_reason': 'length'}]
        client = LLMClient({'model': 'test'})
        with patch('urllib.request.urlopen', return_value=self.response(chunks)):
            client.generate('Hi', on_token=lambda text: None)
        self.assertTrue(client.last_metrics['truncated'])
