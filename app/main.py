from app.agent.agent import BMOAgent


def start_bmo():
    print("BMO is starting...")

    bmo = BMOAgent()
    bmo.start()

    while True:
        message = input("You: ")

        if message.lower() == "exit":
            print("BMO: Goodbye, my loyal squire.")
            break

        response = bmo.respond(message)
        print(f"BMO: {response}")


if __name__ == "__main__":
    start_bmo()