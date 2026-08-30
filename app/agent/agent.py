from app.agent.personality import BMO_NAME, GREETING, STATUS_RESPONSE

class BMOAgent:
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

        return f"You said: {message}"