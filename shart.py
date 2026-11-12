"""Shart chambaragi: admin-started, two-stage random group game."""
import asyncio
import logging
import random
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
)

log = logging.getLogger("shart-game")
router = Router()

SESSIONS = {}  # chat_id -> active round/session
PENDING = {}   # user_id -> (chat_id, selected_user_id)
MAX_PLAYERS = 50
MAX_CONDITION = 250
MAX_CONDITIONS = 20


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(name)}</a>'


async def is_group_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


def lobby_keyboard(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ O‘yinga qo‘shilish", callback_data=f"shart:join:{chat_id}")],
        [InlineKeyboardButton(text="🎡 Odamni tanlash", callback_data=f"shart:pick:{chat_id}")],
    ])


def lobby_text(session):
    names = [
        f"• {mention(uid, player['name'])}"
        for uid, player in session["players"].items()
    ]
    return (
        "🎡 <b>SHART CHAMBARAgi boshlandi!</b>\n\n"
        "O‘yinga qo‘shilish uchun tugmani bosing.\n\n"
        f"👥 Ishtirokchilar: <b>{len(names)}</b>\n"
        + ("\n".join(names) if names else "Hali hech kim qo‘shilmadi.")
        + "\n\nAdmin odam tanlash tugmasini bosadi."
    )


@router.message(Command("shart"))
async def start_shart(message: Message):
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.answer("❗ /shart buyrug‘ini guruhda yuboring.")
        return
    if not await is_group_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("🔒 /shart buyrug‘ini faqat guruh admini ishlata oladi.")
        return
    if message.chat.id in SESSIONS:
        await message.answer("⚠️ Bu guruhda Shart chambaragi allaqachon ochilgan.")
        return

    SESSIONS[message.chat.id] = {
        "phase": "lobby",
        "players": {},
        "remaining": [],
        "selected": None,
        "conditions": [],
        "submitted": set(),
        "bot_username": (await message.bot.get_me()).username,
    }
    await message.answer(
        lobby_text(SESSIONS[message.chat.id]),
        reply_markup=lobby_keyboard(message.chat.id),
    )


@router.message(Command("shartstop"))
async def stop_shart(message: Message):
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await is_group_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("🔒 Bu buyruq faqat guruh adminlari uchun.")
        return
    session = SESSIONS.pop(message.chat.id, None)
    if not session:
        await message.answer("Hozir faol Shart chambaragi yo‘q.")
        return
    for uid, (pending_chat, _) in list(PENDING.items()):
        if pending_chat == message.chat.id:
            PENDING.pop(uid, None)
    await message.answer("🛑 Shart chambaragi admin tomonidan to‘xtatildi.")


@router.callback_query(F.data.startswith("shart:join:"))
async def join_game(call: CallbackQuery):
    chat_id = int(call.data.split(":")[2])
    session = SESSIONS.get(chat_id)
    if not session or session["phase"] != "lobby":
        await call.answer("O‘yinga qo‘shilish yopilgan.", show_alert=True)
        return
    if not call.message or call.message.chat.id != chat_id:
        await call.answer("Bu o‘yin boshqa guruhda.", show_alert=True)
        return

    uid = call.from_user.id
    if uid in session["players"]:
        await call.answer("Siz allaqachon qo‘shilgansiz.")
        return
    if len(session["players"]) >= MAX_PLAYERS:
        await call.answer("Ishtirokchilar soni to‘ldi.", show_alert=True)
        return

    session["players"][uid] = {"name": call.from_user.full_name}
    session["remaining"].append(uid)
    try:
        await call.message.edit_text(
            lobby_text(session),
            reply_markup=lobby_keyboard(chat_id),
        )
    except Exception:
        pass
    await call.answer("✅ O‘yinga qo‘shildingiz!")


async def send_selected_player(call: CallbackQuery, session, chat_id: int, heading: str):
    selected = random.choice(session["remaining"])
    session["remaining"].remove(selected)
    session["selected"] = selected
    session["conditions"] = []
    session["submitted"] = set()
    session["phase"] = "collecting"

    name = session["players"][selected]["name"]
    wheel_names = "\n".join(
        f"• {escape(player['name'])}"
        for player in session["players"].values()
    )
    wheel_message = await call.message.answer(
        "🎡 <b>ODAM TANLASH G‘ILDIRAGI</b>\n\n"
        + wheel_names + "\n\n🔄 Aylanmoqda..."
    )
    await call.answer("G‘ildirak aylanmoqda!")
    # Avoid rapid EditMessageText calls: Telegram applies per-chat flood limits.
    # Keep a short visual pause, then publish the final selected player once.
    await asyncio.sleep(1.5)

    link = (
        f"https://t.me/{session['bot_username']}"
        f"?start=shart_{chat_id}_{selected}"
    )
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Shart yozish", url=link)],
        [InlineKeyboardButton(
            text="🎡 Shartlarni aylantirish",
            callback_data=f"shart:spin:{chat_id}",
        )],
    ])
    result_text = (
        f"🎉 <b>{heading}</b>\\n\\n"
        f"👤 Tanlangan odam: {mention(selected, name)}\\n\\n"
        "Endi guruhdagilar “Shart yozish” tugmasini bosib, "
        "botning shaxsiy chatiga shart yuborishsin.\\n"
        "Shartlar yig‘ilgach, admin “Shartlarni aylantirish” tugmasini bosadi."
    )
    try:
        await wheel_message.edit_text(result_text, reply_markup=buttons)
    except TelegramRetryAfter as exc:
        log.warning(
            "Telegram flood control in %s; retrying final wheel update in %s seconds",
            chat_id, exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after + 1)
        await wheel_message.edit_text(result_text, reply_markup=buttons)


