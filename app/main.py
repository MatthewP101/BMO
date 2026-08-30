from app.agent.agent import BMOAgent
from app.memory.memory import initialise_memory
from ui.bmo_window import BMOWindow
from app.memory.history import initialise_history


def start_bmo():
    print("BMO is starting...")

    initialise_memory()
    initialise_history()

    bmo = BMOAgent()
    bmo.start()

    window = BMOWindow(bmo)
    window.run()


if __name__ == "__main__":
    start_bmo()