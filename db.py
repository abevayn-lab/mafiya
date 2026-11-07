import os
import aiosqlite

DB_PATH = os.getenv("DATABASE_PATH", "mafia.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bot_admins(
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS blocked_users(
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS required_channels(
            chat_id TEXT PRIMARY KEY,
            title TEXT,
            invite_link TEXT
        );

        CREATE TABLE IF NOT EXISTS groups(
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS group_members(
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            username TEXT,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(chat_id,user_id)
        );

        CREATE TABLE IF NOT EXISTS game_results(
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0
        );
        """)
        await db.commit()


async def save_user(user):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users(user_id, full_name, username)
            VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
            full_name=excluded.full_name,
            username=excluded.username
            """,
            (user.id, user.full_name, user.username)
        )
        await db.commit()


async def save_group(chat):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO groups(chat_id,title)
            VALUES(?,?)
            ON CONFLICT(chat_id) DO UPDATE SET
            title=excluded.title
            """,
            (chat.id, chat.title or str(chat.id))
        )
        await db.

async def save_group_user(chat_id, user):
    if not user or user.is_bot:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO group_members(chat_id,user_id,full_name,username,last_seen)
            VALUES(?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id,user_id) DO UPDATE SET
                full_name=excluded.full_name,
                username=excluded.username,
                last_seen=CURRENT_TIMESTAMP
            """,
            (chat_id, user.id, user.full_name, user.username)
        )
        await db.commit()


async def recent_group_users(chat_id, limit=300):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id,full_name
            FROM group_members
            WHERE chat_id=?
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (chat_id, limit)
        )
        return await cur.fetchall()
commit()


async def group_game(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO groups(chat_id,title)
            VALUES(?,?)
            """,
            (chat_id, str(chat_id))
        )
        await db.commit()


async def add_result(user_id, points, won):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO game_results(user_id, points, wins, games)
            VALUES(?,?,?,1)
            ON CONFLICT(user_id) DO UPDATE SET
                points=points + excluded.points,
                wins=wins + excluded.wins,
                games=games + 1
            """,
            (user_id, points, 1 if won else 0)
        )
        await db.commit()


async def get_result(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT points, wins, games
            FROM game_results
            WHERE user_id=?
            """,
            (user_id,)
        )
        result = await cur.fetchone()
        return result or (0, 0, 0)


async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM groups")
        groups = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM required_channels")
        channels = (await cur.fetchone())[0]

        return users, groups, channels


async def user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]


async def recent_users(limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id,full_name,username
            FROM users
            ORDER BY joined_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return await cur.fetchall()


async def is_blocked(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM blocked_users WHERE user_id=?",
            (user_id,)
        )
        return await cur.fetchone() is not None


async def set_block(user_id, blocked=True):
    async with aiosqlite.connect(DB_PATH) as db:
        if blocked:
            await db.execute(
                "INSERT OR IGNORE INTO blocked_users(user_id) VALUES(?)",
                (user_id,)
            )
        else:
            await db.execute(
                "DELETE FROM blocked_users WHERE user_id=?",
                (user_id,)
            )
        await db.commit()


async def admins():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM bot_admins")
        return [r[0] for r in await cur.fetchall()]


async def add_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO bot_admins(user_id) VALUES(?)",
            (user_id,)
        )
        await db.commit()


async def remove_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM bot_admins WHERE user_id=?",
            (user_id,)
        )
        await db.commit()


async def channels():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT chat_id,title,invite_link FROM required_channels"
        )
        return await cur.fetchall()


async def add_channel(chat_id, title, invite_link=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO required_channels
            (chat_id,title,invite_link)
            VALUES(?,?,?)
            """,
            (str(chat_id), title, invite_link)
        )
        await db.commit()


async def remove_channel(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM required_channels WHERE chat_id=?",
            (str(chat_id),)
        )
        await db.commit()


async def top_players(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT u.user_id, u.full_name, r.points, r.wins, r.games
            FROM game_results r
            LEFT JOIN users u ON u.user_id = r.user_id
            ORDER BY r.points DESC, r.wins DESC, r.games ASC
            LIMIT ?
            """,
            (limit,)
        )
        return await cur.fetchall()
