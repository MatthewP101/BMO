import sqlite3
from pathlib import Path
from app.config import ROOT

DATABASE_PATH = ROOT / "data/bmo.db"


def get_connection():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH, timeout=10)
