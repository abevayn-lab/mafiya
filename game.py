import asyncio
import logging
import random
from collections import Counter
from dataclasses import dataclass
from html import escape
from contextlib import suppress

import db
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

log = logging.getLogger("mafia.game")
router = Router()

GAMES = {}
USER_GAME = {}

MAX_PLAYERS = 20
MIN_PLAYERS_DEFAULT = 5

ROLE_NAMES = {
    "mafia": "🔪 Mafiya",
    "doctor": "💉 Shifokor",
    "detective": "🕵️ Komissar",
    "civilian": "👤 Tinch aholi",
}


@dataclass
class Player:
    user_id: int
    name: str
    role: str = "civilian"
    alive: bool = True


class Game:
    def __init__(
        self,
        bot: Bot,
        bot_username: str,
        chat_id: int,
        chat_title: str,
        host_id: int,
        fast: bool,
        min_players: int = MIN_PLAYERS_DEFAULT,
    ):
        self.bot = bot
        self.bot_username = bot_username
        self.chat_id = chat_id
        self.chat_title = chat_title or "Guruh"
        self.host_id = host_id
        self.fast = fast
        self.min_players = min_players

        self.players = {}
        self.phase = "lobby"
        self.round = 0
        self.lobby_message_id = None
        self.task = None

        self.start_event = asyncio.Event()
        self.phase_event = asyncio.Event()

        self.votes = {}
        self.night_actions = {}
        self.expected_night = set()

        self.deadline_seconds = {
            "lobby": 60 if fast else 120,
            "night": 25 if fast else 40,
            "day": 30 if fast else 60,
        }

    def alive(self):
        return [p for p in self.players.values() if p.alive]

    def player_link(self, player):
        return (
            f'<a href="tg://user?id={player.user_id}">'
            f'{escape(player.name)}</a>'
        )

    def lobby_text(self):
        names = "\n".join(
            f"{i}. {self.player_link(p)}"
            for i, p in enumerate(self.players.values(), 1)
        ) or "— hali hech kim yo‘q —"

        mode = "⚡ Tezkor" if self.fast else "🎭 Oddiy"

        return (
            f"<b>🎭 MAFIA — YANGI O‘YIN!</b>\n"
            f"{mode}\n\n"
            f"👥 O‘yinchilar: <b>{len(self.players)}/{MAX_PLAYERS}</b>\n"
            f"{names}\n\n"
            f"Kamida {self.min_players} kishi kerak.\n"
            f"Qo‘shilish uchun tugmani bosing."
        )

    def lobby_keyboard(self):
        join_url = (
            f"https://t.me/{self.bot_username}"
            f"?start=join_{self.chat_id}"
        )

        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 O‘yinga qo‘shilish",
                    url=join_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="▶️ Boshlash",
                    callback_data=f"lobby:start:{self.chat_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"lobby:cancel:{self.chat_id}",
                )
            ],
        ])

    async def refresh_lobby(self):
        if self.lobby_message_id:
            try:
                await self.bot.edit_message_text(
                    self.lobby_text(),
                    chat_id=self.chat_id,
                    message_id=self.lobby_message_id,
                    reply_markup=self.lobby_keyboard(),
                )
            except Exception:
                pass

    async def add_player(self, user_id, name):
        if self.phase != "lobby":
            return "closed"

        if user_id in self.players:
            return "already"

        if len(self.players) >= MAX_PLAYERS:
            return "full"

        if USER_GAME.get(user_id) not in (None, self.chat_id):
            return "busy"

        self.players[user_id] = Player(user_id, name)
        USER_GAME[user_id] = self.chat_id

        await self.refresh_lobby()
        return "ok"

    async def cancel(self):
        if self.phase != "lobby":
            return False

        self.phase = "cancelled"
        self.start_event.set()
        return True

    async def start(self):
        if self.phase != "lobby":
            return "closed"

        if len(self.players) < self.min_players:
            return "few"

        self.phase = "starting"
        self.start_event.set()
        return "ok"

    async def send(self, text, **kwargs):
        try:
            return await self.bot.send_message(
                self.chat_id, text, **kwargs
            )
        except Exception:
            log.exception("Could not send group message")
            return None

    async def remove_lobby_buttons(self):
        if self.lobby_message_id:
            try:
                await self.bot.edit_message_reply_markup(
                    chat_id=self.chat_id,
                    message_id=self.lobby_message_id,
                    reply_markup=None,
                )
            except Exception:
                pass

    async def run(self):
        try:
            try:
                await asyncio.wait_for(
                    self.start_event.wait(),
                    self.deadline_seconds["lobby"],
                )
            except asyncio.TimeoutError:
                pass

            if self.phase == "cancelled":
                await self.send("❌ O‘yin bekor qilindi.")
                return

            if self.phase == "stopped":
                return

            if len(self.players) < self.min_players:
                await self.send(
                    f"❌ O‘yin bekor qilindi. "
                    f"Kamida {self.min_players} o‘yinchi kerak."
                )
                return

            if self.phase != "starting":
                self.phase = "starting"

            await self.remove_lobby_buttons()

            db.group_game(self.chat_id)

            await self.assign_roles()
            await asyncio.sleep(3)

            while self.phase == "playing":
                self.round += 1

                await self.night()

                if self.phase != "playing":
                    break

                if self.check_winner():
                    break

                await self.day()

                if self.phase != "playing":
                    break

                if self.check_winner():
                    break

        except asyncio.CancelledError:
            raise

        except Exception:
            log.exception("Game failed in chat %s", self.chat_id)
            await self.send(
                "⚠️ O‘yinda texnik xatolik yuz berdi "
                "va o‘yin to‘xtatildi."
            )

        finally:
            self.phase = "ended"

            for uid in list(self.players):
                if USER_GAME.get(uid) == self.chat_id:
                    USER_GAME.pop(uid, None)

            if GAMES.get(self.chat_id) is self:
                GAMES.pop(self.chat_id, None)

    async def assign_roles(self):
        count = len(self.players)

        mafia_count = (
            1 if count < 8
            else 2 if count < 13
            else 3
        )

        roles = ["mafia"] * mafia_count
        roles += ["doctor", "detective"]
        roles += ["civilian"] * (count - len(roles))

        random.shuffle(roles)

        for player, role in zip(self.players.values(), roles):
            player.role = role

        self.phase = "playing"

        role_summary = Counter(
            p.role for p in self.players.values()
        )

        summary = ", ".join(
            f"{ROLE_NAMES[k]} ×{v}"
            for k, v in role_summary.items()
        )

        await self.send(
            f"🎬 <b>O‘YIN BOSHLANDI!</b>\n"
            f"Rollar: {summary}\n"
            f"Rollar shaxsiy xabarda yuborildi."
        )

        for p in self.players.values():
            text = (
                f"🎭 Sizning rolingiz: "
                f"<b>{ROLE_NAMES[p.role]}</b>"
            )

            if p.role == "mafia":
                mates = [
                    x.name
                    for x in self.players.values()
                    if x.role == "mafia"
                    and x.user_id != p.user_id
                ]

                if mates:
                    text += (
                        "\nMafiya jamoadoshlaringiz: "
                        + ", ".join(map(escape, mates))
                    )

            try:
                await self.bot.send_message(p.user_id, text)
            except Exception:
                await self.send(
                    f"⚠️ {escape(p.name)} botga shaxsiy xabarda "
                    f"/start yubormagan. Rolini olishi uchun botga yozsin."
                )

    def night_keyboard(self, player):
        targets = [
            p for p in self.alive()
            if p.user_id != player.user_id
            or player.role == "doctor"
        ]

        rows = [
            [
                InlineKeyboardButton(
                    text=p.name[:30],
                    callback_data=f"act:{self.chat_id}:{p.user_id}",
                )
            ]
            for p in targets
        ]

        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def night(self):
        self.phase = "night"
        self.phase_event = asyncio.Event()
        self.night_actions = {}

        self.expected_night = {
            p.user_id
            for p in self.alive()
            if p.role in ("mafia", "doctor", "detective")
        }

        await self.send(
            f"🌙 <b>{self.round}-tun.</b>\n"
            f"Maxsus rollar tanlovini shaxsiy xabarda bajarsin. "
            f"({self.deadline_seconds['night']} soniya)"
        )

        for uid in self.expected_night:
            p = self.players[uid]

            prompt = {
                "mafia": "🔪 Kimni yo‘q qilasiz?",
                "doctor": "💉 Kimni himoya qilasiz?",
                "detective": "🕵️ Kimni tekshirasiz?",
            }[p.role]

            try:
                await self.bot.send_message(
                    uid,
                    prompt,
                    reply_markup=self.night_keyboard(p),
                )
            except Exception:
                pass

        try:
            await asyncio.wait_for(
                self.phase_event.wait(),
                self.deadline_seconds["night"],
            )
        except asyncio.TimeoutError:
            pass

        if self.phase != "night":
            return

        counts = Counter(
            target
            for uid, target in self.night_actions.items()
            if self.players[uid].role == "mafia"
        )

        victim = None

        if counts:
            highest = max(counts.values())
            victim = random.choice([
                uid for uid, n in counts.items()
                if n == highest
            ])

        saved = {
            target
            for uid, target in self.night_actions.items()
            if self.players[uid].role == "doctor"
        }

        if victim and victim not in saved:
            self.players[victim].alive = False
            dead = self.players[victim]

            await self.send(
                f"🌅 Tong otdi. 💀 {self.player_link(dead)} "
                f"halok bo‘ldi. ({ROLE_NAMES[dead.role]})"
            )
        else:
            await self.send(
                "🌅 Tong otdi. Bu kecha hech kim halok bo‘lmadi."
            )

        for uid, target in list(self.night_actions.items()):
            if self.players[uid].role == "detective":
                result = (
                    "MAFIYA"
                    if self.players[target].role == "mafia"
                    else "mafiya emas"
                )

                try:
                    await self.bot.send_message(
                        uid,
                        f"🕵️ Tekshiruv: "
                        f"{escape(self.players[target].name)} "
                        f"— <b>{result}</b>",
                    )
                except Exception:
                    pass

    async def record_night_action(self, user_id, target_id):
        p = self.players.get(user_id)
        target = self.players.get(target_id)

        if (
            self.phase != "night"
            or not p
            or not p.alive
            or not target
            or not target.alive
        ):
            return "Bu tanlov hozir qabul qilinmaydi."

        if user_id not in self.expected_night:
            return "Sizda tungi harakat yo‘q."

        if user_id in self.night_actions:
            return "Siz allaqachon tanlagansiz."

        if p.role == "mafia" and target.role == "mafia":
            return "Mafiya o‘z jamoadoshini tanlay olmaydi."

        if p.role == "detective" and target_id == user_id:
            return "O‘zingizni tekshira olmaysiz."

        self.night_actions[user_id] = target_id

        if self.expected_night.issubset(
            self.night_actions.keys()
        ):
            self.phase_event.set()

        return "✅ Tanlov qabul qilindi."

    async def day(self):
        self.phase = "day"
        self.votes = {}
        self.phase_event = asyncio.Event()

        alive = self.alive()

        rows = [
            [
                InlineKeyboardButton(
                    text=f"🗳 {p.name[:25]}",
                    callback_data=f"vote:{self.chat_id}:{p.user_id}",
                )
            ]
            for p in alive
        ]

        keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

        await self.send(
            f"☀️ <b>{self.round}-kun.</b>\n"
            f"Muhokama qiling va ovoz bering. "
            f"({self.deadline_seconds['day']} soniya)",
            reply_markup=keyboard,
        )

        try:
            await asyncio.wait_for(
                self.phase_event.wait(),
                self.deadline_seconds["day"],
            )
        except asyncio.TimeoutError:
            pass

        if self.phase != "day":
            return

        counts = Counter(self.votes.values())

        if counts:
            high = max(counts.values())
            winners = [
                uid for uid, n in counts.items()
                if n == high
            ]

            if len(winners) == 1:
                out = self.players[winners[0]]
                out.alive = False

                await self.send(
                    f"⚖️ Ovoz bilan chiqarildi: "
                    f"{self.player_link(out)} — "
                    f"{ROLE_NAMES[out.role]}."
                )
            else:
                await self.send(
                    "⚖️ Ovozlar teng. Hech kim chiqarilmadi."
                )
        else:
            await self.send("⚖️ Ovoz berilmadi.")

    async def record_vote(self, voter_id, target_id):
        voter = self.players.get(voter_id)
        target = self.players.get(target_id)

        if (
            self.phase != "day"
            or not voter
            or not target
            or not voter.alive
            or not target.alive
        ):
            return "Ovoz qabul qilinmaydi."

        if voter_id == target_id:
            return "O‘zingizga ovoz bera olmaysiz."

        self.votes[voter_id] = target_id

        if len(self.votes) >= len(self.alive()):
            self.phase_event.set()

        return "✅ Ovozingiz qabul qilindi."

    def check_winner(self):
        alive_mafia = sum(
            p.alive and p.role == "mafia"
            for p in self.players.values()
        )

        alive_civilians = sum(
            p.alive and p.role != "mafia"
            for p in self.players.values()
        )

        if alive_mafia == 0:
            winner = "🏆 Tinch aholi g‘alaba qozondi!"
            won_role = "civilian"

        elif alive_mafia >= alive_civilians:
            winner = "🔪 Mafiya g‘alaba qozondi!"
            won_role = "mafia"

        else:
            return False

        asyncio.create_task(self.send(winner))

        for p in self.players.values():
            won = (
                p.role == won_role
                or (won_role == "civilian" and p.role != "mafia")
            )

            db.add_result(
                p.user_id,
                20 if won else 5,
                won,
            )

        return True


