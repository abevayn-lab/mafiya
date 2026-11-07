import os
from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import db

router = Router()
OWNER_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "8007670371").split(",") if x.strip()}

class AdminInput(StatesGroup):
    broadcast = State()
    add_admin = State()
    add_channel = State()
    remove_channel = State()
    block_user = State()
    unblock_user = State()

async def is_admin(user_id):
    return user_id in OWNER_IDS or user_id in await db.admins()

def panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
         InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm:users")],
        [InlineKeyboardButton(text="📣 Xabar yuborish", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="➕ Admin qo‘shish", callback_data="adm:addadmin")],
        [InlineKeyboardButton(text="🚫 Bloklash", callback_data="adm:block"),
         InlineKeyboardButton(text="♻️ Blokdan olish", callback_data="adm:unblock")],
        [InlineKeyboardButton(text="➕ Majburiy kanal", callback_data="adm:addchannel"),
         InlineKeyboardButton(text="➖ Kanal o‘chirish", callback_data="adm:delchannel")],
        [InlineKeyboardButton(text="📋 Kanallar", callback_data="adm:channels")]
    ])

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("👑 <b>MAFIA BOT — ADMIN PANEL</b>\nKerakli bo‘limni tanlang:", reply_markup=panel_kb())

@router.callback_query(F.data.startswith("adm:"))
async def admin_actions(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        await call.answer("Ruxsat yo‘q", show_alert=True)
        return
    action = call.data.split(":")[1]
    if action == "stats":
        u, g, c = await db.stats()
        await call.message.answer(f"📊 <b>Statistika</b>\n👤 Foydalanuvchilar: {u}\n👥 Guruhlar: {g}\n📢 Majburiy kanallar: {c}")
    elif action == "users":
        rows = await db.recent_users(20)
        if not rows:
            await call.message.answer("Hozircha foydalanuvchilar yo‘q.")
        else:
            txt = "\n".join(f"{i+1}. {escape(str(r[1]))} — <code>{r[0]}</code>" + (f" (@{escape(str(r[2]))})" if r[2] else "") for i,r in enumerate(rows))
            await call.message.answer("👥 <b>Oxirgi foydalanuvchilar</b>\n" + txt)
    elif action == "broadcast":
        await state.set_state(AdminInput.broadcast)
        await call.message.answer("Yuboriladigan xabarni yuboring. Bekor qilish: /cancel")
    elif action == "addadmin":
        await state.set_state(AdminInput.add_admin)
        await call.message.answer("Yangi adminning Telegram ID raqamini yuboring.")
    elif action == "block":
        await state.set_state(AdminInput.block_user)
        await call.message.answer("Bloklanadigan foydalanuvchi ID sini yuboring.")
    elif action == "unblock":
        await state.set_state(AdminInput.unblock_user)
        await call.message.answer("Blokdan olinadigan foydalanuvchi ID sini yuboring.")
    elif action == "addchannel":
        await state.set_state(AdminInput.add_channel)
        await call.message.answer("Kanalni @username yoki -100... ID ko‘rinishida yuboring. Bot kanalga admin bo‘lishi kerak.")
    elif action == "delchannel":
        await state.set_state(AdminInput.remove_channel)
        await call.message.answer("O‘chiriladigan kanalning @username yoki ID sini yuboring.")
    elif action == "channels":
        rows = await db.channels()
        await call.message.answer("📋 <b>Majburiy kanallar</b>\n" + ("\n".join(f"• {escape(str(r[1]))} — <code>{r[0]}</code>" for r in rows) if rows else "Hozircha kanal qo‘shilmagan."))
    await call.answer()

@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")

@router.message(AdminInput.broadcast)
async def do_broadcast(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    ids = await db.user_ids()
    sent = failed = 0
    for uid in ids:
        try:
            await message.bot.copy_message(uid, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
    await state.clear()
    await message.answer(f"📣 Yuborildi: {sent}\nYetkazilmadi: {failed}")

@router.message(AdminInput.add_admin)
async def do_add_admin(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        await db.add_admin(uid)
        await message.answer(f"✅ {uid} admin qilindi.")
    except Exception:
        await message.answer("ID noto‘g‘ri. Raqam yuboring.")
        return
    await state.clear()

@router.message(AdminInput.block_user)
async def do_block(message: Message, state: FSMContext):
    try:
        await db.set_block(int(message.text.strip()), True)
        await message.answer("🚫 Foydalanuvchi bloklandi.")
        await state.clear()
    except Exception:
        await message.answer("ID raqamini yuboring.")

@router.message(AdminInput.unblock_user)
async def do_unblock(message: Message, state: FSMContext):
    try:
        await db.set_block(int(message.text.strip()), False)
        await message.answer("♻️ Blokdan chiqarildi.")
        await state.clear()
    except Exception:
        await message.answer("ID raqamini yuboring.")

@router.message(AdminInput.add_channel)
async def do_add_channel(message: Message, state: FSMContext):
    value = message.text.strip()
    try:
        chat = await message.bot.get_chat(value)
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat.id, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("Bot avval kanalga admin qilinishi kerak.")
            return
        invite = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else "")
        if not invite:
            try:
                invite = (await message.bot.create_chat_invite_link(chat.id)).invite_link
            except Exception:
                invite = ""
        await db.add_channel(chat.id, chat.title or value, invite)
        await message.answer(f"✅ Majburiy kanal qo‘shildi: {chat.title}")
        await state.clear()
    except Exception as e:
        await message.answer("Kanal topilmadi. Botni kanalga admin qiling va @username yoki ID ni qayta yuboring.")

@router.message(AdminInput.remove_channel)
async def do_remove_channel(message: Message, state: FSMContext):
    value = message.text.strip()
    try:
        chat = await message.bot.get_chat(value)
        await db.remove_channel(chat.id)
        await message.answer("✅ Kanal ro‘yxatdan o‘chirildi.")
        await state.clear()
    except Exception:
        await message.answer("Kanalni aniqlab bo‘lmadi. @username yoki ID yuboring.")
