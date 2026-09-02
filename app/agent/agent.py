from app.agent.personality import BMO_NAME, GREETING, STATUS_RESPONSE
from app.tools.tool_registry import run_tool
from app.memory.memory import save_memory, get_memories, initialise_memory
from app.memory.history import save_message, get_recent_history, initialise_history
from app.llm.llm_client import LLMClient


class BMOAgent:
    def __init__(self, llm=None):
        initialise_memory()
        initialise_history()
        self.llm = llm if llm is not None else LLMClient()

    def start(self):
        print("BMO agent online.")

    def respond(self, message):
        message = message.strip()
        if not message:
            raise ValueError("Please say or type a message.")
        if len(message) > 2000:
            raise ValueError("Please keep this voice chat message under 2,000 characters.")
        command = message.casefold()
        history = get_recent_history(12)
        if command in ["hello", "hi", "hey"]:
            response = GREETING
        elif command in ["what is your name", "what is your name?", "what's your name?"]:
            response = f"I am {BMO_NAME}!"
        elif command in ["how are you", "how are you?"]:
            response = STATUS_RESPONSE
        elif command in ["what time is it", "what time is it?", "current time", "what's the time?"]:
            response = f"It is {run_tool('get_current_time')}."
        elif command.startswith("remember "):
            save_memory(message[len("remember "):].strip())
            response = "I'll remember that."
        elif command.rstrip("?") == "what do you remember":
            memories = get_memories()
            response = "I remember: " + ", ".join(memories) if memories else "I don't remember anything yet."
        else:
            response = self.llm.generate(message, history=history, memories=get_memories())
        # failed model requests do not become fictional replies in the history
        save_message("user", message)
        save_message("assistant", response)
        return response
