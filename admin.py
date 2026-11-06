import os
import asyncio
import aiosqlite

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import db

router = Router(name="admin")

DB_PATH = os.getenv("DB_PATH", "mafia.db")

ROOT_ADMINS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

pending = {}


async def ensure_tables():
    async with aiosqlite.connect(DB_PATH) as con:
        await con.executescript("""
        CREATE TABLE IF NOT EXISTS bot_admins (
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS required_channels (
            channel TEXT PRIMARY KEY
        );
        """)
        await con.commit()


async def is_admin(user_id):
    if user_id in ROOT_ADMINS:
        return True

    await ensure_tables()

    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            "SELECT 1 FROM bot_admins WHERE user_id=?",
            (user_id,)
        )
        return await cur.fetchone() is not None


async def is_blocked(user_id):
    await ensure_tables()

    async with aiosqlite.connect(DB_PATH) as con:
        cur = await con.execute(
            "SELECT 1 FROM blocked_users WHERE user_id=?",
            (user_id,)
        )
        return await cur.fetchone() is not None


def panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data="admin:stats"
            ),
            InlineKeyboardButton(
                text="👥 Foydalanuvchilar",
                callback_data="admin:users"
            )
        ],
        [
            InlineKeyboardButton(
                text="🚫 Bloklash",
                callback_data="admin:ban"
            ),
            InlineKeyboardButton(
                text="♻️ Blokdan chiqarish",
                callback_data="admin:unban"
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Xabar yuborish",
                callback_data="admin:broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                text="👑 Admin qo‘shish",
                callback_data="admin:addadmin"
            ),
            InlineKeyboardButton(
                text="➖ Adminni olish",
                callback_data="admin:deladmin"
            )
        ],
        [
            InlineKeyboardButton(
                text="📡 Majburiy kanallar",
                callback_data="admin:channels"
            )
        ]
    ])


def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data="admin:home"
            )
        ]
    ])


@router.message(Command("admin"))
async def admin_start(message: Message):
    if message.chat.type != "private":
        await message.reply(
            "Admin panelni botning shaxsiy chatida oching: /admin"
        )
        return

    if not await is_admin(message.from_user.id):
        await message.answer("⛔ Sizda admin huquqi yo‘q.")
        return

    await message.answer(
        "👑 <b>MAFIA BOT ADMIN PANELI</b>\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=panel()
    )


@router.callback_query(F.data.startswith("admin:"))
async def admin_buttons(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await call.answer("Ruxsat yo‘q!", show_alert=True)
        return

    action = call.data.split(":")[1]

    if action == "home":
        await call.message.edit_text(
            "👑 ADMIN PANEL",
            reply_markup=panel()
        )

    elif action == "stats":
        stats = await db.get_stats()

        await call.message.edit_text(
            f"📊 <b>STATISTIKA</b>\n\n"
            f"👥 Foydalanuvchilar: {stats['users']}\n"
            f"💬 Guruhlar: {stats['groups']}\n"
            f"🎮 O‘yinlar: {stats['games']}",
            reply_markup=back_button()
        )

    elif action == "users":
        users = await db.recent_users()

        text = "<b>Oxirgi foydalanuvchilar:</b>\n\n"

        for user_id, name, username in users:
            text += f"• {name} — <code>{user_id}</code>\n"

        await call.message.edit_text(
            text[:4000],
            reply_markup=back_button()
        )

    elif action == "channels":
        await ensure_tables()

        async with aiosqlite.connect(DB_PATH) as con:
            rows = await (
                await con.execute(
                    "SELECT channel FROM required_channels"
                )
            ).fetchall()

        channels = "\n".join(
            "• " + row[0] for row in rows
        ) or "Hozircha kanal qo‘shilmagan."

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Kanal qo‘shish",
                    callback_data="admin:channel_add"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➖ Kanalni o‘chirish",
                    callback_data="admin:channel_del"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="admin:home"
                )
            ]
        ])

        await call.message.edit_text(
            "📡 <b>MAJBURIY KANALLAR</b>\n\n" + channels,
            reply_markup=kb
        )

    else:
        pending[call.from_user.id] = action

        prompts = {
            "ban": "Bloklanadigan foydalanuvchi ID sini yuboring.",
            "unban": "Blokdan chiqariladigan ID ni yuboring.",
            "broadcast": "Yuboriladigan xabarni yuboring.",
            "addadmin": "Admin qilinadigan ID ni yuboring.",
            "deladmin": "Admin huquqi olinadigan ID ni yuboring.",
            "channel_add": "Kanal @username yoki ID sini yuboring.",
            "channel_del": "O‘chiriladigan kanalni yuboring."
        }

        await call.message.answer(
            prompts.get(action, "Ma'lumot yuboring.")
        )

    await call.answer()


@router.message()
async def admin_input(message: Message):
    user_id = message.from_user.id
    action = pending.get(user_id)

    if not action:
        return

    if message.chat.type != "private":
        return

    if not await is_admin(user_id):
        return

    value = (message.text or "").strip()

    if not value:
        await message.answer("Matn yuboring.")
        return

    await ensure_tables()

    if action == "broadcast":
        pending.pop(user_id, None)

        ids = await db.all_user_ids()
        sent = 0
        failed = 0

        for target in ids:
            try:
                await message.bot.send_message(target, value)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        await message.answer(
            f"📢 Yuborildi: {sent}\n"
            f"❌ Yetkazilmadi: {failed}",
            reply_markup=panel()
        )
        return

    if action in ("ban", "unban", "addadmin", "deladmin"):
        try:
            target = int(value)
        except ValueError:
            await message.answer("ID faqat raqam bo‘lishi kerak.")
            return

        async with aiosqlite.connect(DB_PATH) as con:
            if action == "ban":
                await con.execute(
                    "INSERT OR IGNORE INTO blocked_users VALUES(?)",
                    (target,)
                )
                result = "🚫 Foydalanuvchi bloklandi."

            elif action == "unban":
                await con.execute(
                    "DELETE FROM blocked_users WHERE user_id=?",
                    (target,)
                )
                result = "♻️ Blokdan chiqarildi."

            elif action == "addadmin":
                if target in ROOT_ADMINS:
                    result = "Bu foydalanuvchi allaqachon bosh admin."
                else:
                    await con.execute(
                        "INSERT OR IGNORE INTO bot_admins VALUES(?)",
                        (target,)
                    )
                    result = "👑 Admin qo‘shildi."

            else:
                if target in ROOT_ADMINS:
                    result = "Asosiy adminni Railway Variables orqali o‘zgartiring."
                else:
                    await con.execute(
                        "DELETE FROM bot_admins WHERE user_id=?",
                        (target,)
                    )
                    result = "➖ Admin huquqi olib tashlandi."

            await con.commit()

        pending.pop(user_id, None)

        await message.answer(
            result,
            reply_markup=panel()
        )

    elif action in ("channel_add", "channel_del"):
        async with aiosqlite.connect(DB_PATH) as con:
            if action == "channel_add":
                await con.execute(
                    "INSERT OR IGNORE INTO required_channels VALUES(?)",
                    (value,)
                )
                result = "📡 Kanal ro‘yxatga qo‘shildi."

            else:
                await con.execute(
                    "DELETE FROM required_channels WHERE channel=?",
                    (value,)
                )
                result = "🗑 Kanal o‘chirildi."

            await con.commit()

        pending.pop(user_id, None)

        await message.answer(
            result + "\nObunani majburiy tekshirish hali ulanmagan.",
            reply_markup=panel()
        )
