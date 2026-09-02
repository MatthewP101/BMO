from app.memory.database import connection, initialise_database


def initialise_memory():
    initialise_database()


def save_memory(content, chat_id='legacy'):
    content = content.strip()
    if not content:
        raise ValueError('Tell me what you want to remember.')
    with connection() as db:
        db.execute('INSERT INTO memories(content,chat_id) SELECT ?,? WHERE NOT EXISTS '
                   '(SELECT 1 FROM memories WHERE content=? AND chat_id=?)', (content,chat_id,content,chat_id))


def get_memories(chat_id='legacy'):
    with connection() as db:
        rows = db.execute('SELECT content FROM memories WHERE chat_id=? ORDER BY id', (chat_id,)).fetchall()
    return [row[0] for row in rows]


def remove_memory(content, chat_id='legacy'):
    with connection() as db:
        db.execute('DELETE FROM memories WHERE content=? AND chat_id=?', (content,chat_id))
