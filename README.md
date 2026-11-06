# Mafia Telegram Bot — professional starter

## Imkoniyatlar
- Guruhda `/game` orqali lobby ochish; ro‘yxatdagi o‘yinchilar jonli ko‘rinadi.
- Kamida 5, ko‘pi bilan 20 o‘yinchi.
- Rollar shaxsiy chatga yuboriladi: mafiya, doktor, komissar, tinch aholi.
- Kecha: mafiya hujum qiladi, doktor himoya qiladi, komissar tekshiradi.
- Kunduz: muhokama taymeri, so‘ng guruhdagi ovoz berish.
- Ovoz natijasi, chiqarilgan o‘yinchi roli va g‘olib aniqlanadi.
- Tugmali admin panel, statistika, broadcast, admin qo‘shish, bloklash.
- Majburiy kanal qo‘shish/o‘chirish va obunani tekshirish.

## Muhim sozlash
1. Railway Variables ga `BOT_TOKEN` va `ADMIN_IDS=8007670371` kiriting.
2. `requirements.txt`, `main.py`, `game.py`, `admin.py`, `db.py` ni GitHub root papkasiga joylang.
3. Railway start command: `python main.py`.
4. Botni guruhga admin qiling (xabar yuborish va xabarni tahrirlash huquqi).
5. O‘yinchilar botga shaxsiy chatda `/start` yozishi shart — Telegram bot foydalanuvchiga birinchi bo‘lib DM yubora olmaydi.
6. Majburiy kanal ishlatmoqchi bo‘lsangiz, botni kanalga admin qilib, `/admin` → Majburiy kanal orqali qo‘shing.

## Rasm
`assets/night.jpg` va `assets/day.jpg` rasmlari kecha/kunduz bosqichida Telegram guruhiga avtomatik yuboriladi. `assets/mafia_concept.png` umumiy dizayn konsepsiyasidir.

## Cheklovlar
- O‘yin holati hozir RAMda saqlanadi: Railway qayta ishga tushsa davom etayotgan o‘yin to‘xtaydi.
- Taymerlar va o‘yin bir Railway instance uchun mo‘ljallangan.
- Avval test guruhida tekshiring.
