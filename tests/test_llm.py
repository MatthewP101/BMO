import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from app.llm.llm_client import LLMClient


class TestLLM(unittest.TestCase):
    def setUp(self):
        owner = self
        self.status = 200
        self.reply = {"message": {"content": "A real-shaped answer"}}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.path = self.path
                owner.payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(owner.status)
                self.end_headers()
                self.wfile.write(json.dumps(owner.reply).encode())
            def log_message(self, *args):
                pass
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = LLMClient({"model": "qwen3.5:4b", "url": f"http://127.0.0.1:{self.server.server_port}"})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_ollama_contract_and_history(self):
        self.assertEqual(self.client.generate("MyCode", [("user", "Before")]), "A real-shaped answer")
        self.assertEqual(self.path, "/api/chat")
        self.assertFalse(self.payload["stream"])
        self.assertFalse(self.payload["think"])
        self.assertEqual(self.payload["messages"][-1], {"role": "user", "content": "MyCode"})
        self.assertEqual(self.payload["messages"][-2]["content"], "Before")

    def test_missing_model_actionable(self):
        self.status = 404
        with self.assertRaisesRegex(RuntimeError, "ollama pull qwen3.5:4b"):
            self.client.generate("hello")

    def test_empty_reply_rejected(self):
        self.reply = {"message": {"content": " "}}
        with self.assertRaisesRegex(RuntimeError, "no spoken answer"):
            self.client.generate("hello")

    def test_history_bounded(self):
        self.client.generate("Now", [("user", "x" * 3000)] * 100)
        self.assertLessEqual(sum(len(x["content"]) for x in self.payload["messages"][1:-1]), 5000)
