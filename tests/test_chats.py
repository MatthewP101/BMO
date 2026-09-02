import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from app.agent.agent import BMOAgent
from app.memory.database import initialise_database, connection
from app.memory.history import (create_chat, get_chat, list_chats, save_turn,
    get_recent_history, archive_chat, rename_chat, export_chat)
from app.memory.memory import save_memory, get_memories, remove_memory


class ChatTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'bmo.db'
        patcher = patch('app.memory.database.DATABASE_PATH', self.path)
        patcher.start(); self.addCleanup(patcher.stop)

    def test_old_database_migrates_without_losing_rows_or_overwriting_backup(self):
        with sqlite3.connect(self.path) as db:
            db.executescript('''CREATE TABLE conversation_history(id INTEGER PRIMARY KEY,role TEXT,content TEXT,created_at TEXT);
                CREATE TABLE memories(id INTEGER PRIMARY KEY,content TEXT);
                INSERT INTO conversation_history VALUES(7,'user','MyCase /Home/BMO','2024-01-01');
                INSERT INTO memories VALUES(5,'Original note');''')
        initialise_database()
        self.assertEqual(get_recent_history(), [('user','MyCase /Home/BMO')])
        self.assertEqual(get_memories(), ['Original note'])
        backup = self.path.with_name('bmo-before-chats.db')
        before = backup.read_bytes()
        with sqlite3.connect(backup) as db:
            self.assertNotIn('chat_id', [r[1] for r in db.execute('PRAGMA table_info(memories)')])
            self.assertEqual(db.execute('SELECT id,content FROM memories').fetchone(),(5,'Original note'))
        save_turn('New','Reply')
        initialise_database()
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(len(get_recent_history()), 3)

    def test_history_notes_search_archive_restore_are_scoped(self):
        initialise_database()
        first,second = create_chat(),create_chat('Other')
        save_turn('My 100% solution','Hello',first)
        save_turn('Different','Answer',second)
        save_memory('Only here',first);save_memory('Only here',first)
        self.assertEqual(get_memories(first),['Only here'])
        self.assertEqual(get_memories(second),[])
        self.assertEqual(get_chat(first)['title'],'My 100% solution')
        self.assertEqual([c['id'] for c in list_chats('%')],[first])
        self.assertEqual(list_chats('_'),[])
        archive_chat(first)
        self.assertNotIn(first,[c['id'] for c in list_chats()])
        self.assertEqual([c['id'] for c in list_chats(archived=True)],[first])
        archive_chat(first,False);rename_chat(first,'Renamed')
        self.assertEqual(get_chat(first)['title'],'Renamed')
        self.assertEqual(''.join(export_chat(first)), 'YOU\nMy 100% solution\n\nBMO\nHello\n\n')
        remove_memory('Only here',second);self.assertEqual(get_memories(first),['Only here'])
        remove_memory('Only here',first);self.assertEqual(get_memories(first),[])

    def test_turn_is_atomic_on_second_insert_failure(self):
        initialise_database(); chat=create_chat()
        with connection() as db:
            db.execute("CREATE TRIGGER reject_reply BEFORE INSERT ON conversation_history WHEN NEW.role='assistant' BEGIN SELECT RAISE(ABORT,'no reply'); END")
        with self.assertRaises(sqlite3.IntegrityError):save_turn('Question','Answer',chat)
        self.assertEqual(get_recent_history(chat_id=chat),[])
        self.assertEqual(get_chat(chat)['title'],'New chat')

    def test_model_only_receives_active_chat_and_late_reply_keeps_origin(self):
        llm=Mock(settings={'history_messages':2,'include_memories':True})
        llm.generate.return_value='Answer'
        agent=BMOAgent(llm)
        one,two=create_chat(),create_chat()
        agent.set_chat(one);agent.respond('remember One secret')
        agent.set_chat(two);agent.respond('Hello')
        self.assertEqual(llm.generate.call_args.kwargs['memories'],[])
        self.assertEqual(llm.generate.call_args.kwargs['history'],[])
        def switch_mid_reply(*args,**kwargs):
            agent.set_chat(one)
            return 'Saved in two'
        llm.generate.side_effect=switch_mid_reply
        agent.respond('Keep this here')
        self.assertEqual(get_recent_history(chat_id=two)[-1][1],'Saved in two')
        self.assertNotIn('Saved in two',''.join(export_chat(one)))

    def test_history_zero_keeps_saved_transcript(self):
        llm=Mock(settings={'history_messages':0,'include_memories':False})
        llm.generate.return_value='Answer'
        agent=BMOAgent(llm)
        agent.respond('One');agent.respond('Two')
        self.assertEqual(llm.generate.call_args.kwargs['history'],[])
        self.assertEqual(len(get_recent_history()),4)
