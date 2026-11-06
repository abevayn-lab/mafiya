import asyncio, random, os, logging
from collections import Counter
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from pathlib import Path
import db

router = Router()
GAMES = {}
MIN_PLAYERS = 5
MAX_PLAYERS = 20
NIGHT_SECONDS = int(os.getenv("NIGHT_SECONDS", "45"))
DAY_SECONDS = int(os.getenv("DAY_SECONDS", "90"))
VOTE_SECONDS = int(os.getenv("VOTE_SECONDS", "45"))
log = logging.getLogger(__name__)

ROLE_INFO = {
    "mafia": ("🔫 Mafiya", "Siz mafiyasiz. Kechasi bir o‘yinchini tanlab yo‘q qilishga ovoz bering."),
    "doctor": ("🩺 Doktor", "Siz doktорsiz. Kechasi bir o‘yinchini himoya qiling. O‘zingizni ham tanlashingiz mumkin."),
    "detective": ("🕵️ Komissar", "Siz komissarsiz. Kechasi bir o‘yinchini tekshiring va uning mafiyaligini biling."),
    "civilian": ("👤 Tinch aholi", "Siz tinch aholisisiz. Kunduzgi muhokama va ovoz berishda mafiyani toping.")
}
NIGHT_ART = "🌙 <b>KECHASI</b>\nShahar uxlamoqda... Mafiya o‘z harakatini qilmoqda."
DAY_ART = "☀️ <b>KUNDUZ</b>\nShahar uyg‘ondi! Muhokama qiling va gumondorni toping."

def player_name(p):
    return p["name"]

def alive_ids(g):
    return [uid for uid,p in g["players"].items() if p["alive"]]

def lobby_text(g):
    names = [f"{i+1}. {p['name']}" for i,p in enumerate(g["players"].values())]
    return ("🎭 <b>MAFIA — O‘YIN XONASI</b>\n\n"
            f"👥 O‘yinchilar: <b>{len(g['players'])}/{MAX_PLAYERS}</b>\n"
            f"🔻 Boshlash uchun kamida {MIN_PLAYERS} kishi kerak.\n\n"
            + ("\n".join(names) if names else "Hali hech kim qo‘shilmadi.")
            + "\n\n👇 Qo‘shilish uchun tugmani bosing.")

def lobby_kb(chat_id, g):
    rows = [[InlineKeyboardButton(text="➕ O‘yinga qo‘shilish", callback_data=f"m:join:{chat_id}")]]
    if len(g["players"]) >= MIN_PLAYERS:
        rows.append([InlineKeyboardButton(text="▶️ O‘yinni boshlash", callback_data=f"m:start:{chat_id}")])
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"m:cancel:{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def refresh_lobby(bot, chat_id):
    g = GAMES.get(chat_id)
    if not g or g["status"] != "lobby": return
    try:
        await bot.edit_message_text(lobby_text(g), chat_id, g["message_id"], reply_markup=lobby_kb(chat_id,g))
    except Exception:
        pass

async def ensure_dm(bot, uid):
    try:
        await bot.send_chat_action(uid, "typing")
        return True
    except Exception:
        return False

async def add_player(bot, chat_id, user):
    g = GAMES.get(chat_id)
    if not g or g["status"] != "lobby": return False, "O‘yin xonasi yopilgan."
    if user.id in g["players"]: return True, "Siz allaqachon ro‘yxatdasiz."
    if len(g["players"]) >= MAX_PLAYERS: return False, "O‘yinchilar soni to‘ldi."
    g["players"][user.id] = {"name": user.full_name, "role": None, "alive": True}
    await refresh_lobby(bot, chat_id)
    return True, "O‘yinga qo‘shildingiz!"

@router.message(Command("game"))
async def create_game(message: Message):
    if message.chat.type == "private":
        await message.answer("O‘yinni guruhda /game buyrug‘i bilan boshlang.")
        return
    if message.chat.id in GAMES and GAMES[message.chat.id]["status"] in ("lobby","night","day","vote"):
        await message.answer("Bu guruhda allaqachon faol o‘yin bor.")
        return
    await db.save_group(message.chat)
    user = message.from_user
    g = {"chat_id":message.chat.id, "host":user.id, "players":{}, "status":"lobby",
         "message_id":None, "night_actions":{}, "votes":{}, "round":0, "timer":None}
    GAMES[message.chat.id] = g
    g["players"][user.id] = {"name":user.full_name,"role":None,"alive":True}
    sent = await message.answer(lobby_text(g), reply_markup=lobby_kb(message.chat.id,g))
    g["message_id"] = sent.message_id

