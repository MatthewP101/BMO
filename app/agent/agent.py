class BMOAgent:
    def start(self):
        print("BMO agent online.")

    def respond(self, message):
        message = message.lower().strip()

        if message in ["hello", "hi", "hey"]:
            return "Hello, my loyal squire!"

        if "your name" in message:
            return "I am BMO!"

        if "how are you" in message:
            return "BMO is doing great!"

        return f"You said: {message}"