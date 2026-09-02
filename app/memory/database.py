"""short transactions; each thread owns its SQLite connection"""
import sqlite3
from pathlib import Path
from threading import RLock
from contextlib import contextmanager
from app.config import ROOT

DATABASE_PATH = ROOT / 'data/bmo.db'
_schema_lock = RLock()


def get_connection():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


@contextmanager
def connection():
    db = get_connection()
    try:
        with db:
            yield db
    finally:
        db.close()


def initialise_database():
    with _schema_lock, connection() as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version >= 1:
            return
        has_history = db.execute("SELECT 1 FROM sqlite_master WHERE name='conversation_history'").fetchone()
        has_memories = db.execute("SELECT 1 FROM sqlite_master WHERE name='memories'").fetchone()
        if has_history or has_memories:
            # one snapshot before the additive migration; never overwrite it
            backup = Path(DATABASE_PATH).with_name(Path(DATABASE_PATH).stem + '-before-chats.db')
            if not backup.exists():
                target = sqlite3.connect(backup)
                try:
                    db.backup(target)
                finally:
                    target.close()
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archived INTEGER NOT NULL DEFAULT 0)''')
        db.execute("INSERT OR IGNORE INTO chats(id,title) VALUES ('legacy','Earlier conversations')")
        db.execute('''CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, chat_id TEXT NOT NULL DEFAULT 'legacy')''')
        db.execute('''CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL,
            chat_id TEXT NOT NULL DEFAULT 'legacy')''')
        for table in ('conversation_history', 'memories'):
            columns = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            if 'chat_id' not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN chat_id TEXT NOT NULL DEFAULT 'legacy'")
            db.execute(f'CREATE INDEX IF NOT EXISTS {table}_chat_id ON {table}(chat_id,id)')
        db.execute('CREATE INDEX IF NOT EXISTS chats_recent ON chats(archived,updated_at)')
        db.execute('PRAGMA user_version=1')
