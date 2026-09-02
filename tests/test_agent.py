import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from app.agent.agent import BMOAgent
from app.memory.history import get_recent_history
from app.memory.memory import get_memories


class TestBMOAgent(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p = patch("app.memory.database.DATABASE_PATH", Path(temp.name) / "bmo.db")
        p.start()
        self.addCleanup(p.stop)
        self.llm = Mock()
        self.llm.generate.return_value = "Hello from the model."
        self.bmo = BMOAgent(llm=self.llm)

    def test_greeting(self):
        self.assertEqual(self.bmo.respond("hello"), "Hello, my loyal squire!")
        self.llm.generate.assert_not_called()

    def test_name(self):
        self.assertEqual(self.bmo.respond("what is your name"), "I am BMO!")

    def test_status(self):
        self.assertEqual(self.bmo.respond("how are you"), "BMO is doing great!")

    def test_case_and_context_survive(self):
        self.bmo.respond("Remember MyProject lives in /home/Dirpy/BMO")
        self.bmo.respond("Explain MyClass in /home/Dirpy/BMO")
        args, kwargs = self.llm.generate.call_args
        self.assertEqual(args[0], "Explain MyClass in /home/Dirpy/BMO")
        self.assertEqual(kwargs["memories"], ["MyProject lives in /home/Dirpy/BMO"])
        self.assertEqual(len(kwargs["history"]), 2)
        self.assertEqual(get_recent_history()[-2][1], args[0])

    def test_failed_request_not_saved_as_conversation(self):
        self.llm.generate.side_effect = RuntimeError("offline")
        with self.assertRaisesRegex(RuntimeError, "offline"):
            self.bmo.respond("Explain loops")
        self.assertEqual(get_recent_history(), [])

    def test_commands_do_not_swallow_unrelated_questions(self):
        self.bmo.respond("Explain what time complexity means")
        self.llm.generate.assert_called_once()

    def test_restart_preserves_memories(self):
        self.bmo.respond("remember Capital Letters")
        restarted = BMOAgent(llm=self.llm)
        self.assertIn("Capital Letters", restarted.respond("what do you remember"))

    def test_blank_and_oversized_input_rejected(self):
        for message in ("  ", "x" * 2001):
            with self.assertRaises(ValueError):
                self.bmo.respond(message)
        self.assertEqual(get_recent_history(), [])
