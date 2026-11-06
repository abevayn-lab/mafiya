import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from dotenv import load_dotenv

import db
from admin import router as admin_router, is_blocked
from game import router as game_router

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("BOT_TOKEN Railway Variables ichida kiritilmagan.")

def parse_ids(raw):
    result = set()
    for item in raw.split(","):
        item = item.strip()
        if item.isdigit():
            result.add(int(item))
    return result

ADMIN_IDS = parse_ids(os.getenv("ADMIN_IDS", ""))
if not ADMIN_IDS:
    logging.warning("ADMIN_IDS bo'sh. /admin hech kimga ochilmaydi.")

level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

dp = Dispatcher()
dp.include_router(game_router)
dp.include_router(admin_router)

@dp.message(Command("start"))
async def start_cmd(message: Message):
    if await is_blocked(message.from_user.id):
        await message.answer("⛔ Siz botdan foydalanish huquqidan mahrum qilingansiz.")
        return
    await db.upsert_user(message.from_user)
    await message.answer(
        "🕵️ <b>Mafia botiga xush kelibsiz!</b>\n\n"
        "Guruhda o'yin ochish: /game\n"
        "Tezkor o'yin: /fast\n"
        "Yordam: /help"
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "<b>Buyruqlar</b>\n"
        "/start — botni boshlash\n"
        "/game — guruhda o'yin ochish\n"
        "/fast — tezkor o'yin ochish\n"
        "/cancelgame — o'yinni bekor qilish\n"
        "/admin — boshqaruv paneli (faqat admin)"
    )

async def main():
    await db.init_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    logging.info("Bot ishga tushdi: @%s (%s)", me.username, me.id)
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Botni boshlash"),
            BotCommand(command="help", description="Yordam"),
            BotCommand(command="game", description="Guruhda o'yin ochish"),
            BotCommand(command="fast", description="Tezkor o'yin"),
            BotCommand(command="cancelgame", description="O'yinni bekor qilish"),
            BotCommand(command="admin", description="Admin panel"),
        ])
    except Exception:
        logging.exception("Bot komandalarini sozlashda xatolik")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
