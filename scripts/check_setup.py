"""read-only setup report; never starts services or downloads models"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from urllib import request, error
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import ROOT, load_config


def main():
    config = load_config()
    print(f'Python {sys.version.split()[0]} (Pocket TTS supports 3.10–3.14)')
    for name in ['tkinter', 'numpy', 'sounddevice', 'faster_whisper', 'pocket_tts', 'torch']:
        print(f'{name}: ' + ('installed' if importlib.util.find_spec(name) else 'missing'))
    print('Voice backend: ' + config['voice']['backend'])
    print('Voice: ' + (config['voice'].get('reference_voice') or config['voice']['pocket_voice']))
    print('Voice tuning: pace ' + str(config['voice'].get('pace',1.)) + ', pitch ' + str(config['voice'].get('pitch_shift',0.)))
    print('ffmpeg: ' + ('installed' if shutil.which('ffmpeg') else 'optional; needed for pace/pitch changes'))
    print('Fast replies: ' + str(config['llm'].get('fast_replies', True)))
    print('Routine history messages: ' + str(config['llm'].get('history_messages', 2)))
    print('Voice download check: python -m app.voice --download-voice')
    try:
        url = config['llm']['url'].rstrip('/') + '/api/tags'
        with request.urlopen(url, timeout=5) as response:
            models = [m['name'] for m in json.load(response).get('models', [])]
        model = config['llm']['model']
        print(f'Ollama: reachable; {model}: ' + ('installed' if model in models else 'not found'))
    except (error.URLError, OSError, ValueError) as exc:
        print(f'Ollama: unavailable ({type(exc).__name__})')
    print('A microphone/speaker test still needs the actual audio devices.')


if __name__ == '__main__':
    main()