async def is_group_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


@router.message(Command("game"))
async def create_game(message: Message, command: CommandObject):
    if message.chat.type == "private":
        await message.answer(
            "🎭 O‘yinni guruh ichida /game buyrug‘i bilan boshlang."
        )
        return

    chat_id = message.chat.id

    if chat_id in GAMES:
        await message.answer(
            "⚠️ Bu guruhda allaqachon o‘yin mavjud.\n"
            "To‘xtatish uchun /stop buyrug‘ini bering."
        )
        return

    bot_info = await message.bot.get_me()

    args = (command.args or "").lower()
    fast = "fast" in args or "tez" in args

    game = Game(
        bot=message.bot,
        bot_username=bot_info.username,
        chat_id=chat_id,
        chat_title=message.chat.title or "Guruh",
        host_id=message.from_user.id,
        fast=fast,
    )

    GAMES[chat_id] = game

    sent = await message.answer(
        game.lobby_text(),
        reply_markup=game.lobby_keyboard(),
    )

    game.lobby_message_id = sent.message_id
    game.task = asyncio.create_task(game.run())


async def join_from_start(message: Message, args: str):
    if not args.startswith("join_"):
        return

    try:
        chat_id = int(args.replace("join_", "", 1))
    except ValueError:
        await message.answer("❌ O‘yin havolasi noto‘g‘ri.")
        return

    game = GAMES.get(chat_id)

    if not game:
        await message.answer(
            "❌ Bu o‘yin endi mavjud emas. Guruhda yangi o‘yin oching."
        )
        return

    result = await game.add_player(
        message.from_user.id,
        message.from_user.full_name,
    )

    messages = {
        "ok": "✅ Siz o‘yinga qo‘shildingiz!",
        "already": "ℹ️ Siz allaqachon o‘yindasiz.",
        "full": "❌ O‘yinchilar soni to‘ldi.",
        "busy": "⚠️ Siz boshqa o‘yinda qatnashyapsiz.",
        "closed": "❌ O‘yinga qo‘shilish yopilgan.",
    }

    await message.answer(messages.get(result, "Xatolik yuz berdi."))


