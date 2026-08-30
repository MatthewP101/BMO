from app.memory.database import get_connection


HISTORY_LIMIT = 20


def initialise_history():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def save_message(role, content):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO conversation_history (role, content)
        VALUES (?, ?)
        """,
        (role, content)
    )

    connection.commit()
    connection.close()


def get_recent_history(limit=HISTORY_LIMIT):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT role, content
        FROM conversation_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    connection.close()

    # database returned newest first, so reverse it
    rows.reverse()

    return rows