@router.callback_query(F.data.startswith("m:join:"))
async def join_game(call: CallbackQuery):
    chat_id = int(call.data.rsplit(":",1)[1])
    ok, msg = await add_player(call.bot, chat_id, call.from_user)
    if ok:
        await call.answer(msg, show_alert=True)
        try:
            await call.bot.send_message(call.from_user.id, "🤝 Guruhdagi Mafia o‘yiniga qo‘shildingiz. O‘yin boshlanganda rolingiz shu yerga yuboriladi.")
        except Exception:
            me = await call.bot.get_me()
            link = f"https://t.me/{me.username}?start=play_{chat_id}"
            await call.message.answer(f"{call.from_user.full_name}, botga avval shaxsiy xabar yozing:", 
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🤖 Botni ochish",url=link)]]))
    else:
        await call.answer(msg, show_alert=True)

async def join_from_start(message, payload):
    if not payload.startswith("play_"): return
    try: chat_id = int(payload.split("_",1)[1])
    except ValueError: return
    ok, msg = await add_player(message.bot, chat_id, message.from_user)
    await message.answer("🎮 " + msg)

@router.callback_query(F.data.startswith("m:cancel:"))
async def cancel_game(call: CallbackQuery):
    chat_id = int(call.data.rsplit(":",1)[1])
    g = GAMES.get(chat_id)
    if not g or call.from_user.id != g["host"]:
        await call.answer("Faqat xona egasi bekor qila oladi.", show_alert=True); return
    if g.get("timer"): g["timer"].cancel()
    GAMES.pop(chat_id,None)
    await call.message.edit_text("❌ O‘yin bekor qilindi.")
    await call.answer()

@router.callback_query(F.data.startswith("m:start:"))
async def start_game(call: CallbackQuery):
    chat_id = int(call.data.rsplit(":",1)[1])
    g = GAMES.get(chat_id)
    if not g or call.from_user.id != g["host"]:
        await call.answer("Faqat xona egasi boshlashi mumkin.", show_alert=True); return
    if len(g["players"]) < MIN_PLAYERS:
        await call.answer(f"Kamida {MIN_PLAYERS} o‘yinchi kerak.", show_alert=True); return
    # Check private access for every player before dealing roles.
    inaccessible = []
    for uid in g["players"]:
        try: await call.bot.send_chat_action(uid, "typing")
        except Exception: inaccessible.append(g["players"][uid]["name"])
    if inaccessible:
        await call.answer("Hamma o‘yinchi botni shaxsiy chatda ochishi kerak.", show_alert=True)
        await call.message.answer("⚠️ Botga /start yozishi kerak:\n" + "\n".join("• "+n for n in inaccessible))
        return
    ids = list(g["players"])
    random.shuffle(ids)
    mafia_count = max(1, len(ids)//4)
    roles = ["mafia"]*mafia_count + ["doctor","detective"] + ["civilian"]*(len(ids)-mafia_count-2)
    random.shuffle(roles)
    for uid, role in zip(ids,roles): g["players"][uid]["role"] = role
    g["status"] = "night"
    await call.message.edit_text("🎭 <b>O‘YIN BOSHLANDI!</b>\nBarcha rollar shaxsiy xabarga yuborildi.")
    for uid,p in g["players"].items():
        title, desc = ROLE_INFO[p["role"]]
        try:
            await call.bot.send_message(uid, f"🎭 <b>SIZNING ROLINGIZ: {title}</b>\n\n{desc}\n\nGuruh: {call.message.chat.title or 'Mafia'}")
        except Exception:
            log.exception("Could not send role to %s", uid)
    await call.answer("O‘yin boshlandi!")
    await begin_night(call.bot, chat_id)

async def schedule_phase(bot, chat_id, seconds, callback):
    g = GAMES.get(chat_id)
    if not g: return
    async def runner():
        try:
            await asyncio.sleep(seconds)
            await callback(bot,chat_id)
        except asyncio.CancelledError:
            return
    g["timer"] = asyncio.create_task(runner())

def night_kb(chat_id, targets, action):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p["name"], callback_data=f"act:{action}:{chat_id}:{uid}")]
        for uid,p in targets
    ])