@router.callback_query(F.data.startswith("lobby:start:"))
async def lobby_start(call: CallbackQuery):
    chat_id = int(call.data.split(":")[2])
    game = GAMES.get(chat_id)

    if not game:
        await call.answer("O‘yin topilmadi.", show_alert=True)
        return

    allowed = (
        call.from_user.id == game.host_id
        or await is_group_admin(
            call.bot, chat_id, call.from_user.id
        )
    )

    if not allowed:
        await call.answer(
            "Faqat xona egasi yoki guruh admini boshlashi mumkin.",
            show_alert=True,
        )
        return

    result = await game.start()

    if result == "few":
        await call.answer(
            f"Kamida {game.min_players} o‘yinchi kerak!",
            show_alert=True,
        )
    elif result == "ok":
        await call.answer("O‘yin boshlanmoqda!")
        await game.remove_lobby_buttons()
    else:
        await call.answer("O‘yin allaqachon boshlangan.")


@router.callback_query(F.data.startswith("lobby:cancel:"))
async def lobby_cancel(call: CallbackQuery):
    chat_id = int(call.data.split(":")[2])
    game = GAMES.get(chat_id)

    if not game:
        await call.answer("O‘yin topilmadi.", show_alert=True)
        return

    allowed = (
        call.from_user.id == game.host_id
        or await is_group_admin(
            call.bot, chat_id, call.from_user.id
        )
    )

    if not allowed:
        await call.answer(
            "Faqat xona egasi yoki guruh admini bekor qila oladi.",
            show_alert=True,
        )
        return

    if await game.cancel():
        await call.answer("O‘yin bekor qilindi.")
        await game.remove_lobby_buttons()
    else:
        await call.answer(
            "Bu o‘yinni endi bekor qilib bo‘lmaydi.",
            show_alert=True,
        )


