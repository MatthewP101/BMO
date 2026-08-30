from app.agent.personality import BMO_NAME, GREETING, STATUS_RESPONSE
from app.tools.tool_registry import run_tool
from app.memory.memory import save_memory, get_memories
from app.llm.llm_client import LLMClient


class BMOAgent:
    def __init__(self):
            self.llm = LLMClient()

    def start(self):
        print("BMO agent online.")

    def respond(self, message):
        message = message.lower().strip()

        if message in ["hello", "hi", "hey"]:
            return GREETING

        if "your name" in message:
            return f"I am {BMO_NAME}!"

        if "how are you" in message:
            return STATUS_RESPONSE

        if "what time" in message or "current time" in message:
            time = run_tool("get_current_time")
            return f"It is {time}."

        if message.startswith("remember "):
            remembered_text = message.removeprefix("remember ").strip()
            save_memory(remembered_text)
            return "I'll remember that."

        if message == "what do you remember":
            memories = get_memories()

            if not memories:
                return "I don't remember anything yet."

            return "I remember: " + ", ".join(memories)

        return self.llm.generate(message)