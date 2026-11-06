# Telegram Mafia Bot

## Railway orqali ishga tushirish

1. Ushbu fayllarning barchasini GitHub repository root papkasiga joylang.
2. Railway'da shu repository va `main` branch'ni ulang.
3. Railway → Variables ichiga quyidagilarni kiriting:
   - `BOT_TOKEN`: BotFather bergan haqiqiy token
   - `ADMIN_IDS`: o'zingizning Telegram raqamli ID'ingiz
   - `MIN_PLAYERS`: `5`
   - `LOG_LEVEL`: `INFO`
4. Railway → Settings → Deploy → Start Command: `python main.py`
5. Deploy qiling. Deploy Logs ichida `Bot started: @...` yozuvi chiqishi kerak.

## Lokal ishga tushirish

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# .env ichidagi BOT_TOKEN va ADMIN_IDS ni to'ldiring
python main.py
```

## Buyruqlar

- Guruh: `/game`, `/fast`, `/cancelgame`
- Shaxsiy chat: `/start`, `/help`, `/profile`, `/top`, `/stats`

O'yinchilar o'yinga qo'shilish, tungi rol harakatlari va ovoz berishni inline tugmalar orqali bajaradi.
O'yinchilar o'yin boshlanishidan oldin botga shaxsiy chatda `/start` yuborishi kerak, aks holda bot ularga rol xabarini yubora olmaydi.

## Eslatma

- SQLite bazasi `mafia.db` faylida saqlanadi.
- Railway filesystem doimiy saqlanishi reja/tarifga bog'liq. Doimiy statistika kerak bo'lsa, Railway Volume yoki tashqi PostgreSQL ishlating.
- `BOT_TOKEN` ni hech qachon GitHub'ga joylamang.
