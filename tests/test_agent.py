import unittest

from app.agent.agent import BMOAgent


class TestBMOAgent(unittest.TestCase):

    def setUp(self):
        self.bmo = BMOAgent()

    def test_greeting(self):
        response = self.bmo.respond("hello")
        self.assertEqual(response, "Hello, my loyal squire!")

    def test_name(self):
        response = self.bmo.respond("what is your name")
        self.assertEqual(response, "I am BMO!")

    def test_status(self):
        response = self.bmo.respond("how are you")
        self.assertEqual(response, "BMO is doing great!")


if __name__ == "__main__":
    unittest.main()