@router.callback_query(F.data.startswith("shart:pick:"))
async def pick_player(call: CallbackQuery):
    chat_id = int(call.data.split(":")[2])
    session = SESSIONS.get(chat_id)
    if not session:
        await call.answer("O‘yin topilmadi.", show_alert=True)
        return
    if not await is_group_admin(call.bot, chat_id, call.from_user.id):
        await call.answer("Odamni faqat guruh admini tanlaydi.", show_alert=True)
        return
    if session["phase"] not in ("lobby", "done") or not session["remaining"]:
        await call.answer("Tanlash uchun odam qolmagan yoki hozir tanlab bo‘lmaydi.", show_alert=True)
        return
    if not session["players"]:
        await call.answer("Avval odamlar o‘yinga qo‘shilsin.", show_alert=True)
        return
    await send_selected_player(call, session, chat_id, "G‘ILDIRAK TANLADI!")


async def handle_start(message: Message, args: str):
    """Process /start shart_<group_chat_id>_<selected_user_id> deep link."""
    try:
        _, chat_raw, target_raw = args.split("_", 2)
        chat_id, target_id = int(chat_raw), int(target_raw)
    except (ValueError, AttributeError):
        await message.answer("❌ Shart havolasi noto‘g‘ri yoki eskirgan.")
        return

    session = SESSIONS.get(chat_id)
    if (
        not session
        or session["phase"] != "collecting"
        or session.get("selected") != target_id
    ):
        await message.answer("❌ Hozir shart yuborish vaqti emas. Guruhdagi yangi havolani bosing.")
        return
    if message.from_user.id == target_id:
        await message.answer("😄 Bu safar shartni boshqalar yozadi. Siz shartni bajarasiz!")
        return
    if message.from_user.id in session["submitted"]:
        await message.answer("✅ Siz bu tur uchun shart yuborib bo‘lgansiz.")
        return

    PENDING[message.from_user.id] = (chat_id, target_id)
    await message.answer(
        f"✍️ <b>{escape(session['players'][target_id]['name'])}</b> uchun shartingizni yozing.\n\n"
        "Bitta kulgili va xavfsiz topshiriq yuboring. "
        f"Matn {MAX_CONDITION} belgidan oshmasin."
    )


@router.message(
    F.chat.type == ChatType.PRIVATE,
    F.text,
    lambda message: bool(message.from_user and message.from_user.id in PENDING),
)
async def receive_condition(message: Message):
    pending = PENDING.get(message.from_user.id)
    if not pending:
        return
    chat_id, target_id = pending
    session = SESSIONS.get(chat_id)
    if (
        not session
        or session["phase"] != "collecting"
        or session.get("selected") != target_id
    ):
        PENDING.pop(message.from_user.id, None)
        await message.answer("❌ Bu tur yakunlangan. Guruhdagi yangi shart havolasidan foydalaning.")
        return

    condition = (message.text or "").strip()
    if not condition or condition.startswith("/"):
        await message.answer("Iltimos, shartni oddiy matn qilib yozing.")
        return
    if len(condition) > MAX_CONDITION:
        await message.answer(f"❌ Shart {MAX_CONDITION} belgidan oshmasin.")
        return
    if len(session["conditions"]) >= MAX_CONDITIONS:
        await message.answer(f"Bu turda ko‘pi bilan {MAX_CONDITIONS} ta shart qabul qilinadi.")
        return
    if message.from_user.id == target_id:
        await message.answer("Siz tanlangan odamsiz, bu turda shart yubora olmaysiz.")
        return
    if message.from_user.id in session["submitted"]:
        await message.answer("Siz bu tur uchun shart yuborib bo‘lgansiz.")
        return

    session["conditions"].append({
        "text": condition,
        "by": message.from_user.id,
        "name": message.from_user.full_name,
    })
    session["submitted"].add(message.from_user.id)
    PENDING.pop(message.from_user.id, None)
    await message.answer("✅ Shartingiz qabul qilindi! Guruhda g‘ildirak aylanishini kuting.")
    try:
        await message.bot.send_message(
            chat_id,
            f"📝 Yangi shart qo‘shildi! Jami shartlar: <b>{len(session['conditions'])}</b>",
        )
    except Exception:
        log.exception("Could not notify group about a new condition")