@router.callback_query(F.data.startswith("act:"))
async def night_action(call: CallbackQuery):
    try:
        _, chat_id, target_id = call.data.split(":")
        chat_id = int(chat_id)
        target_id = int(target_id)
    except ValueError:
        await call.answer("Noto‘g‘ri tanlov.")
        return

    game = GAMES.get(chat_id)

    if not game:
        await call.answer("O‘yin tugagan.", show_alert=True)
        return

    result = await game.record_night_action(
        call.from_user.id,
        target_id,
    )

    await call.answer(result, show_alert=result != "✅ Tanlov qabul qilindi.")


@router.callback_query(F.data.startswith("vote:"))
async def vote_player(call: CallbackQuery):
    try:
        _, chat_id, target_id = call.data.split(":")
        chat_id = int(chat_id)
        target_id = int(target_id)
    except ValueError:
        await call.answer("Noto‘g‘ri ovoz.")
        return

    game = GAMES.get(chat_id)

    if not game:
        await call.answer("O‘yin tugagan.", show_alert=True)
        return

    result = await game.record_vote(
        call.from_user.id,
        target_id,
    )

    await call.answer(
        result,
        show_alert=result != "✅ Ovozingiz qabul qilindi.",
    )


@router.message(Command("stop"))
async def stop_game(message: Message):
    if message.chat.type == "private":
        await message.answer(
            "⛔ /stop buyrug‘i guruhda ishlaydi."
        )
        return

    chat_id = message.chat.id
    game = GAMES.get(chat_id)

    if not game:
        await message.answer(
            "ℹ️ Bu guruhda faol o‘yin mavjud emas."
        )
        return

    user_id = message.from_user.id

    allowed = (
        user_id == game.host_id
        or await is_group_admin(
            message.bot, chat_id, user_id
        )
    )

    if not allowed:
        await message.answer(
            "⛔ O‘yinni faqat xona egasi yoki guruh admini to‘xtata oladi."
        )
        return

    game.phase = "stopped"
    game.start_event.set()
    game.phase_event.set()

    await game.remove_lobby_buttons()

    task = game.task

    if task and not task.done():
        task.cancel()

        with suppress(asyncio.CancelledError):
            await task

    for uid in list(game.players):
        if USER_GAME.get(uid) == chat_id:
            USER_GAME.pop(uid, None)

    if GAMES.get(chat_id) is game:
        GAMES.pop(chat_id, None)

    await message.answer(
        "🛑 <b>O‘YIN TO‘XTATILDI!</b>\n\n"
        "O‘yin xona egasi yoki guruh administratori tomonidan bekor qilindi.\n\n"
        "🎮 Yangi o‘yin boshlash uchun /game buyrug‘ini bering."
    )
