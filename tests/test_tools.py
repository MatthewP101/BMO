import unittest

from app.tools.tool_registry import run_tool


class TestTools(unittest.TestCase):

    def test_current_time_tool(self):
        result = run_tool("get_current_time")

        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_missing_tool(self):
        result = run_tool("does_not_exist")

        self.assertEqual(result, "Tool not found.")


if __name__ == "__main__":
    unittest.main()