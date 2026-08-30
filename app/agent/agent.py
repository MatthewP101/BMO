from app.agent.personality import BMO_NAME, GREETING, STATUS_RESPONSE
from app.tools.tool_registry import run_tool
from app.memory.memory import save_memory, get_memories
from app.memory.history import save_message
from app.llm.llm_client import LLMClient


class BMOAgent:
    def __init__(self):
        self.llm = LLMClient()

    def start(self):
        print("BMO agent online.")

    def respond(self, message):
        message = message.lower().strip()

        save_message("user", message)

        if message in ["hello", "hi", "hey"]:
            response = GREETING

        elif "your name" in message:
            response = f"I am {BMO_NAME}!"

        elif "how are you" in message:
            response = STATUS_RESPONSE

        elif "what time" in message or "current time" in message:
            time = run_tool("get_current_time")
            response = f"It is {time}."

        elif message.startswith("remember "):
            remembered_text = message.removeprefix("remember ").strip()
            save_memory(remembered_text)
            response = "I'll remember that."

        elif message == "what do you remember":
            memories = get_memories()

            if not memories:
                response = "I don't remember anything yet."
            else:
                response = "I remember: " + ", ".join(memories)

        else:
            response = self.llm.generate(message)

        save_message("assistant", response)

        return response