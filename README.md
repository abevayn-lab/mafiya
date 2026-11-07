# ABE VAYN MAFIA — Telegram game bot

A branded Uzbek-language Mafia game bot with original noir artwork.

## O‘yin imkoniyatlari
- Guruhda `/game` bilan chiroyli rasmli o‘yin xonasi ochiladi.
- 4–20 o‘yinchi; ro‘yxat qo‘shilgan sari yangilanadi.
- Har bir o‘yinchiga shaxsiy chatda o‘z roliga mos alohida karta yuboriladi.
- Rollar: Mafiya, Shifokor, Komissar va Tinch aholi.
- Tun va kunduz bosqichlari alohida original rasmlar bilan ko‘rsatiladi.
- Mafiya hujumi, shifokor himoyasi, komissar tekshiruvi va kunduzgi ovoz berish.
- O‘yin yakunida g‘olib jamoa va barcha o‘yinchilarning haqiqiy rollari e’lon qilinadi.
- Profil, reyting, guruh statistikasi va admin panel.

## Buyruqlar
- `/start` — bot menyusi va guruhga qo‘shish
- `/game` — guruhda yangi o‘yin
- `/game fast` — tezkor o‘yin
- `/players` — o‘yinchilar ro‘yxati
- `/status` — o‘yin holati
- `/stop` — o‘yinni to‘xtatish (xona egasi yoki guruh admini)
- `/profile` — shaxsiy statistika
- `/top` — reyting
- `/myid` — Telegram ID
- `/admin` — admin panel

## Railway sozlamalari
1. Variables ichida `BOT_TOKEN` kiriting.
2. `ADMIN_IDS` ga admin Telegram ID larini vergul bilan yozing.
3. Start Command: `python main.py`.
4. Bitta Railway replica ishlating — polling rejimida ikkinchi nusxa TelegramConflictError chiqarishi mumkin.
5. Botni guruhga qo‘shing va xabar yuborish huquqini bering.
6. Har bir o‘yinchi botga shaxsiy chatda `/start` yuborishi kerak. Telegram bot foydalanuvchi birinchi yozmaguncha unga shaxsiy xabar yubora olmaydi.

## Texnik ma’lumot
- Python 3.11+
- aiogram 3
- SQLite (aiosqlite)
- Pillow orqali original 3:4 portret kartalar yaratiladi.
- O‘yin holati RAMda saqlanadi; Railway qayta ishga tushsa davom etayotgan o‘yin to‘xtaydi.
