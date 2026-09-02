import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from app.voice.audio_effects import transform_chunks
from app.voice.text_to_speech import TextToSpeech
from app.voice.controller import VoiceController


def tone_chunks(seconds=2, frequency=240):
    samples=(.2*np.sin(2*np.pi*frequency*np.arange(int(seconds*24000))/24000)).astype(np.float32)
    for i in range(0,len(samples),1920):yield samples[i:i+1920],24000


class VoiceTuningTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg needed for DSP checks')
    def test_tuning_changes_pitch_and_duration_independently(self):
        out=np.concatenate([samples for samples,rate in transform_chunks(tone_chunks(),.94,1.)])
        self.assertAlmostEqual(len(out)/24000,2/.94,delta=.12)
        middle=out[4000:24000]
        peak=np.fft.rfftfreq(len(middle),1/24000)[np.argmax(abs(np.fft.rfft(middle)))]
        self.assertAlmostEqual(peak,240*2**(1/12),delta=3)

    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg needed for DSP checks')
    def test_tuned_model_serialization_can_resume_source_on_worker(self):
        speaker=TextToSpeech({'pitch_shift':.4})
        speaker.model=Mock(sample_rate=24000)
        def generate(*args,**kwargs):
            for samples,rate in tone_chunks():
                chunk=Mock();chunk.detach.return_value.cpu.return_value.numpy.return_value=samples
                yield chunk
        speaker.model.generate_audio_stream.side_effect=generate
        result=[];errors=[]
        def run():
            try:result.append(speaker.synthesise('Hello')[0])
            except BaseException as exc:errors.append(exc)
        worker=threading.Thread(target=run,daemon=True);worker.start();worker.join(10)
        self.assertFalse(worker.is_alive(),'Tuned speech deadlocked')
        self.assertEqual(errors,[])
        self.assertGreater(len(result[0]),10000)
        # Repeated audition uses cached model PCM; the tuning still applies.
        again=speaker.synthesise('Hello')[0]
        np.testing.assert_allclose(result[0],again)
        self.assertEqual(speaker.model.generate_audio_stream.call_count,1)

    def test_neutral_voice_needs_no_processor(self):
        speaker=TextToSpeech({})
        with patch.object(speaker,'_generate_chunks',return_value=tone_chunks()),patch('app.voice.text_to_speech.transform_chunks',side_effect=AssertionError):
            self.assertEqual(len(speaker.synthesise('Hello')[0]),48000)

    def test_missing_processor_is_actionable(self):
        with patch('shutil.which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'apt install ffmpeg'):
                list(transform_chunks(tone_chunks(),1.,.1))

    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg needed for DSP checks')
    def test_source_error_propagates_and_close_drains_source(self):
        def broken():
            yield next(tone_chunks())
            raise RuntimeError('source broke')
        with self.assertRaisesRegex(RuntimeError,'source broke'):list(transform_chunks(broken(),1.,.3))
        done=threading.Event()
        def source():
            try:yield from tone_chunks(3)
            finally:done.set()
        stream=transform_chunks(source(),1.,.3)
        next(stream);stream.close()
        self.assertTrue(done.is_set())

    def test_replay_does_not_call_model_or_add_chat_events(self):
        agent=Mock();speaker=Mock();done=threading.Event()
        speaker.speak.side_effect=lambda text,stop,start,end,audio,mode:(start(),done.set())
        controller=VoiceController(agent,{},speaker=speaker)
        self.assertTrue(controller.say('A small adventure.'))
        self.assertTrue(done.wait(2))
        # Wait for Ready, rather than relying on the playback thread's timing.
        while True:
            event=controller.events.get(timeout=2)
            self.assertNotIn(event[0],('heard','token','reply'))
            if event==('state','Ready'):break
        agent.respond.assert_not_called()
        self.assertFalse(controller.busy)
