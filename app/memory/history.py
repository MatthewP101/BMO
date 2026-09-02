from uuid import uuid4
from app.memory.database import connection, initialise_database

HISTORY_LIMIT = 20


def initialise_history():
    initialise_database()


def create_chat(title='New chat'):
    chat_id = uuid4().hex
    with connection() as db:
        db.execute('INSERT INTO chats(id,title) VALUES (?,?)', (chat_id, title.strip()[:80] or 'New chat'))
    return chat_id


def get_chat(chat_id):
    with connection() as db:
        row = db.execute('SELECT id,title,archived FROM chats WHERE id=?', (chat_id,)).fetchone()
    return dict(zip(('id','title','archived'), row)) if row else None


def list_chats(query='', archived=False):
    # literal substring search; a typed % or _ is not a wildcard
    term = '%' + query.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')[:100] + '%'
    with connection() as db:
        rows = db.execute('''SELECT c.id,c.title,c.updated_at,
            (SELECT count(*) FROM conversation_history h WHERE h.chat_id=c.id)
            FROM chats c WHERE c.archived=? AND (c.title LIKE ? ESCAPE '\\' OR
            EXISTS (SELECT 1 FROM conversation_history h WHERE h.chat_id=c.id AND h.content LIKE ? ESCAPE '\\'))
            ORDER BY c.updated_at DESC,c.rowid DESC LIMIT 100''', (int(archived),term,term)).fetchall()
    return [dict(zip(('id','title','updated_at','messages'),row)) for row in rows]


def rename_chat(chat_id, title):
    title = title.strip()[:80]
    if not title:
        raise ValueError('Give this chat a name.')
    with connection() as db:
        db.execute('UPDATE chats SET title=? WHERE id=?', (title,chat_id))


def archive_chat(chat_id, archived=True):
    with connection() as db:
        db.execute('UPDATE chats SET archived=? WHERE id=?', (int(archived),chat_id))


def save_message(role, content, chat_id='legacy'):
    with connection() as db:
        if not db.execute('SELECT 1 FROM chats WHERE id=?', (chat_id,)).fetchone():
            raise ValueError('This chat no longer exists.')
        db.execute('INSERT INTO conversation_history(role,content,chat_id) VALUES (?,?,?)', (role,content,chat_id))
        db.execute('UPDATE chats SET updated_at=CURRENT_TIMESTAMP WHERE id=?', (chat_id,))


def save_turn(message, reply, chat_id='legacy'):
    # both messages commit together; interrupted turns cannot leave half a pair
    with connection() as db:
        if not db.execute('SELECT 1 FROM chats WHERE id=?', (chat_id,)).fetchone():
            raise ValueError('This chat no longer exists.')
        db.executemany('INSERT INTO conversation_history(role,content,chat_id) VALUES (?,?,?)',
                       [('user',message,chat_id),('assistant',reply,chat_id)])
        title = ' '.join(message.split())[:64]
        db.execute("UPDATE chats SET title=CASE WHEN title='New chat' THEN ? ELSE title END, updated_at=CURRENT_TIMESTAMP WHERE id=?", (title,chat_id))


def get_recent_history(limit=HISTORY_LIMIT, chat_id='legacy', offset=0):
    limit = max(0, min(10000, int(limit)))
    with connection() as db:
        rows = db.execute('SELECT role,content FROM conversation_history WHERE chat_id=? ORDER BY id DESC LIMIT ? OFFSET ?',
                          (chat_id,limit,max(0,int(offset)))).fetchall()
    return rows[::-1]


def export_chat(chat_id):
    # stream the complete transcript; the display may show only its newest portion
    with connection() as db:
        for role, content in db.execute('SELECT role,content FROM conversation_history WHERE chat_id=? ORDER BY id', (chat_id,)):
            yield ('YOU' if role == 'user' else 'BMO') + '\n' + content + '\n\n'
