from app.memory.database import get_connection


from app.memory.database import get_connection


def initialise_memory():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def save_memory(content):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO memories (content) VALUES (?)",
        (content,)
    )

    connection.commit()
    connection.close()


def get_memories():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT content FROM memories")
    rows = cursor.fetchall()

    connection.close()

    return [row[0] for row in rows]