async def begin_night(bot, chat_id):
    g = GAMES.get(chat_id)
    if not g: return
    g["status"]="night"; g["round"] += 1; g["night_actions"]={"kill_votes": {}}
    night_pic = Path("assets/night.jpg")
    caption = f"{NIGHT_ART}\n\n🌘 <b>{g['round']}-kecha</b>\n⏳ {NIGHT_SECONDS} soniya."
    if night_pic.exists():
        await bot.send_photo(chat_id, FSInputFile(night_pic), caption=caption)
    else:
        await bot.send_message(chat_id, caption)
    alive = [(uid,g["players"][uid]) for uid in alive_ids(g)]
    for uid,p in alive:
        role=p["role"]
        if role=="mafia":
            targets=[(i,x) for i,x in alive if x["role"]!="mafia"]
            await bot.send_message(uid,"🔫 <b>Mafiya:</b> qurbonni tanlang.",reply_markup=night_kb(chat_id,targets,"kill"))
        elif role=="doctor":
            await bot.send_message(uid,"🩺 <b>Doktor:</b> kimni himoya qilasiz?",reply_markup=night_kb(chat_id,alive,"heal"))
        elif role=="detective":
            targets=[(i,x) for i,x in alive if i!=uid]
            await bot.send_message(uid,"🕵️ <b>Komissar:</b> kimni tekshirasiz?",reply_markup=night_kb(chat_id,targets,"check"))
    await schedule_phase(bot,chat_id,NIGHT_SECONDS,finish_night)

@router.callback_query(F.data.startswith("act:"))
async def night_action(call: CallbackQuery):
    try:
        _,action,chat_id_s,target_s=call.data.split(":")
        chat_id,target=int(chat_id_s),int(target_s)
    except Exception:
        await call.answer("Xato tugma.",show_alert=True); return
    g=GAMES.get(chat_id)
    if not g or g["status"]!="night":
        await call.answer("Hozir tun emas.",show_alert=True); return
    p=g["players"].get(call.from_user.id)
    if not p or not p["alive"]:
        await call.answer("Siz o‘yinda emassiz yoki o‘lgansiz.",show_alert=True); return
    allowed={"kill":"mafia","heal":"doctor","check":"detective"}
    if p["role"]!=allowed[action]:
        await call.answer("Bu harakat sizga tegishli emas.",show_alert=True); return
    if target not in alive_ids(g):
        await call.answer("Bu o‘yinchi faol emas.",show_alert=True); return
    if action=="kill" and g["players"][target]["role"]=="mafia":
        await call.answer("Mafiyani nishonga olib bo‘lmaydi.",show_alert=True); return
    if action == "kill":
        g["night_actions"].setdefault("kill_votes", {})[call.from_user.id] = target
    else:
        g["night_actions"][action]=target
    if action=="check":
        result="MAFIYA 🔫" if g["players"][target]["role"]=="mafia" else "MAFIA EMAS 👤"
        await call.answer("Tekshiruv natijasi: "+result,show_alert=True)
    else:
        await call.answer("Tanlovingiz qabul qilindi.")
        await call.message.edit_reply_markup(reply_markup=None)

async def finish_night(bot,chat_id):
    g=GAMES.get(chat_id)
    if not g or g["status"]!="night": return
    actions=g["night_actions"]
    kill_votes = Counter(actions.get("kill_votes", {}).values())
    victim = kill_votes.most_common(1)[0][0] if kill_votes else None
    healed=actions.get("heal")
    if victim and victim!=healed and victim in g["players"]:
        g["players"][victim]["alive"]=False
        await bot.send_message(chat_id,f"💀 Kechasi <b>{g['players'][victim]['name']}</b> o‘yindan chiqdi. Roli: {ROLE_INFO[g['players'][victim]['role']][0]}")
    else:
        await bot.send_message(chat_id,"🛡 Kechasi hech kim o‘lmadi.")
    winner=check_winner(g)
    if winner:
        await end_game(bot,chat_id,winner); return
    await begin_day(bot,chat_id)

