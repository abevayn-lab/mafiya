"""SQLite storage for the Telegram Mafia bot."""
import sqlite3
import threading
import time
from pathlib import Path

_DB_PATH = Path(__file__).with_name("mafia.db")
_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_lock = threading.RLock()


def init():
    with _lock:
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT,
            xp INTEGER NOT NULL DEFAULT 0,
            games INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            joined INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            games INTEGER NOT NULL DEFAULT 0
        );
        """)
        _conn.commit()


def _execute(sql, args=(), fetch=None):
    with _lock:
        cur = _conn.execute(sql, args)
        result = cur.fetchone() if fetch == "one" else cur.fetchall() if fetch == "all" else None
        _conn.commit()
        return result


def upsert_user(user_id, name, username=None):
    _execute(
        """INSERT INTO users(user_id,name,username,joined) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username""",
        (user_id, name, username, int(time.time())),
    )


def get_user(user_id):
    return _execute("SELECT * FROM users WHERE user_id=?", (user_id,), "one")


def add_result(user_id, xp, won):
    _execute(
        "UPDATE users SET xp=xp+?, games=games+1, wins=wins+? WHERE user_id=?",
        (int(xp), int(bool(won)), user_id),
    )


def top_users(limit=10):
    return _execute(
        "SELECT * FROM users WHERE games>0 ORDER BY xp DESC, wins DESC LIMIT ?",
        (int(limit),), "all",
    )


def count_users():
    return _execute("SELECT COUNT(*) AS n FROM users", fetch="one")["n"]


def upsert_group(chat_id, title):
    _execute(
        """INSERT INTO groups(chat_id,title) VALUES(?,?)
        ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title""",
        (chat_id, title),
    )


def group_game(chat_id):
    _execute("UPDATE groups SET games=games+1 WHERE chat_id=?", (chat_id,))


def count_groups():
    return _execute("SELECT COUNT(*) AS n FROM groups", fetch="one")["n"]


def total_games():
    return _execute("SELECT COALESCE(SUM(games),0) AS n FROM groups", fetch="one")["n"]