@router.callback_query(F.data.startswith("shart:spin:"))
async def spin_conditions(call: CallbackQuery):
    chat_id = int(call.data.split(":")[2])
    session = SESSIONS.get(chat_id)
    if not session or session["phase"] != "collecting":
        await call.answer("Hozir shart g‘ildiragini aylantirib bo‘lmaydi.", show_alert=True)
        return
    if not await is_group_admin(call.bot, chat_id, call.from_user.id):
        await call.answer("Shart g‘ildiragini faqat admin aylantiradi.", show_alert=True)
        return
    if not session["conditions"]:
        await call.answer("Hali hech kim shart yubormadi.", show_alert=True)
        return

    session["phase"] = "spinning"
    conditions = list(session["conditions"])
    wheel_lines = "\n".join(
        f"{i}. {escape(item['text'][:150])}"
        for i, item in enumerate(conditions, 1)
    )
    wheel = await call.message.answer(
        "🎡 <b>SHARTLAR G‘ILDIRAGI</b>\n\n"
        + wheel_lines + "\n\n🔄 Aylanmoqda..."
    )
    await call.answer("Shartlar g‘ildiragi aylanmoqda!")
    # One final edit is enough; rapid frame edits trigger Telegram flood control.
    await asyncio.sleep(1.5)

    chosen = random.choice(conditions)
    session["chosen_condition"] = chosen
    session["phase"] = "done"
    selected = session["selected"]
    player_name = session["players"][selected]["name"]
    result = (
        "🎊 <b>G‘ILDIRAK TO‘XTADI!</b>\n\n"
        f"👤 Tanlangan odam: {mention(selected, player_name)}\n\n"
        "🎯 <b>Unga tushgan shart:</b>\n"
        f"🔥 <b>{escape(chosen['text'])}</b>\n\n"
        "Endi tanlangan odam shartni bajaradi!"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Shart bajarildi",
            callback_data=f"shart:done:{chat_id}:{selected}",
        )],
        [InlineKeyboardButton(
            text="🎡 Keyingi odamni tanlash",
            callback_data=f"shart:next:{chat_id}",
        )],
    ])
    try:
        await wheel.edit_text(result, reply_markup=keyboard)
    except TelegramRetryAfter as exc:
        log.warning(
            "Telegram flood control in %s; retrying condition result in %s seconds",
            chat_id, exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after + 1)
        await wheel.edit_text(result, reply_markup=keyboard)


@router.callback_query(F.data.startswith("shart:done:"))
async def confirm_condition(call: CallbackQuery):
    _, _, chat_raw, target_raw = call.data.split(":")
    chat_id, target_id = int(chat_raw), int(target_raw)
    session = SESSIONS.get(chat_id)
    if not session or session["phase"] != "done" or session.get("selected") != target_id:
        await call.answer("Bu tur topilmadi.", show_alert=True)
        return
    if (
        call.from_user.id != target_id
        and not await is_group_admin(call.bot, chat_id, call.from_user.id)
    ):
        await call.answer("Bu tugmani faqat tanlangan odam yoki admin bosishi mumkin.", show_alert=True)
        return

    session["phase"] = "await_next"
    next_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎡 Keyingi odamni tanlash",
            callback_data=f"shart:next:{chat_id}",
        )
    ]])
    await call.message.edit_reply_markup(reply_markup=next_keyboard)
    await call.message.answer(
        f"✅ {mention(target_id, session['players'][target_id]['name'])} "
        "shartni bajarganini tasdiqladi!"
    )
    await call.answer("Bajarildi!")


@router.callback_query(F.data.startswith("shart:next:"))
async def next_player(call: CallbackQuery):
    chat_id = int(call.data.split(":")[2])
    session = SESSIONS.get(chat_id)
    if not session:
        await call.answer("O‘yin topilmadi.", show_alert=True)
        return
    if not await is_group_admin(call.bot, chat_id, call.from_user.id):
        await call.answer("Keyingi odamni faqat admin tanlaydi.", show_alert=True)
        return
    if session["phase"] not in ("done", "await_next"):
        await call.answer("Avval joriy tur yakunlansin.", show_alert=True)
        return
    if not session["remaining"]:
        await call.message.answer(
            "🏁 Barcha ishtirokchilar navbatdan o‘tdi!\n"
            "Yangi o‘yin uchun /shart yuboring."
        )
        SESSIONS.pop(chat_id, None)
        await call.answer("O‘yin yakunlandi!")
        return
    await send_selected_player(call, session, chat_id, "KEYINGI ODAM TANLANDI!")
