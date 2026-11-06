"""Telegram Mafia bot entrypoint (aiogram 3.x)."""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
)
from dotenv import load_dotenv

import db
from game import Game, GAMES, USER_GAME, MAX_PLAYERS, ROLE_NAMES

load_dotenv()
raw_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
log_level = int(raw_level) if raw_level.isdigit() else getattr(logging, raw_level, logging.INFO)
logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mafia-bot")

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
MIN_PLAYERS = max(3, min(20, int(os.getenv("MIN_PLAYERS", "5"))))
dp = Dispatcher()
bot_username = ""


def in_group(message: Message):
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def private_only(message: Message):
    return message.chat.type == ChatType.PRIVATE


@dp.message(CommandStart())
async def start_cmd(message: Message):
    if not private_only(message):
        return
    db.upsert_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    payload = ""
    if message.text and len(message.text.split(maxsplit=1)) > 1:
        payload = message.text.split(maxsplit=1)[1].strip()
    if payload.startswith("join_"):
        try:
            chat_id = int(payload[5:])
        except ValueError:
            await message.answer("❌ O‘yin havolasi noto‘g‘ri.")
            return
        game = GAMES.get(chat_id)
        if not game:
            await message.answer("❌ Bu o‘yin topilmadi yoki ro‘yxatdan o‘tish yopilgan.")
            return
        result = await game.add_player(message.from_user.id, message.from_user.full_name)
        texts = {
            "ok": "✅ O‘yinga muvaffaqiyatli qo‘shildingiz! O‘yin boshlanishini kuting.",
            "already": "Siz allaqachon ro‘yxatdasiz.",
            "full": "O‘yinchilar soni to‘ldi.",
            "busy": "Siz boshqa o‘yinda qatnashyapsiz.",
            "closed": "Ro‘yxatdan o‘tish yopilgan.",
        }
        await message.answer(texts.get(result, "Xatolik yuz berdi."))
        return
    await message.answer(
        "🎭 <b>Mafia botiga xush kelibsiz!</b>\n\n"
        "O‘yin boshlash uchun botni guruhga qo‘shing va guruhda /game yuboring.\n"
        "O‘yinga qo‘shilish, ovoz berish va rollar harakati tugmalar orqali bajariladi.\n\n"
        "/help — yordam\n/profile — profilingiz\n/top — reyting"
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    if not private_only(message):
        return
    await message.answer(
        "<b>Qo‘llanma</b>\n"
        "1. Botga shaxsiy chatda /start yuboring.\n"
        "2. Botni guruhga qo‘shing.\n"
        "3. Guruhda /game yoki /fast yuboring.\n"
        "4. O‘yinchilar «O‘yinga qo‘shilish» tugmasini bosing.\n"
        "5. Boshlash, tungi harakatlar va ovoz berish tugmalar orqali bajariladi.\n\n"
        "Guruh buyruqlari: /game, /fast, /cancelgame."
    )


@dp.message(Command("profile"))
async def profile_cmd(message: Message):
    if not private_only(message):
        return
    db.upsert_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    u = db.get_user(message.from_user.id)
    await message.answer(
        f"👤 <b>{message.from_user.full_name}</b>\n"
        f"⭐ XP: {u['xp']}\n🎮 O‘yinlar: {u['games']}\n🏆 G‘alabalar: {u['wins']}"
    )


@dp.message(Command("top"))
async def top_cmd(message: Message):
    if not private_only(message):
        return
    rows = db.top_users(10)
    if not rows:
        await message.answer("Hozircha reyting bo‘sh.")
        return
    lines = [f"{i}. {r['name']} — ⭐ {r['xp']} XP | 🏆 {r['wins']}" for i, r in enumerate(rows, 1)]
    await message.answer("<b>🏆 TOP 10</b>\n" + "\n".join(lines))


@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if not private_only(message):
        return
    await message.answer(
        f"📊 Foydalanuvchilar: {db.count_users()}\n"
        f"👥 Guruhlar: {db.count_groups()}\n"
        f"🎮 O‘yinlar: {db.total_games()}"
    )


async def create_game(message: Message, fast: bool):
    if not in_group(message):
        await message.answer("Bu buyruq faqat guruhda ishlaydi.")
        return
    if message.chat.id in GAMES:
        await message.answer("Bu guruhda o‘yin allaqachon ochilgan.")
        return
    db.upsert_group(message.chat.id, message.chat.title or "Guruh")
    game = Game(message.bot, bot_username, message.chat.id, message.chat.title or "Guruh",
                message.from_user.id, fast, MIN_PLAYERS)
    GAMES[message.chat.id] = game
    sent = await message.answer(game.lobby_text(), reply_markup=game.lobby_keyboard())
    game.lobby_message_id = sent.message_id
    game.task = asyncio.create_task(game.run())


@dp.message(Command("game"))
async def game_cmd(message: Message):
    await create_game(message, False)


@dp.message(Command("fast"))
async def fast_cmd(message: Message):
    await create_game(message, True)


@dp.message(Command("cancelgame"))
async def cancel_game_cmd(message: Message):
    if not in_group(message):
        return
    game = GAMES.get(message.chat.id)
    if not game:
        await message.answer("Faol ro‘yxatdan o‘tish yo‘q.")
        return
    if message.from_user.id != game.host_id and message.from_user.id not in ADMIN_IDS:
        await message.answer("Faqat o‘yinni ochgan odam bekor qilishi mumkin.")
        return
    await game.cancel()
    await message.answer("❌ O‘yin bekor qilindi.")


@dp.callback_query(F.data.startswith("lobby:start:"))
async def lobby_start_cb(call: CallbackQuery):
    try:
        chat_id = int(call.data.rsplit(":", 1)[1])
    except (ValueError, AttributeError):
        await call.answer("Noto‘g‘ri tugma.", show_alert=True)
        return
    game = GAMES.get(chat_id)
    if not game or call.message.chat.id != chat_id:
        await call.answer("O‘yin topilmadi.", show_alert=True)
        return
    if call.from_user.id != game.host_id and call.from_user.id not in ADMIN_IDS:
        await call.answer("Faqat o‘yinni ochgan odam boshlashi mumkin.", show_alert=True)
        return
    result = await game.start()
    await call.answer({"ok": "Boshlanmoqda!", "few": f"Kamida {game.min_players} o‘yinchi kerak.",
                       "closed": "Ro‘yxatdan o‘tish yopilgan."}.get(result, "Tayyor."), show_alert=result != "ok")


@dp.callback_query(F.data.startswith("lobby:cancel:"))
async def lobby_cancel_cb(call: CallbackQuery):
    chat_id = int(call.data.rsplit(":", 1)[1])
    game = GAMES.get(chat_id)
    if not game:
        await call.answer("O‘yin topilmadi.", show_alert=True)
        return
    if call.from_user.id != game.host_id and call.from_user.id not in ADMIN_IDS:
        await call.answer("Faqat o‘yinni ochgan odam bekor qilishi mumkin.", show_alert=True)
        return
    await game.cancel()
    await call.answer("O‘yin bekor qilindi.")


@dp.callback_query(F.data.startswith("act:"))
async def night_action_cb(call: CallbackQuery):
    try:
        _, chat_id, target_id = call.data.split(":")
        game = GAMES.get(int(chat_id))
        if not game:
            raise ValueError
        result = await game.record_night_action(call.from_user.id, int(target_id))
        await call.answer(result, show_alert=result != "✅ Tanlov qabul qilindi.")
    except (ValueError, TypeError):
        await call.answer("O‘yin topilmadi.", show_alert=True)


@dp.callback_query(F.data.startswith("vote:"))
async def vote_cb(call: CallbackQuery):
    try:
        _, chat_id, target_id = call.data.split(":")
        game = GAMES.get(int(chat_id))
        if not game:
            raise ValueError
        result = await game.record_vote(call.from_user.id, int(target_id))
        await call.answer(result, show_alert=result != "✅ Ovozingiz qabul qilindi.")
    except (ValueError, TypeError):
        await call.answer("O‘yin topilmadi.", show_alert=True)


async def main():
    if not TOKEN or TOKEN == "123456:YOUR_TELEGRAM_BOT_TOKEN":
        raise RuntimeError("BOT_TOKEN topilmadi. Railway Variables ichiga haqiqiy BOT_TOKEN kiriting.")
    db.init()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    global bot_username
    bot_username = me.username or ""
    await bot.set_my_commands(
        [BotCommand(command="start", description="Botni boshlash"),
         BotCommand(command="help", description="Yordam"),
         BotCommand(command="profile", description="Profil"),
         BotCommand(command="top", description="Reyting"),
         BotCommand(command="stats", description="Statistika")],
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        [BotCommand(command="game", description="Oddiy o‘yin"),
         BotCommand(command="fast", description="Tezkor o‘yin"),
         BotCommand(command="cancelgame", description="O‘yinni bekor qilish")],
        scope=BotCommandScopeAllGroupChats(),
    )
    log.info("Bot started: @%s", bot_username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
