import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def merge_settings(defaults, personal):
    result = copy.deepcopy(defaults)
    for key, value in personal.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_settings(result[key], value)
        else:
            result[key] = value
    return result


def load_config():
    try:
        defaults = json.loads((ROOT / 'config/config.example.json').read_text(encoding='utf-8'))
        path = ROOT / 'config/config.json'
        personal = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(personal, dict):
            raise ValueError('the top level must be an object')
        settings = merge_settings(defaults, personal)
        for section in ('llm', 'voice', 'ui'):
            if not isinstance(settings.get(section), dict):
                raise ValueError(f'{section} must be an object')
        # Migrate in memory; retain the user's device choices and original file.
        if settings['voice'].get('backend') == 'kokoro':
            settings['voice']['backend'] = 'pocket'
        voice = settings['voice']
        if not isinstance(voice.get('profiles', {}), dict):
            raise ValueError('voice.profiles must be an object')
        if voice.get('reference_voice'):
            voice.setdefault('profiles', {}).setdefault('Original BMO', voice['reference_voice'])
        return settings
    except (OSError, ValueError) as exc:
        raise RuntimeError(f'Cannot read BMO settings: {exc}') from exc


def save_preferences(section, changes):
    path = ROOT / 'config/config.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    data.setdefault(section, {}).update(changes)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, indent=4) + '\n', encoding='utf-8')
    temporary.replace(path)
