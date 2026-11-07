from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import random

# Original ABE VAYN MAFIA artwork. Portrait 3:4 cards fit Telegram photo previews.
W, H = 900, 1200
PALETTES = {
    "mafia": ((7, 7, 13), (66, 12, 27), (236, 55, 72)),
    "doctor": ((5, 13, 23), (12, 48, 62), (75, 205, 205)),
    "detective": ((5, 10, 25), (23, 39, 76), (112, 164, 255)),
    "civilian": ((18, 13, 10), (70, 43, 20), (226, 174, 91)),
    "night": ((3, 6, 18), (13, 23, 51), (132, 164, 232)),
    "day": ((42, 20, 13), (112, 58, 25), (255, 190, 93)),
    "welcome": ((4, 5, 11), (42, 8, 20), (238, 52, 70)),
}
ROLE_DATA = {
    "mafia": ("MAFIYA", "TUN HUKMDORI", "TUNDA NISHON TANLANG", "♠"),
    "doctor": ("SHIFOKOR", "JAMOANING HIMOYACHISI", "HAR TUN BIR KISHINI ASRANG", "+"),
    "detective": ("KOMISSAR", "HAQIQAT IZLOVCHI", "HAR TUN BIR ROLNI TEKSHIRING", "?"),
    "civilian": ("TINCH AHOLI", "SHAHAR FUQAROSI", "KUNDUZI MAFIYANI TOPING", "✦"),
}

def _font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

