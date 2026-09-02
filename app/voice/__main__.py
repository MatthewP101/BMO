import argparse
from app.config import load_config
from app.voice.speech_to_text import SpeechToText


def main():
    parser = argparse.ArgumentParser(description="BMO audio setup")
    parser.add_argument("--devices", action="store_true")
    parser.add_argument("--download-model", action="store_true")
    args = parser.parse_args()
    if args.devices:
        import sounddevice as sd
        print(sd.query_devices())
    elif args.download_model:
        SpeechToText(load_config()["voice"]).load()
        print("Whisper is ready for offline transcription.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
