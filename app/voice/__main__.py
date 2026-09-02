import argparse
from pathlib import Path
from urllib import request
from threading import Event

from app.config import ROOT, load_config
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech

VOICE_FILES = {
    'kokoro-v1.0.onnx': 325532387,
    'voices-v1.0.bin': 28214398,
}
VOICE_BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'


def download_voice():
    directory = ROOT / 'models/kokoro'
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in VOICE_FILES.items():
        target = directory / name
        if target.exists() and target.stat().st_size == expected:
            print(f'{name}: already downloaded')
            continue
        partial = target.with_suffix(target.suffix + '.part')
        print(f'Downloading {name} ({expected / 1e6:.0f} MB)...', flush=True)
        try:
            with request.urlopen(VOICE_BASE + name, timeout=60) as source, partial.open('wb') as dest:
                while chunk := source.read(1024 * 1024):
                    dest.write(chunk)
            if partial.stat().st_size != expected:
                raise RuntimeError(f'{name}: unexpected download size; original file preserved. Try again.')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    print('Neural voice ready. Restart BMO.')


def main():
    parser = argparse.ArgumentParser(description='BMO voice setup and checks')
    parser.add_argument('--download-model', action='store_true', help='download the hearing model')
    parser.add_argument('--download-voice', action='store_true', help='download the local neural voice')
    parser.add_argument('--devices', action='store_true')
    parser.add_argument('--test-voice', action='store_true')
    parser.add_argument('--voice', choices=['af_sky', 'af_bella', 'af_heart'])
    args = parser.parse_args()
    settings = load_config()['voice']
    if args.download_voice:
        download_voice()
    if args.download_model:
        SpeechToText(settings).load()
    if args.devices:
        import sounddevice
        print(sounddevice.query_devices())
    if args.test_voice:
        if args.voice:
            settings['kokoro_voice'] = args.voice
        TextToSpeech(settings).speak('Oh, hello. I am a very distinguished little computer. What shall we do today?',
                                     Event(), lambda: None, lambda: None)
    if not any((args.download_model, args.download_voice, args.devices, args.test_voice)):
        parser.print_help()


if __name__ == '__main__':
    main()
