import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.memory.memory import initialise_memory, save_memory, get_memories


class TestMemory(unittest.TestCase):
    def test_save_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.memory.database.DATABASE_PATH", Path(directory) / "nested/bmo.db"):
                initialise_memory()
                save_memory("my colour is green")
                self.assertEqual(get_memories(), ["my colour is green"])
