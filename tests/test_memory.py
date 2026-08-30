import os
import unittest

from app.memory import database
from app.memory.memory import initialise_memory, save_memory, get_memories


class TestMemory(unittest.TestCase):

    def setUp(self):
        database.DATABASE_PATH = "data/test_bmo.db"

        if os.path.exists(database.DATABASE_PATH):
            os.remove(database.DATABASE_PATH)

        initialise_memory()

    def tearDown(self):
        if os.path.exists(database.DATABASE_PATH):
            os.remove(database.DATABASE_PATH)

    def test_save_memory(self):
        save_memory("my colour is green")

        memories = get_memories()

        self.assertIn("my colour is green", memories)


if __name__ == "__main__":
    unittest.main()