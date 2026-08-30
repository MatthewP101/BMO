from app.agent.agent import BMOAgent
from app.memory.memory import initialise_memory
from ui.bmo_window import BMOWindow


def start_bmo():
    print("BMO is starting...")

    initialise_memory()

    bmo = BMOAgent()
    bmo.start()

    window = BMOWindow(bmo)
    window.run()


if __name__ == "__main__":
    start_bmo()