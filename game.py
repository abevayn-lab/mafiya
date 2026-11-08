import asyncio
import logging
import random
from collections import Counter
from pathlib import Path
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
    ChatPermissions,
)
from aiogram.types import BufferedInputFile
from art import role_card, phase_card

log = logging.getLogger("mafia.game")
router = Router()

GAMES = {}
USER_GAME = {}
PENDING_LAST_WORDS = {}
LAST_WORD_GAMES = {}

MAX_PLAYERS = 20
MIN_PLAYERS_DEFAULT = 4


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
        self.lobby_is_photo = False
        self.task = None
        self.original_permissions = None
        self.permissions_saved = False

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
            f"{i}. {escape(p.name[:24])}"
            for i, p in enumerate(self.players.values(), 1)
        ) or "— hali hech kim yo‘q —"

        mode = "⚡ Tezkor" if self.fast else "🎭 Oddiy"

        return (
            f"🩸 <b>ABE VAYN</b>\n"
            f"<i>ISHONCH • AQL • STRATEGIYA</i>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎭 <b>YANGI O‘YIN XONASI</b>  {mode}\n\n"
            f"👥 O‘yinchilar: <b>{len(self.players)}/{MAX_PLAYERS}</b>\n"
            f"{names}\n\n"
            f"🔓 Boshlash uchun kamida <b>{self.min_players}</b> kishi kerak.\n"
            f"👇 O‘yinga qo‘shilish uchun pastdagi <b>QO‘SHILISH</b> knopkasini bosing."
        )

    def lobby_keyboard(self):
        join_url = (
            f"https://t.me/{self.bot_username}"
            f"?start=join_{self.chat_id}"
        )

        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ QO‘SHILISH",
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
                if self.lobby_is_photo:
                    await self.bot.edit_message_caption(
                        caption=self.lobby_text(),
                        chat_id=self.chat_id,
                        message_id=self.lobby_message_id,
                        reply_markup=self.lobby_keyboard(),
                    )
                else:
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

    async def set_group_chat(self, discussion=False):
        """Allow text discussion only during the day; lock member messages at night."""
        try:
            if not self.permissions_saved:
                chat = await self.bot.get_chat(self.chat_id)
                self.original_permissions = chat.permissions
                self.permissions_saved = True

            permissions = ChatPermissions(
                can_send_messages=discussion,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )
            await self.bot.set_chat_permissions(
                self.chat_id,
                permissions=permissions,
                use_independent_chat_permissions=True,
            )
            return True
        except Exception:
            log.exception("Could not change group chat permissions")
            return False

    async def restore_group_chat(self):
        if not self.permissions_saved:
            return
        try:
            permissions = self.original_permissions or ChatPermissions(
                can_send_messages=True
            )
            await self.bot.set_chat_permissions(
                self.chat_id,
                permissions=permissions,
                use_independent_chat_permissions=True,
            )
        except Exception:
            log.exception("Could not restore group chat permissions")

    async def send_phase_image(self, phase, caption, reply_markup=None):
        """Post the illustrated day/night phase card to the game group."""
        try:
            card = BufferedInputFile(
                phase_card(phase).getvalue(),
                filename=f"abevayn_{phase}.png",
            )
            return await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=card,
                caption=caption,
                reply_markup=reply_markup,
            )
        except Exception:
            log.exception("Could not send phase artwork; using text fallback")
            return await self.send(caption, reply_markup=reply_markup)

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
            await self.set_group_chat(discussion=False)

            await db.group_game(self.chat_id)

            await self.assign_roles()
            await asyncio.sleep(3)

            while self.phase == "playing":
                self.round += 1

                await self.night()

                if self.phase != "playing":
                    break

                if await self.check_winner():
                    break

                await self.day()

                if self.phase != "playing":
                    break

                if await self.check_winner():
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
            await self.restore_group_chat()
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

        await self.send(
            "🎬 <b>O‘YIN BOSHLANDI!</b>\n"
            "🔐 Har bir o‘yinchi o‘z rolini botning shaxsiy chatida ko‘radi.\n"
            f"👉 <a href=\"https://t.me/{self.bot_username}\">ABE VAYN BOTINI OCHISH</a>\n"
            "Botda <code>/start</code> bosing.\n"
            "🤫 Rollaringizni sir saqlang. Omad!"
        )

        for p in self.players.values():
            role_descriptions = {
                "mafia": "Kechasi mafiya bilan birga hujum uchun nishon tanlang.",
                "doctor": "Har kecha bir o‘yinchini himoya qiling.",
                "detective": "Har kecha bir o‘yinchining mafiya ekanini tekshiring.",
                "civilian": "Kunduz muhokama qiling va ovoz berib mafiyani toping.",
            }
            text = (
                f"🎭 <b>SIZNING ROLINGIZ</b>\n\n"
                f"Sizning rolingiz: <b>{ROLE_NAMES[p.role]}</b>\n\n"
                f"{role_descriptions[p.role]}\n\n"
                f"🤫 Rolingizni sir saqlang."
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
                card = BufferedInputFile(
                    role_card(p.role).getvalue(),
                    filename=f"abevayn_{p.role}.png",
                )
                await self.bot.send_photo(
                    p.user_id,
                    card,
                    caption=text,
                )
            except Exception:
                log.exception("Could not send role card to %s", p.user_id)
                try:
                    await self.bot.send_message(p.user_id, text)
                except Exception:
                    await self.send(
                        f"⚠️ {escape(p.name)}, rolingizni olish uchun "
                        f"<a href=\"https://t.me/{self.bot_username}\">ABE VAYN BOTINI OCHING</a> va <code>/start</code> bosing. "
                        "Keyingi o‘yinda rol kartangiz shaxsiy yuboriladi."
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
        await self.set_group_chat(discussion=False)
        self.phase_event = asyncio.Event()
        self.night_actions = {}

        self.expected_night = {
            p.user_id
            for p in self.alive()
            if p.role in ("mafia", "doctor", "detective")
        }

        await self.send_phase_image(
            "night",
            f"🌙 <b>{self.round}-TUN</b>\n"
            f"Maxsus rollar tanlovni shaxsiy xabarda bajarsin. "
            f"⏳ {self.deadline_seconds['night']} soniya"
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
                f"🌅 <b>TONG OTDI</b>\n\n"
                f"💀 {self.player_link(dead)} halok bo‘ldi.\n"
                f"🎭 Uning roli: <b>{ROLE_NAMES[dead.role]}</b>"
            )
            LAST_WORD_GAMES[dead.user_id] = self
            try:
                await self.bot.send_message(
                    dead.user_id,
                    "🕯 <b>SIZNI MAFIYA OTIB KETDI</b>\n\n"
                    "O‘yindan chiqdingiz. Jon berishdan oldin guruhga "
                    "so‘nggi gapingizni baqirib aytmoqchimisiz? 😄",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📝 Ha, so‘z qoldiraman",
                                callback_data=f"lastword:yes:{self.chat_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="Yo‘q, rahmat",
                                callback_data=f"lastword:no:{self.chat_id}",
                            )
                        ],
                    ]),
                )
            except Exception:
                log.exception("Could not send last-word prompt to %s", dead.user_id)
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
                    log.exception("Could not send detective result to %s", uid)

        # Return to the main game loop after the night has fully resolved.
        if self.phase == "night":
            self.phase = "playing"

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
        # Keep ordinary members muted throughout the whole game.
        # Voting and night actions are handled by inline buttons.
        await self.set_group_chat(discussion=False)
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

        await self.send_phase_image(
            "day",
            f"☀️ <b>{self.round}-KUN</b>\n"
            f"Muhokama qiling va ovoz bering. "
            f"⏳ {self.deadline_seconds['day']} soniya",
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

        # Muhokama va ovoz berish tugadi — keyingi tun uchun chatni yoping.
        await self.set_group_chat(discussion=False)

        counts = Counter(self.votes.values())

        # Ovoz berish yakunida kim kimga ovoz berganini guruhga ko‘rsatish.
        if self.votes:
            vote_lines = []
            for voter_id, target_id in self.votes.items():
                voter = self.players.get(voter_id)
                target = self.players.get(target_id)
                if voter and target:
                    vote_lines.append(
                        f"• {self.player_link(voter)} ➜ {self.player_link(target)}"
                    )
            await self.send(
                "📊 <b>RAUND YAKUNI — OVOZLAR</b>\n\n"
                + "\n".join(vote_lines)
                + "\n\n<b>Umumiy hisob:</b>\n"
                + "\n".join(
                    f"• {self.player_link(self.players[uid])}: <b>{count}</b> ta"
                    for uid, count in counts.most_common()
                    if uid in self.players
                )
            )
        else:
            await self.send("🗳 Bu kuni hech kim ovoz bermadi.")

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
                    "⚖️ <b>XALQ HUKMI IJRO ETILDI!</b>\n\n"
                    f"🪢 {self.player_link(out)} ko‘pchilik ovozi bilan "
                    "dor ostiga yuborildi va o‘yindan chiqarildi!\n"
                    f"🎭 Uning haqiqiy roli: <b>{ROLE_NAMES[out.role]}</b>"
                )
            else:
                await self.send(
                    "⚖️ Ovozlar teng. Hech kim chiqarilmadi."
                )
        else:
            await self.send("⚖️ Ovoz berilmadi.")

        # Return to the main game loop so winner checks and the next night run.
        if self.phase == "day":
            self.phase = "playing"

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

        if voter_id in self.votes:
            return "Siz bu raundda allaqachon ovoz bergansiz."

        self.votes[voter_id] = target_id
        await self.send(
            "🗳 <b>OVOZ BERILDI</b>\n\n"
            f"{self.player_link(voter)}  ➜  {self.player_link(target)}\n"
            f"<i>Jami ovozlar: {len(self.votes)}/{len(self.alive())}</i>"
        )

        if len(self.votes) >= len(self.alive()):
            self.phase_event.set()

        return "✅ Ovozingiz qabul qilindi."

    async def check_winner(self):
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

        winning_players = [
            p for p in self.players.values()
            if (
                p.role == won_role
                or (won_role == "civilian" and p.role != "mafia")
            )
        ]
        winner_names = "\n".join(
            f"🏆 {self.player_link(p)}" for p in winning_players
        ) or "—"
        reveal = "\n".join(
            f"{'💀' if not p.alive else '🟢'} {self.player_link(p)} — <b>{ROLE_NAMES[p.role]}</b>"
            for p in self.players.values()
        )
        await self.send(
            f"🩸 <b>ABE VAYN — O‘YIN YAKUNLANDI</b>\n\n"
            f"{winner}\n\n"
            f"🏆 <b>G‘OLIBLAR:</b>\n{winner_names}\n\n"
            f"🎭 <b>HAQIQIY ROLLAR:</b>\n{reveal}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Yana bir raund uchun /game buyrug‘ini bering."
        )

        for p in self.players.values():
            won = (
                p.role == won_role
                or (won_role == "civilian" and p.role != "mafia")
            )

            await db.add_result(
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


@router.message(Command("abe"))
async def invite_random_players(message: Message):
    if message.chat.type not in ("group", "supergroup") or not message.from_user:
        await message.answer("📣 /abe buyrug‘ini guruh ichida ishlating.")
        return

    await db.save_group_user(message.chat.id, message.from_user)
    candidates = await db.recent_group_users(message.chat.id, 300)
    random.shuffle(candidates)

    selected = []
    for user_id, full_name in candidates:
        if user_id == message.from_user.id:
            continue
        try:
            member = await message.bot.get_chat_member(message.chat.id, user_id)
            if member.status in ("left", "kicked"):
                continue
        except Exception:
            continue
        selected.append((user_id, full_name))
        if len(selected) == 10:
            break

    if not selected:
        await message.answer(
            "📣 Hozircha chaqirish uchun tanish guruh a’zolari topilmadi. "
            "A’zolar guruhda yozishgan sari ro‘yxat to‘planadi."
        )
        return

    mentions = "\n".join(
        f'🎲 <a href="tg://user?id={user_id}">{escape(name)}</a>'
        for user_id, name in selected
    )
    await message.answer(
        "📣 <b>ABE VAYN SIZNI O‘YINGA CHAQIRYAPTI!</b>\n\n"
        "Tasodifiy tanlangan 10 tagacha guruh a’zosi:\n"
        f"{mentions}\n\n"
        "🎭 Kim jasur? /game orqali o‘yinga qo‘shiling!"
    )


@router.message(Command("game"))
async def create_game(message: Message, command: CommandObject):
    if message.chat.type == "private":
        await message.answer(
            "🎭 O‘yinni guruh ichida /game buyrug‘i bilan boshlang."
        )
        return

    if not await is_group_admin(message.bot, message.chat.id, message.from_user.id):
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

    # Lock member chat messages as soon as /game is opened.
    # Telegram admins remain able to write; players use the bot buttons.
    locked = await game.set_group_chat(discussion=False)
    if not locked:
        await message.answer(
            "⚠️ Guruh yozishmalarini yopib bo‘lmadi.\n"
            "Botni guruhda admin qiling va <b>A’zolarni cheklash</b> "
            "ruxsatini yoqing, keyin /game ni qayta bosing."
        )
        return

    GAMES[chat_id] = game
    try:
        sent = await message.answer(
            game.lobby_text(),
            reply_markup=game.lobby_keyboard(),
        )
        game.lobby_message_id = sent.message_id
        game.lobby_is_photo = False
        game.task = asyncio.create_task(game.run())
    except Exception:
        GAMES.pop(chat_id, None)
        await game.restore_group_chat()
        raise


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


@router.callback_query(F.data.startswith("lastword:"))
async def last_word_choice(call: CallbackQuery):
    try:
        _, choice, chat_id = call.data.split(":")
        chat_id = int(chat_id)
    except ValueError:
        await call.answer("So‘rov noto‘g‘ri.", show_alert=True)
        return

    game = LAST_WORD_GAMES.get(call.from_user.id)
    player = game.players.get(call.from_user.id) if game else None
    if not game or game.chat_id != chat_id or not player or player.alive:
        await call.answer("Bu so‘rov endi faol emas.", show_alert=True)
        return

    if choice == "yes":
        PENDING_LAST_WORDS[call.from_user.id] = game
        LAST_WORD_GAMES.pop(call.from_user.id, None)
        await call.answer("Yozishingiz mumkin.")
        await call.message.answer(
            "📢 <b>OXIRGI GAPPINGIZNI YOZING!</b>\n"
            "Xabaringiz guruhga ismingiz bilan: "
            "«Jon berishidan oldin baqirdi...» deb chiqariladi. 😄\n"
            "500 belgigacha yozing."
        )
    else:
        PENDING_LAST_WORDS.pop(call.from_user.id, None)
        LAST_WORD_GAMES.pop(call.from_user.id, None)
        await call.answer("Mayli. O‘yinda qatnashganingiz uchun rahmat.")


@router.message(
    F.chat.type == "private",
    F.text,
    lambda message: bool(message.from_user and message.from_user.id in PENDING_LAST_WORDS),
)
async def publish_last_word(message: Message):
    game = PENDING_LAST_WORDS.pop(message.from_user.id, None)
    if not game:
        await message.answer("O‘yin yakunlangan. So‘nggi so‘zingizni yuborib bo‘lmadi.")
        return

    words = (message.text or "").strip()
    if not words or words.startswith("/"):
        PENDING_LAST_WORDS[message.from_user.id] = game
        await message.answer("Iltimos, oddiy matn ko‘rinishida so‘nggi so‘zingizni yozing.")
        return

    words = words[:500]
    player = game.players.get(message.from_user.id)
    name = game.player_link(player) if player else escape(message.from_user.full_name)
    await game.send(
        "📢 <b>SO‘NGGI NAFASIDAN OLDIN BAQIRDI!</b>\n\n"
        f"😵‍💫 {name}:\n"
        f"«<i>{escape(words)}</i>»"
    )
    await message.answer("✅ So‘nggi so‘zingiz guruhga yuborildi.")


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



@router.message(Command("players"))
async def list_players(message: Message):
    if message.chat.type != "private" and not await is_group_admin(message.bot, message.chat.id, message.from_user.id):
        return
    game = GAMES.get(message.chat.id)
    if not game:
        await message.answer("ℹ️ Hozir bu guruhda faol o‘yin yo‘q.")
        return
    alive = [p for p in game.players.values() if p.alive]
    dead = [p for p in game.players.values() if not p.alive]
    lines = ["👥 <b>O‘YINCHILAR RO‘YXATI</b>", ""]
    lines.append(f"🟢 Tiriklar ({len(alive)}):")
    lines.extend(f"• {game.player_link(p)}" for p in alive)
    if dead:
        lines.extend(["", f"💀 O‘yindan chiqqanlar ({len(dead)}):"])
        lines.extend(f"• {game.player_link(p)}" for p in dead)
    await message.answer("\n".join(lines))


@router.message(Command("status"))
async def game_status(message: Message):
    if message.chat.type != "private" and not await is_group_admin(message.bot, message.chat.id, message.from_user.id):
        return
    game = GAMES.get(message.chat.id)
    if not game:
        await message.answer("ℹ️ Hozir bu guruhda faol o‘yin yo‘q. /game bilan boshlang.")
        return
    phase_names = {
        "lobby": "Qabul davom etmoqda",
        "starting": "Boshlanmoqda",
        "playing": "O‘yin davom etmoqda",
        "night": "🌙 Tun",
        "day": "☀️ Kun",
        "cancelled": "Bekor qilingan",
        "stopped": "To‘xtatilgan",
    }
    await message.answer(
        f"🎭 <b>O‘YIN HOLATI</b>\n"
        f"📍 Bosqich: {phase_names.get(game.phase, game.phase)}\n"
        f"👥 O‘yinchilar: {len(game.players)}\n"
        f"🟢 Tiriklar: {len(game.alive())}\n"
        f"🔄 Raund: {game.round}"
    )

@router.message((F.text | F.caption) & F.chat.type.in_({"group", "supergroup"}) & ~F.text.startswith("/"))
async def anti_advertising(message: Message):
    """Delete promotional links and forwarded promotions from non-admin members."""
    if message.chat.type not in ("group", "supergroup"):
        return
    if not message.from_user:
        return

    await db.save_group_user(message.chat.id, message.from_user)

    if await is_group_admin(message.bot, message.chat.id, message.from_user.id):
        return

    text_value = message.text or message.caption or ""
    lowered = text_value.lower()
    has_link = (
        "http://" in lowered
        or "https://" in lowered
        or "www." in lowered
        or "t.me/" in lowered
        or "telegram.me/" in lowered
    )
    entities = (message.entities or []) + (message.caption_entities or [])
    has_link = has_link or any(
        entity.type in ("url", "text_link")
        for entity in entities
    )
    is_forwarded = message.forward_origin is not None

    if has_link or is_forwarded:
        try:
            await message.delete()
        except Exception:
            log.exception("Could not delete advertisement in chat %s", message.chat.id)

