import io
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from queue import Queue
from unittest.mock import Mock, patch
import numpy as np
from app.agent.agent import BMOAgent
from app.config import load_config
from app.llm.llm_client import LLMClient
from app.memory.history import create_chat, get_recent_history, save_turn
from app.voice.__main__ import use_reference, main as voice_main
from app.voice.controller import VoiceController
from ui.bmo_window import BMOWindow


class MajorIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        patched=patch('app.memory.database.DATABASE_PATH',self.root/'bmo.db')
        patched.start();self.addCleanup(patched.stop)

    def test_queued_old_reply_is_handled_before_ui_switches_chat(self):
        bmo=BMOAgent(Mock());other=create_chat()
        window=BMOWindow.__new__(BMOWindow)
        window.bmo=bmo;window.controller=Mock(busy=False,events=Queue())
        window.controller.events.put(('reply','Old answer'))
        window.controller.events.put(('state','Ready'))
        handled=[]
        window.handle_event=lambda k,v:handled.append((bmo.chat_id,k,v))
        window.entry=Mock();window.notice=Mock();window.renderer=Mock();window.started=0
        window.load_current_chat=Mock();window.persist=Mock()
        self.assertTrue(window.switch_chat(other))
        self.assertEqual([h[0] for h in handled],['legacy','legacy'])
        self.assertEqual(bmo.chat_id,other)
        window.controller.busy=True
        window.show_notice=Mock()
        self.assertFalse(window.switch_chat('legacy'))
        self.assertEqual(bmo.chat_id,other)

    def test_real_agent_controller_emits_early_blush_and_saves_only_active_chat(self):
        llm=Mock(settings={'history_messages':0});llm.last_metrics={}
        def generate(message,**kwargs):
            kwargs['on_token']('Oh. You noticed.')
            return 'Oh. You noticed.'
        llm.generate.side_effect=generate
        agent=BMOAgent(llm);chat=create_chat();agent.set_chat(chat)
        controller=VoiceController(agent,{},speaker=Mock())
        controller.start('You are cute',speak=False)
        events=[]
        while True:
            event=controller.events.get(timeout=3);events.append(event)
            if event==('state','Ready'):break
        self.assertLess(events.index(('expression','blush')),events.index(('token','Oh. You noticed.')))
        self.assertEqual(get_recent_history(),[])
        self.assertEqual(get_recent_history(chat_id=chat)[-1][1],'Oh. You noticed.')

    def test_pagination_does_not_repeat_messages(self):
        BMOAgent(Mock())
        for i in range(8):save_turn(f'Q{i}',f'A{i}')
        newest=get_recent_history(6);older=get_recent_history(6,offset=6)
        self.assertEqual(newest[0][1],'Q5')
        self.assertEqual(older[0][1],'Q2')
        self.assertFalse(set(newest)&set(older))

    def test_named_reference_preserves_working_voice_and_existing_profile(self):
        source=self.root/'reference.wav'
        with wave.open(str(source),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
            wav.writeframes((np.sin(np.arange(8*24000)*.1)*9000).astype('<i2').tobytes())
        settings={'reference_voice':'models/pocket/voices/working.safetensors','profiles':{'Expressive BMO':'previous.safetensors'}}
        package=Mock()
        package.export_model_state.side_effect=lambda state,path:Path(path).write_bytes(b'test-state')
        with patch.dict(sys.modules,{'pocket_tts':package}),patch('app.voice.__main__.ROOT',self.root),patch('app.voice.__main__.TextToSpeech'),patch('app.voice.__main__.save_preferences') as save:
            use_reference(source,settings,'Expressive BMO')
        self.assertEqual(settings['profiles']['Original BMO'],'models/pocket/voices/working.safetensors')
        self.assertEqual(settings['profiles']['Expressive BMO (previous)'],'previous.safetensors')
        self.assertEqual(settings['profiles']['Expressive BMO'],settings['reference_voice'])
        self.assertTrue((self.root/settings['reference_voice']).exists())
        save.assert_called_once()

    def test_selecting_bundled_voice_keeps_reference_profile(self):
        (self.root/'config').mkdir()
        defaults={'voice':{'backend':'pocket'},'llm':{},'ui':{}}
        (self.root/'config/config.example.json').write_text(json.dumps(defaults))
        (self.root/'config/config.json').write_text(json.dumps({'voice':{'reference_voice':'working.safetensors'}}))
        with patch('app.config.ROOT',self.root),patch.object(sys,'argv',['voice','--voice','azelma']):
            self.assertEqual(voice_main(),0)
            saved=load_config()['voice']
        self.assertEqual(saved['reference_voice'],'')
        self.assertEqual(saved['profiles']['Original BMO'],'working.safetensors')

    def test_warmup_sends_no_conversation_and_keeps_metrics(self):
        client=LLMClient({'model':'my-qwen','fast_replies':False,'num_ctx':8192})
        client.last_metrics={'seconds':1.2}
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"done":true}')) as urlopen:
            client.warmup()
        request=urlopen.call_args.args[0];payload=json.loads(request.data)
        self.assertTrue(request.full_url.endswith('/api/generate'))
        self.assertNotIn('messages',payload)
        self.assertEqual(payload['prompt'],'')
        self.assertEqual(payload['options']['num_ctx'],8192)
        self.assertEqual(client.last_metrics,{'seconds':1.2})
