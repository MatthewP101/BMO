from app.agent.agent import BMOAgent


def start_bmo():
    print("BMO is starting...")

    bmo = BMOAgent()
    bmo.start()
    message = input("You: ")
    response = bmo.respond(message)

    print(f"BMO: {response}")
    print("MY LOYAL SQUIREEEE")


if __name__ == "__main__":
    start_bmo()