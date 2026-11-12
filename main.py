import os, logging
from html import escape
from dotenv import load_dotenv
load_dotenv()
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from art import welcome_card
from aiogram.fsm.storage.memory import MemoryStorage
import db
from game import router as game_router, join_from_start, is_group_admin
from shart import router as shart_router, handle_start as handle_shart_start
from admin import router as admin_router, is_admin

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
TOKEN=os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN .env yoki Railway Variables ichida kiritilmagan.")

async def check_subscription(bot,user_id):
    channels=await db.channels()
    missing=[]
    for chat_id,title,link in channels:
        try:
            member=await bot.get_chat_member(int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,user_id)
            if member.status in ("left","kicked"):
                missing.append((title,link))
        except Exception:
            missing.append((title,link))
    return missing

async def main():
    await db.init_db()
    bot=Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp=Dispatcher(storage=MemoryStorage())
    dp.include_router(shart_router)
    dp.include_router(game_router)
    dp.include_router(admin_router)

    @dp.message(CommandStart())
    async def start(message: Message, command: CommandObject):
        if message.chat.type != "private" and not await is_group_admin(bot, message.chat.id, message.from_user.id):
            return
        await db.save_user(message.from_user)
        me = await bot.get_me()
        bot_url = f"https://t.me/{me.username}"

        # In groups, never post the long private welcome screen.
        if message.chat.type != "private":
            await message.answer(
                "🩸 <b>ABE VAYN</b>\n"
                "<i>ISHONCH • AQL • STRATEGIYA</i>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "🎭 O‘yinga kirish va maxfiy rolingizni olish uchun "
                "botning shaxsiy chatiga o‘ting.\n"
                f"👇 <a href=\"{bot_url}\">ABE VAYN BOTINI OCHISH</a>\n"
                "1. Havolani bosing.\n"
                "2. Botda <b>START</b> tugmasini bosing.\n"
                "3. O‘yin boshlanganda rolingiz shaxsiy xabarda keladi.",
                disable_web_page_preview=True,
            )
            return

        if await db.is_blocked(message.from_user.id):
            await message.answer("⛔ Botdan foydalanishingiz cheklangan.")
            return

        missing = await check_subscription(bot, message.from_user.id)
        if missing:
            rows = [[InlineKeyboardButton(text="📢 " + title, url=link)] for title, link in missing if link]
            rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="sub:check")])
            await message.answer(
                "Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo‘ling:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
            return

        # Deep-link for Shart Chambalagi: accept a private condition submission.
        if command.args and command.args.startswith("shart_"):
            await handle_shart_start(message, command.args)
            return

        # Deep-link join: add player, confirm, and do not send a second welcome card.
        if command.args and command.args.startswith("join_"):
            await join_from_start(message, command.args)
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♟ GURUHGA QO‘SHISH", url=f"{bot_url}?startgroup=add")],
            [InlineKeyboardButton(text="📜 O‘YIN QOIDALARI", callback_data="info:rules"),
             InlineKeyboardButton(text="📊 STATISTIKA", callback_data="info:stats")],
            [InlineKeyboardButton(text="👑 ADMIN PANEL", callback_data="info:admin")]
        ])
        welcome_text = (
            "🩸 <b>ABE VAYN</b>\n"
            "<i>ISHONCH • AQL • STRATEGIYA</i>\n\n"
            "Shahar uxlaydi. Ammo tun hukmdorlari uyg‘oq...\n"
            "Do‘stlaringizni guruhga yig‘ing va kimga ishonishni aniqlang.\n\n"
            "♟ <b>O‘YINNI BOSHLASH</b>\n"
            "1. Botni guruhga qo‘shing.\n"
            "2. Guruhda <code>/game</code> buyrug‘ini yuboring.\n"
            "3. O‘yinchilar guruhdagi <b>ROLNI OLISH UCHUN BOTGA O‘TISH</b> tugmasini bosing. "
            "Bot ochilgach <b>START</b> bosing.\n\n"
            "🔐 <b>Har bir rol faqat shaxsiy chatda yuboriladi.</b>\n"
            "👥 4–20 o‘yinchi  •  🌙 Tun / ☀️ Kunduz\n"
            "🏆 <code>/top</code> — reyting  |  👤 <code>/profile</code> — profil"
        )
        try:
            photo = BufferedInputFile(welcome_card().getvalue(), filename="abevayn_welcome.png")
            await message.answer_photo(photo, caption=welcome_text, reply_markup=kb)
        except Exception:
            logging.exception("Welcome artwork could not be sent")
            await message.answer(welcome_text, reply_markup=kb)

    @dp.callback_query(F.data=="sub:check")
    async def sub_check(call):
        missing=await check_subscription(bot,call.from_user.id)
        if missing:
            await call.answer("Hali barcha kanallarga obuna bo‘lmagansiz.",show_alert=True)
        else:
            await call.message.answer("✅ Obuna tasdiqlandi. /start bosing.")
            await call.answer()

    @dp.callback_query(F.data=="info:rules")
    async def rules(call):
        await call.message.answer("📜 <b>Qoidalar</b>\nMafiya kechasi hujum qiladi. Doktor bir kishini himoya qiladi. Komissar shubhali o‘yinchini tekshiradi. Kunduz hamma muhokama qilib ovoz beradi. Mafiya yo‘q bo‘lsa tinch aholi, mafiyalar soni qolganlar soniga tenglashsa mafiya yutadi.")
        await call.answer()

    @dp.callback_query(F.data=="info:stats")
    async def stats(call):
        u,g,c=await db.stats()
        await call.message.answer(f"📊 Foydalanuvchilar: {u}\n👥 Guruhlar: {g}\n📢 Kanallar: {c}")
        await call.answer()

    @dp.callback_query(F.data=="info:admin")
    async def admin_info(call):
        if await is_admin(call.from_user.id):
            await call.message.answer("Admin panel: /admin")
        else:
            await call.answer("Siz admin emassiz.",show_alert=True)
            return
        await call.answer()

    @dp.message(Command("myid"))
    async def my_id_cmd(message: Message):
        if message.chat.type != "private" and not await is_group_admin(bot, message.chat.id, message.from_user.id):
            return
        await message.answer(
            f"🆔 Sizning Telegram ID raqamingiz:\n<code>{message.from_user.id}</code>\n\n"
            "Admin bo‘lish uchun shu raqamni Railway Variables ichidagi ADMIN_IDS ga yozing."
        )

    @dp.message(Command("top"))
    async def top_cmd(message: Message):
        if message.chat.type != "private" and not await is_group_admin(bot, message.chat.id, message.from_user.id):
            return
        rows = await db.top_players(10)
        if not rows:
            await message.answer("🏆 Hozircha reyting bo‘sh. O‘yin o‘ynab ochko to‘plang!")
            return
        lines = ["🏆 <b>ABE VAYN — TOP 10</b>", ""]
        for i, row in enumerate(rows, 1):
            name = row[1] or f"Player {row[0]}"
            lines.append(f"{i}. {escape(name)} — <b>{row[2]} ochko</b> | 🏅 {row[3]} g‘alaba")
        await message.answer("\n".join(lines))

    @dp.message(Command("profile"))
    async def profile_cmd(message: Message):
        if message.chat.type != "private" and not await is_group_admin(bot, message.chat.id, message.from_user.id):
            return
        points, wins, games = await db.get_result(message.from_user.id)
        rate = round((wins / games) * 100) if games else 0
        await message.answer(
            f"👤 <b>SIZNING PROFILINGIZ</b>\n\n"
            f"🎯 Ochko: <b>{points}</b>\n"
            f"🏆 G‘alaba: <b>{wins}</b>\n"
            f"🎮 O‘yinlar: <b>{games}</b>\n"
            f"📈 G‘alaba foizi: <b>{rate}%</b>"
        )

    @dp.message(Command("help"))
    async def help_cmd(message):
        if message.chat.type != "private" and not await is_group_admin(bot, message.chat.id, message.from_user.id):
            return
        await message.answer("/start — botni ochish\n/game — Mafia o‘yini\n/shart — Shart chambaragini boshlash (guruh admini)\n/shartstop — Shart o‘yinini to‘xtatish\n/players — o‘yinchilar\n/status — o‘yin holati\n/profile — profil\n/top — reyting\n/myid — Telegram ID\n/admin — admin panel")

    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