def _background(top, bottom):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        t = y / (H - 1)
        base = tuple(int(top[i] * (1-t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            glow = max(0.0, 1 - math.sqrt(((x-W*.5)/(W*.85))**2 + ((y-H*.38)/(H*.95))**2))
            px[x, y] = tuple(min(255, int(c + glow*11)) for c in base)
    return im.convert("RGBA")

def _city(draw, accent, horizon=790):
    # Layered original city skyline, kept below the character silhouette.
    rng = random.Random(19)
    for layer, color in [(0, (5, 7, 13, 220)), (1, (9, 10, 18, 245))]:
        x = -10
        while x < W:
            width = rng.randint(38, 100)
            height = rng.randint(100, 300) if layer == 0 else rng.randint(70, 220)
            y = horizon - height + (30 if layer == 0 else 0)
            draw.rectangle((x, y, x+width, horizon+80), fill=color)
            if rng.random() > .35:
                draw.polygon([(x-5,y+8),(x+width//2,y-25),(x+width+5,y+8)], fill=color)
            for wx in range(x+10, x+width-5, 18):
                for wy in range(y+25, horizon-10, 28):
                    if rng.random() > .56:
                        draw.rectangle((wx,wy,wx+5,wy+9), fill=(*accent, 90))
            x += width - 4

def _frame(draw, accent):
    draw.rounded_rectangle((24, 24, W-24, H-24), radius=38, outline=(*accent, 190), width=4)
    draw.rounded_rectangle((42, 42, W-42, H-42), radius=29, outline=(255,255,255,35), width=2)
    for x in (66, W-66):
        for y in (66, H-66):
            draw.ellipse((x-6,y-6,x+6,y+6), fill=(*accent,220))
    draw.line((76, 112, 260, 112), fill=(*accent,210), width=4)
    draw.line((W-260, H-112, W-76, H-112), fill=(*accent,210), width=4)

def _silhouette(draw, role, accent):
    cx = W // 2
    # Backlight ring
    draw.ellipse((cx-235, 125, cx+235, 595), outline=(*accent,75), width=5)
    draw.ellipse((cx-205, 155, cx+205, 565), outline=(255,255,255,24), width=2)
    if role == "mafia":
        draw.polygon([(cx-205,310),(cx-155,205),(cx+150,205),(cx+205,310)], fill=(3,4,9,255))
        draw.polygon([(cx-205,310),(cx,280),(cx+205,310),(cx+150,345),(cx-150,345)], fill=(12,10,16,255))
        draw.ellipse((cx-112,295,cx+112,520), fill=(17,13,17,255))
        draw.polygon([(cx-315,850),(cx-220,500),(cx-95,455),(cx,610),(cx+95,455),(cx+220,500),(cx+315,850)], fill=(5,6,12,255))
        draw.polygon([(cx-92,500),(cx,670),(cx+92,500)], fill=(*accent,210))
        draw.line((cx-72,365,cx+72,365), fill=(*accent,180), width=7)
    elif role == "doctor":
        draw.ellipse((cx-112,245,cx+112,465), fill=(20,30,35,255))
        draw.rounded_rectangle((cx-165,430,cx+165,810), radius=68, fill=(196,207,207,255))
        draw.polygon([(cx-65,445),(cx,570),(cx+65,445)], fill=(10,36,48,255))
        draw.rectangle((cx-19,540,cx+19,690), fill=(18,130,145,255))
        draw.rectangle((cx-83,595,cx+83,633), fill=(18,130,145,255))
        draw.line((cx+112,520,cx+112,760), fill=(255,255,255,170), width=5)
    elif role == "detective":
        draw.polygon([(cx-190,325),(cx-130,215),(cx+130,215),(cx+190,325)], fill=(4,7,16,255))
        draw.ellipse((cx-112,280,cx+112,500), fill=(22,25,34,255))
        draw.polygon([(cx-300,850),(cx-205,500),(cx-105,455),(cx,590),(cx+105,455),(cx+205,500),(cx+300,850)], fill=(5,9,20,255))
        draw.line((cx-82,370,cx+82,370), fill=(*accent,230), width=12)
        draw.ellipse((cx-19,351,cx+19,389), fill=(*accent,255))
        draw.line((cx+135,560,cx+215,780), fill=(*accent,170), width=8)
    else:
        draw.ellipse((cx-112,270,cx+112,495), fill=(73,48,32,255))
        draw.rounded_rectangle((cx-170,455,cx+170,820), radius=80, fill=(35,37,35,255))
        draw.polygon([(cx-75,475),(cx,600),(cx+75,475)], fill=(*accent,210))
        draw.ellipse((cx-18,545,cx+18,581), fill=(12,13,17,255))

def _png(im):
    out = BytesIO()
    im.save(out, "PNG", optimize=True)
    out.seek(0)
    return out

def role_card(role):
    role = role if role in ROLE_DATA else "civilian"
    top, bottom, accent = PALETTES[role]
    im = _background(top, bottom)
    draw = ImageDraw.Draw(im, "RGBA")
    _city(draw, accent, 850)
    _silhouette(draw, role, accent)
    _frame(draw, accent)
    name, subtitle, hint, symbol = ROLE_DATA[role]
    # Opaque lower panel guarantees all text remains inside Telegram crop-safe area.
    draw.rounded_rectangle((66, 820, W-66, 1115), radius=34, fill=(3,5,11,238), outline=(*accent,220), width=3)
    draw.text((W//2, 866), "SIZNING ROLINGIZ", font=_font(30, True), fill=(*accent,255), anchor="mm")
    draw.text((W//2, 945), name, font=_font(66 if len(name)<12 else 53, True), fill=(255,255,255,255), anchor="mm")
    draw.text((W//2, 1012), subtitle, font=_font(23, True), fill=(*accent,255), anchor="mm")
    draw.text((W//2, 1070), hint, font=_font(20, True), fill=(235,237,242,255), anchor="mm")
    draw.text((W//2, 710), symbol, font=_font(88, True), fill=(*accent,240), anchor="mm")
    draw.text((W//2, 72), "ABE VAYN  /  MAFIA", font=_font(23, True), fill=(245,245,250,230), anchor="mm")
    return _png(im)

def phase_card(phase):
    key = "night" if phase == "night" else "day"
    top, bottom, accent = PALETTES[key]
    im = _background(top, bottom)
    draw = ImageDraw.Draw(im, "RGBA")
    _city(draw, accent, 850)
    _frame(draw, accent)
    cx, cy = W//2, 420
    if key == "night":
        draw.ellipse((cx-170,cy-170,cx+170,cy+170), fill=(*accent,235))
        draw.ellipse((cx-85,cy-210,cx+225,cy+100), fill=(*bottom,255))
        rng = random.Random(7)
        for _ in range(75):
            x, y = rng.randint(80,W-80), rng.randint(120,720)
            r = rng.choice((2,3,4))
            draw.ellipse((x-r,y-r,x+r,y+r), fill=(255,255,255,rng.randint(90,220)))
        title, sub = "TUN", "SHAHAR UYQUDA..."
        symbol = "☾"
    else:
        draw.ellipse((cx-145,cy-145,cx+145,cy+145), fill=(*accent,255))
        for a in range(0,360,30):
            x1=cx+math.cos(math.radians(a))*185
            y1=cy+math.sin(math.radians(a))*185
            x2=cx+math.cos(math.radians(a))*235
            y2=cy+math.sin(math.radians(a))*235
            draw.line((x1,y1,x2,y2), fill=(*accent,230), width=12)
        title, sub = "KUNDUZ", "SHAHAR UYG'ONDI!"
        symbol = "☀"
    draw.rounded_rectangle((70,770,W-70,1050), radius=36, fill=(3,5,11,225), outline=(*accent,210), width=3)
    draw.text((cx,845), title, font=_font(100,True), fill=(255,255,255,255), anchor="mm")
    draw.text((cx,940), sub, font=_font(30,True), fill=(*accent,255), anchor="mm")
    draw.text((cx,1080), "ABE VAYN  •  MAFIA", font=_font(27,True), fill=(*accent,255), anchor="mm")
    return _png(im)

def welcome_card():
    top, bottom, accent = PALETTES["welcome"]
    im = _background(top, bottom)
    draw = ImageDraw.Draw(im, "RGBA")
    _city(draw, accent, 930)
    _frame(draw, accent)
    cx = W//2
    # Original noir king silhouette and red halo.
    draw.ellipse((cx-210,175,cx+210,595), outline=(*accent,170), width=7)
    draw.polygon([(cx-185,365),(cx-135,245),(cx+135,245),(cx+185,365)], fill=(2,3,8,255))
    draw.polygon([(cx-185,365),(cx,330),(cx+185,365),(cx+125,395),(cx-125,395)], fill=(10,8,14,255))
    draw.ellipse((cx-105,355,cx+105,565), fill=(10,9,14,255))
    draw.polygon([(cx-300,870),(cx-205,570),(cx-100,520),(cx,665),(cx+100,520),(cx+205,570),(cx+300,870)], fill=(3,4,10,255))
    draw.text((cx,755), "ABE VAYN", font=_font(82,True), fill=(255,255,255,255), anchor="mm")
    draw.text((cx,875), "MAFIA", font=_font(112,True), fill=(*accent,255), anchor="mm")
    draw.text((cx,1030), "ISHONCH  •  AQL  •  STRATEGIYA", font=_font(24,True), fill=(245,235,235,255), anchor="mm")
    return _png(im)