async def begin_day(bot,chat_id):
    g=GAMES.get(chat_id)
    if not g: return
    g["status"]="day"
    alive=[g["players"][uid]["name"] for uid in alive_ids(g)]
    day_pic = Path("assets/day.jpg")
    caption = f"{DAY_ART}\n\n🗣 <b>{DAY_SECONDS} soniya muhokama:</b>\n" + "\n".join("• "+n for n in alive)
    if day_pic.exists():
        await bot.send_photo(chat_id, FSInputFile(day_pic), caption=caption)
    else:
        await bot.send_message(chat_id, caption)
    await bot.send_message(chat_id,"⏳ Muhokama tugagach ovoz berish avtomatik boshlanadi.")
    await schedule_phase(bot,chat_id,DAY_SECONDS,begin_vote)

async def begin_vote(bot,chat_id):
    g=GAMES.get(chat_id)
    if not g: return
    g["status"]="vote"; g["votes"]={}
    targets=[(uid,g["players"][uid]) for uid in alive_ids(g)]
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗳 "+p["name"],callback_data=f"vote:{chat_id}:{uid}")]
        for uid,p in targets
    ])
    await bot.send_message(chat_id,f"🗳 <b>OVOZ BERISH BOSHLANDI</b>\n⏳ {VOTE_SECONDS} soniya. Kimni shahardan chiqaramiz?",reply_markup=kb)
    await schedule_phase(bot,chat_id,VOTE_SECONDS,finish_vote)

@router.callback_query(F.data.startswith("vote:"))
async def cast_vote(call: CallbackQuery):
    try: _,chat_s,target_s=call.data.split(":"); chat_id,target=int(chat_s),int(target_s)
    except Exception:
        await call.answer("Xato."); return
    g=GAMES.get(chat_id)
    if not g or g["status"]!="vote":
        await call.answer("Ovoz berish tugagan.",show_alert=True); return
    p=g["players"].get(call.from_user.id)
    if not p or not p["alive"]:
        await call.answer("Faqat tirik o‘yinchilar ovoz beradi.",show_alert=True); return
    if target not in alive_ids(g):
        await call.answer("Bu o‘yinchi faol emas.",show_alert=True); return
    g["votes"][call.from_user.id]=target
    await call.answer("Ovozingiz qabul qilindi.")
    # Keep the group keyboard active so every living player can cast a vote.

async def finish_vote(bot,chat_id):
    g=GAMES.get(chat_id)
    if not g or g["status"]!="vote": return
    counts=Counter(g["votes"].values())
    if not counts:
        await bot.send_message(chat_id,"🤷 Ovoz berilmadi. Hech kim chiqarilmadi.")
    else:
        top=counts.most_common()
        if len(top)>1 and top[0][1]==top[1][1]:
            await bot.send_message(chat_id,"⚖️ Ovozlar teng. Hech kim chiqarilmadi.")
        else:
            uid,votes=top[0]
            g["players"][uid]["alive"]=False
            await bot.send_message(chat_id,f"🚪 <b>{g['players'][uid]['name']}</b> ovoz bilan chiqarildi ({votes} ovoz).\nRoli: {ROLE_INFO[g['players'][uid]['role']][0]}")
    winner=check_winner(g)
    if winner:
        await end_game(bot,chat_id,winner); return
    await begin_night(bot,chat_id)

def check_winner(g):
    alive=[g["players"][uid]["role"] for uid in alive_ids(g)]
    mafia=sum(r=="mafia" for r in alive)
    others=len(alive)-mafia
    if mafia==0: return "Tinch aholi"
    if mafia>=others: return "Mafiya"
    return None

async def end_game(bot,chat_id,winner):
    g=GAMES.get(chat_id)
    if not g: return
    if g.get("timer"): g["timer"].cancel()
    rows=[]
    for p in g["players"].values():
        status="🟢 tirik" if p["alive"] else "⚫ chiqdi"
        rows.append(f"• {p['name']} — {ROLE_INFO[p['role']][0]} ({status})")
    await bot.send_message(chat_id,f"🏆 <b>O‘YIN TUGADI!</b>\n\nG‘olib: <b>{winner}</b>\n\n<b>Rollar:</b>\n"+"\n".join(rows))
    GAMES.pop(chat_id,None)
