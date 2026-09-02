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
    print(f'Python {sys.version.split()[0]} (neural voice supports 3.10–3.13)')
    for name in ['tkinter', 'numpy', 'sounddevice', 'faster_whisper', 'kokoro_onnx', 'onnxruntime']:
        print(f'{name}: ' + ('installed' if importlib.util.find_spec(name) else 'missing'))
    for key in ['kokoro_model', 'kokoro_voices']:
        path = ROOT / config['voice'][key]
        print(f'{key}: ' + ('present' if path.is_file() else 'missing; python -m app.voice --download-voice'))
    print('ffmpeg: ' + ('installed' if shutil.which('ffmpeg') else 'missing (only needed for pitch adjustment)'))
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
