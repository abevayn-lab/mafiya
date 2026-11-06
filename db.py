import os
import aiosqlite

DB_PATH = os.getenv("DB_PATH", "mafia.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as con:
        await con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            username TEXT,
            joined TEXT DEFAULT CURRENT_TIMESTAMP,
            games INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            games INTEGER NOT NULL DEFAULT 0
        );
        """)
        await con.commit()

async def upsert_user(user):
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute("""
            INSERT INTO users(user_id,name,username) VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username
        """, (user.id, user.full_name or "", user.username))
        await con.commit()

async def upsert_group(chat):
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute("""
            INSERT INTO groups(chat_id,title) VALUES(?,?)
            ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title
        """, (chat.id, chat.title or ""))
        await con.commit()

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as con:
        users = (await (await con.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        groups = (await (await con.execute("SELECT COUNT(*) FROM groups")).fetchone())[0]
        games = (await (await con.execute("SELECT COALESCE(SUM(games),0) FROM groups")).fetchone())[0]
        return {"users": users, "groups": groups, "games": games}

async def recent_users(limit=20):
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            "SELECT user_id,name,username FROM users ORDER BY joined DESC LIMIT ?", (limit,)
        )
        return await cur.fetchall()

async def all_user_ids():
    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]

async def add_game_to_group(chat_id):
    async with aiosqlite.connect(DB_PATH) as con:
        await con.execute("UPDATE groups SET games=games+1 WHERE chat_id=?", (chat_id,))
        await con.commit()
