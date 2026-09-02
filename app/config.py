import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    # personal settings override the tracked example without entering git
    path = ROOT / "config/config.json"
    if not path.exists():
        path = ROOT / "config/config.example.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)
