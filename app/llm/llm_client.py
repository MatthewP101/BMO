from app.config import load_config


class LLMClient:
    def __init__(self):
        config = load_config()
        llm_config = config["llm"]

        self.backend = llm_config["backend"]
        self.model = llm_config["model"]
        self.host = llm_config["host"]
        self.port = llm_config["port"]

    def generate(self, message):
        return (
            f"LLM received: {message} "
            f"[model={self.model}, backend={self.backend}]"
        )