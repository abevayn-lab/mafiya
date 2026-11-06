# Mafia Telegram Bot

## Railway sozlamalari
Variables bo‘limiga quyidagilarni kiriting:

- `BOT_TOKEN` — BotFather bergan token
- `ADMIN_IDS` — bosh admin Telegram ID si. Siz uchun: `8007670371`
- `LOG_LEVEL` — `INFO`
- `DB_PATH` — `mafia.db`

Start command: `python main.py`

## Buyruqlar
- `/start` — botni boshlash (shaxsiy chat)
- `/help` — yordam
- `/game` — guruhda lobby ochish
- `/fast` — lobby ochish
- `/cancelgame` — lobby bekor qilish
- `/admin` — admin panel (shaxsiy chatda)

## Admin panel
Statistika, foydalanuvchilar ro‘yxati, bloklash/blokdan chiqarish, broadcast,
admin qo‘shish/o‘chirish va majburiy kanallar ro‘yxatini boshqarish.

**Eslatma:** `required_channels` hozircha kanal ro‘yxatini saqlaydi, lekin yangi
foydalanuvchilar obunasini avtomatik tekshirish hali ulanmagan. Kanal tekshiruvi
uchun bot kanalda administrator bo‘lishi, `getChatMember` orqali tekshirish
va `/start`, o‘yin buyruqlari hamda callbacklarda middleware/check qo‘shilishi kerak.

**Eslatma:** bu loyiha minimal ishlaydigan asos. O‘yin lobbysi bor, lekin to‘liq
Mafia raundlari/rollar/kecha-kunduz/voting mexanikasi kiritilmagan.
