"""Minimal group lobby commands. Game mechanics can be expanded independently."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

import db
from admin import is_blocked

router = Router(name="game")

@router.message(Command("game"))
async def game_cmd(message: Message):
    if message.chat.type == "private":
        await message.answer("O‘yinni guruh ichida /game deb boshlang.")
        return
    if await is_blocked(message.from_user.id):
        await message.reply("⛔ Siz bloklangansiz.")
        return
    await db.upsert_user(message.from_user)
    await db.upsert_group(message.chat)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ O‘yinga qo‘shilish", callback_data="lobby:join")]
    ])
    await message.answer(
        "🕵️ <b>Mafia o‘yini uchun xona ochildi!</b>\n"
        "O‘yinchilar botga shaxsiy chatda /start yuborgan bo‘lishi kerak.\n"
        "O‘yinga qo‘shilish tugmasini bosing.", reply_markup=kb)

@router.message(Command("fast"))
async def fast_cmd(message: Message):
    await game_cmd(message)

@router.message(Command("cancelgame"))
async def cancel_cmd(message: Message):
    if message.chat.type == "private":
        await message.answer("Bu buyruq guruhda ishlaydi.")
    else:
        await message.answer("🛑 Hozirgi lobby bekor qilindi.")

@router.callback_query(lambda c: c.data == "lobby:join")
async def join_lobby(call):
    if await is_blocked(call.from_user.id):
        await call.answer("Siz bloklangansiz.", show_alert=True)
        return
    await db.upsert_user(call.from_user)
    await call.answer("Siz ro‘yxatga olindingiz!", show_alert=True)
