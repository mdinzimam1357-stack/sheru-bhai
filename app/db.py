"""
db.py - ALL the SQL of the app lives here (plain sqlite3, '?' placeholders).

Dates are stored by SQLite in UTC. We ask SQLite to give them back as ISO text
("2026-11-20T06:30:00Z") and the browser shows them in the visitor's own time zone.
"""
import os
import sqlite3

from flask import current_app, g

HERE = os.path.dirname(os.path.abspath(__file__))


def _iso(column):
    return f"strftime('%Y-%m-%dT%H:%M:%SZ', {column})"


def get_db():
    """One connection per request, kept in Flask's 'g'."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")      # needed for ON DELETE CASCADE
    return g.db


def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def init_db():
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        get_db().executescript(f.read())


# ------------------------------------------------------------------ settings
def read_settings():
    return {r["key"]: r["value"] for r in get_db().execute("SELECT key, value FROM settings")}


def write_settings(values):
    conn = get_db()
    for key, value in values.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    conn.commit()


def delete_settings(keep=()):
    marks = ",".join("?" for _ in keep) or "''"
    get_db().execute(f"DELETE FROM settings WHERE key NOT IN ({marks})", tuple(keep))
    get_db().commit()


# ------------------------------------------------------------- conversations
def create_conversation(title="New chat"):
    cur = get_db().execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    get_db().commit()
    return cur.lastrowid


def get_conversation(conversation_id):
    row = get_db().execute(
        f"SELECT id, title, {_iso('created_at')} AS created_at, {_iso('updated_at')} AS updated_at "
        "FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return dict(row) if row else None


def _like(text):
    """Make user text safe for LIKE (so '%' and '_' are searched literally)."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_conversations(query="", limit=200):
    sql = f"""
        SELECT c.id, c.title, {_iso('c.created_at')} AS created_at, {_iso('c.updated_at')} AS updated_at,
               COUNT(m.id) AS message_count,
               (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY id DESC LIMIT 1) AS preview
        FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id
    """
    params = []
    if query:
        # search the title AND the text of every message in the chat
        sql += """ WHERE c.title LIKE ? ESCAPE '\\'
                   OR EXISTS (SELECT 1 FROM messages x WHERE x.conversation_id = c.id
                              AND x.content LIKE ? ESCAPE '\\') """
        params += [_like(query), _like(query)]
    sql += " GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in get_db().execute(sql, params)]


def rename_conversation(conversation_id, title):
    cur = get_db().execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
    get_db().commit()
    return cur.rowcount


def delete_conversation(conversation_id):
    cur = get_db().execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    get_db().commit()
    return cur.rowcount


def delete_all_conversations():
    cur = get_db().execute("DELETE FROM conversations")       # messages go with them (CASCADE)
    get_db().commit()
    return cur.rowcount


# ------------------------------------------------------------------ messages
def add_message(conversation_id, role, content, model=None):
    conn = get_db()
    conn.execute("INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
                 (conversation_id, role, content, model))
    conn.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
    conn.commit()


def get_messages(conversation_id):
    rows = get_db().execute(
        f"SELECT id, role, content, model, {_iso('created_at')} AS created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))
    return [dict(r) for r in rows]


def recent_messages(conversation_id, limit):
    """The last `limit` messages, oldest first: this is the model's 'memory'."""
    rows = get_db().execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conversation_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def stats():
    conn = get_db()
    return {
        "conversations": conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
        "messages": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        "questions": conn.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'").fetchone()[0],
    }
