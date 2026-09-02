import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from app.agent.character import choose_mode, reaction_for, expression_for, gesture_for, prompt_for
from app.files import attachment_text
from ui.face import FaceMotion, FaceRenderer, EXPRESSIONS, geometry


class MajorExpressionTests(unittest.TestCase):
    def test_context_overrides_affection_and_play_for_serious_requests(self):
        for text in ('You are cute but debug this code', 'Let\'s play after this Python error', 'I am overwhelmed, BMO'):
            mode=choose_mode(text,'play')
            self.assertEqual(mode,'focus')
            self.assertIn(reaction_for(text,mode),('attentive','gentle'))
        self.assertEqual(reaction_for('You are adorable','companion'),'blush')
        self.assertEqual(expression_for('Hello','Oh. You noticed.','companion'),'blush')
        self.assertEqual(expression_for('Help','Oh. You noticed.','focus'),'attentive')
        self.assertIn('small, sincere pleasure',prompt_for('companion','You are cute'))
        self.assertNotIn('small, sincere pleasure',prompt_for('focus','You are cute but fix this'))

    def test_only_exact_gesture_commands_trigger(self):
        self.assertEqual(gesture_for('Game over!')[0],'game_over')
        self.assertIsNone(gesture_for('Explain my game over handler'))

    def test_blush_controls_and_gesture_lifetime(self):
        for setting,expected in [('auto',.65),('always',.65),('off',0.)]:
            motion=FaceMotion(7);motion.blush_mode=setting;motion.blush_strength=.65
            motion.set_expression('blush',0)
            for frame in range(80):motion.step(frame/40)
            self.assertAlmostEqual(motion.values['blush'],expected,places=4)
        motion=FaceMotion(7);motion.set_expression('game_over',0)
        for frame in range(50):motion.step(frame/40)
        self.assertGreater(motion.values['crosses'],.95)
        for frame in range(50,160):motion.step(frame/40)
        self.assertLess(motion.values['crosses'],.001)

    def test_every_expression_stays_inside_narrow_and_wide_face(self):
        for name in EXPRESSIONS:
            for width,height in [(340,82),(700,690),(1200,540)]:
                motion=FaceMotion(4);motion.set_expression(name,0)
                for i in range(150):
                    shape=geometry(width,height,motion.step(i/40))
                    for path in shape['eyes']+shape['cheeks']+shape['crosses']+shape['brows']+[shape['closed'],shape['mouth']]:
                        self.assertTrue(all(0<=x<=width and 0<=y<=height for x,y in zip(path[::2],path[1::2])),name)

    def test_pink_changes_colour_without_changing_character_or_motion(self):
        canvas=Mock();renderer=FaceRenderer(canvas)
        renderer.motion.mode='focus';renderer.motion.set_expression('gentle',0)
        state=vars(renderer.motion).copy()
        renderer.set_theme('pink')
        self.assertEqual(vars(renderer.motion),state)
        self.assertEqual(renderer.colours['face'],'#f0bfd3')

    def test_text_attachment_is_bounded_quoted_and_never_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'MyCase.py'
            file.write_text('```python\nMyClass\n```\n'+'More\n'*3000)
            attached=attachment_text(file)
            self.assertIn('MyCase.py (excerpt; file is longer)',attached)
            self.assertIn('\n````\n',attached)
            self.assertLess(len(attached),6150)
            file.write_bytes(b'Binary\x00file')
            with self.assertRaisesRegex(ValueError,'binary'):attachment_text(file)
