from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import random

# ABE VAYN MAFIA — original premium noir artwork.
W, H = 900, 1200
PALETTES = {
    "mafia": ((5, 5, 12), (35, 5, 20), (255, 48, 75), (255, 135, 145)),
    "doctor": ((4, 12, 20), (5, 38, 48), (45, 220, 205), (160, 255, 235)),
    "detective": ((5, 8, 22), (12, 24, 54), (90, 155, 255), (175, 210, 255)),
    "civilian": ((17, 11, 8), (53, 29, 14), (235, 170, 75), (255, 220, 155)),
    "night": ((3, 5, 15), (13, 20, 44), (120, 155, 255), (210, 225, 255)),
    "day": ((38, 17, 9), (102, 48, 19), (255, 174, 65), (255, 228, 155)),
    "welcome": ((3, 3, 9), (36, 4, 17), (255, 42, 70), (255, 145, 155)),
}
ROLE_DATA = {
    "mafia": ("MAFIYA", "TUN HUKMDORI", "TUNDA NISHON TANLANG", "♠", "Shahar sizning qo‘lingizda."),
    "doctor": ("SHIFOKOR", "JAMOANING HIMOYACHISI", "HAR TUN BIR KISHINI ASRANG", "+", "Bir hayot — butun o‘yinni o‘zgartiradi."),
    "detective": ("KOMISSAR", "HAQIQAT IZLOVCHI", "HAR TUN BIR ROLNI TEKSHIRING", "⌕", "Haqiqat zulmatda ham yashirinmaydi."),
    "civilian": ("TINCH AHOLI", "SHAHAR FUQAROSI", "KUNDUZI MAFIYANI TOPING", "✦", "Aqlingiz — eng kuchli qurolingiz."),
}

def _font(size, bold=False, serif=False):
    candidates = []
    if serif:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()

def _gradient(top, bottom):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        t = y / (H - 1)
        for x in range(W):
            glow = max(0, 1 - math.sqrt(((x-W*.50)/(W*.90))**2 + ((y-H*.36)/(H*.95))**2))
            grain = ((x*13 + y*7) % 11) - 5
            px[x, y] = tuple(max(0, min(255, int(top[i]*(1-t) + bottom[i]*t + glow*12 + grain*.25))) for i in range(3))
    return im.convert("RGBA")

def _glow(im, box, color, blur=30, width=10):
    layer = Image.new("RGBA", im.size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=30, outline=(*color,210), width=width)
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    im.alpha_composite(layer)

def _city(draw, accent, horizon=850, seed=17):
    rng = random.Random(seed)
    # distant skyline
    for layer, base, low, high in [
        (0, (9, 10, 19, 205), 130, 330),
        (1, (5, 6, 13, 245), 90, 250),
    ]:
        x = -15
        while x < W + 20:
            bw = rng.randint(38, 92)
            bh = rng.randint(low, high)
            y = horizon - bh + (28 if layer == 0 else 0)
            draw.rectangle((x, y, x+bw, horizon+40), fill=base)
            if rng.random() > .45:
                draw.polygon([(x-4,y+5),(x+bw//2,y-22),(x+bw+4,y+5)], fill=base)
            for wx in range(x+9, x+bw-4, 16):
                for wy in range(y+25, horizon-10, 25):
                    if rng.random() > .56:
                        draw.rounded_rectangle((wx,wy,wx+5,wy+9), radius=2, fill=(*accent, rng.randint(75,180)))
            x += bw - 5

def _stars(draw, accent, seed=8, count=70):
    rng = random.Random(seed)
    for _ in range(count):
        x, y = rng.randint(60,W-60), rng.randint(90,800)
        r = rng.choice((1,2,3))
        draw.ellipse((x-r,y-r,x+r,y+r), fill=(255,255,255,rng.randint(80,180)))
    for _ in range(12):
        x, y = rng.randint(80,W-80), rng.randint(180,740)
        draw.line((x-5,y,x+5,y), fill=(*accent,120), width=2)
        draw.line((x,y-5,x,y+5), fill=(*accent,120), width=2)

def _frame(draw, accent, label="PRIVATE DOSSIER"):
    draw.rounded_rectangle((22,22,W-22,H-22), radius=38, outline=(*accent,245), width=4)
    draw.rounded_rectangle((39,39,W-39,H-39), radius=30, outline=(255,255,255,85), width=2)
    draw.line((72,122,270,122), fill=(*accent,240), width=4)
    draw.line((W-270,H-122,W-72,H-122), fill=(*accent,240), width=4)
    for x in (62,W-62):
        for y in (62,H-62):
            draw.ellipse((x-7,y-7,x+7,y+7), fill=(*accent,255))
    draw.text((W//2,78), label, font=_font(18,True), fill=(240,240,248,210), anchor="mm")

def _person(draw, role, accent):
    cx = W//2
    # luminous halo
    draw.ellipse((cx-225,150,cx+225,600), outline=(*accent,70), width=5)
    draw.ellipse((cx-195,180,cx+195,570), outline=(255,255,255,24), width=2)
    if role == "mafia":
        draw.polygon([(cx-205,320),(cx-150,205),(cx+150,205),(cx+205,320),(cx+125,350),(cx-125,350)], fill=(2,3,9,255))
        draw.ellipse((cx-108,295,cx+108,535), fill=(12,10,17,255))
        draw.polygon([(cx-320,870),(cx-230,530),(cx-95,465),(cx,620),(cx+95,465),(cx+230,530),(cx+320,870)], fill=(3,4,10,255))
        draw.polygon([(cx-95,505),(cx,690),(cx+95,505)], fill=(*accent,205))
        draw.line((cx-74,375,cx+74,375), fill=(*accent,210), width=8)
        draw.ellipse((cx-80,365,cx-62,383), fill=(255,255,255,230))
        draw.ellipse((cx+62,365,cx+80,383), fill=(255,255,255,230))
    elif role == "doctor":
        draw.ellipse((cx-108,250,cx+108,475), fill=(16,32,39,255))
        draw.rounded_rectangle((cx-170,430,cx+170,840), radius=65, fill=(168,190,190,255))
        draw.polygon([(cx-68,445),(cx,575),(cx+68,445)], fill=(8,29,42,255))
        draw.rectangle((cx-17,560,cx+17,715), fill=(*accent,255))
        draw.rectangle((cx-83,620,cx+83,654), fill=(*accent,255))
        draw.line((cx+116,520,cx+116,775), fill=(255,255,255,180), width=6)
    elif role == "detective":
        draw.polygon([(cx-190,325),(cx-135,215),(cx+135,215),(cx+190,325)], fill=(3,5,13,255))
        draw.ellipse((cx-108,285,cx+108,510), fill=(18,22,34,255))
        draw.polygon([(cx-310,865),(cx-210,510),(cx-100,455),(cx,600),(cx+100,455),(cx+210,510),(cx+310,865)], fill=(4,8,20,255))
        draw.line((cx-80,380,cx+80,380), fill=(*accent,245), width=11)
        draw.ellipse((cx-18,362,cx+18,398), fill=(255,255,255,255))
        draw.line((cx+140,550,cx+225,790), fill=(*accent,190), width=8)
    else:
        draw.ellipse((cx-108,275,cx+108,500), fill=(75,48,31,255))
        draw.rounded_rectangle((cx-170,460,cx+170,835), radius=75, fill=(31,35,38,255))
        draw.polygon([(cx-75,475),(cx,605),(cx+75,475)], fill=(*accent,210))
        draw.ellipse((cx-18,555,cx+18,591), fill=(12,13,17,255))

def _panel(draw, accent, box, radius=28):
    draw.rounded_rectangle(box, radius=radius, fill=(4,5,12,238), outline=(*accent,220), width=3)

def _png(im):
    out = BytesIO()
    im.convert("RGB").save(out, "PNG", optimize=True)
    out.seek(0)
    return out

def role_card(role):
    role = role if role in ROLE_DATA else "civilian"
    top, bottom, accent, light = PALETTES[role]
    im = _gradient(top, bottom)
    draw = ImageDraw.Draw(im, "RGBA")
    _stars(draw, accent, seed=10)
    _city(draw, accent, 865, seed=11)
    _person(draw, role, accent)
    _frame(draw, accent, "ABE VAYN  /  CLASSIFIED ROLE")
    name, subtitle, hint, symbol, quote = ROLE_DATA[role]
    _panel(draw, accent, (62,820,W-62,1128), 34)
    draw.text((W//2,865), "SIZNING ROLINGIZ", font=_font(30,True), fill=light+(255,), anchor="mm")
    draw.line((220,900,680,900), fill=(*accent,190), width=2)
    draw.text((W//2,962), name, font=_font(68 if len(name)<12 else 54,True,True), fill=(255,255,255,255), anchor="mm", stroke_width=1, stroke_fill=(*accent,130))
    draw.text((W//2,1025), subtitle, font=_font(21,True), fill=light+(255,), anchor="mm")
    draw.text((W//2,1074), hint, font=_font(19,True), fill=(238,239,245,255), anchor="mm")
    draw.text((W//2,730), symbol, font=_font(86,True,True), fill=light+(245,), anchor="mm")
    draw.text((W//2,1155), quote, font=_font(15), fill=(220,220,230,210), anchor="mm")
    return _png(im)

def phase_card(phase):
    key = "night" if phase == "night" else "day"
    top, bottom, accent, light = PALETTES[key]
    im = _gradient(top,bottom)
    draw = ImageDraw.Draw(im,"RGBA")
    _stars(draw,accent,seed=4 if key=="night" else 9,count=100)
    _city(draw,accent,865,seed=23)
    _frame(draw,accent,"ABE VAYN  /  CITY CHRONICLE")
    cx,cy=W//2,405
    if key=="night":
        draw.ellipse((cx-165,cy-165,cx+165,cy+165),fill=light+(245,))
        draw.ellipse((cx-75,cy-205,cx+230,cy+100),fill=bottom+(255,))
        title,sub,symbol="TUN","SIRLI VAQT...","☾"
    else:
        draw.ellipse((cx-135,cy-135,cx+135,cy+135),fill=light+(255,))
        for a in range(0,360,30):
            x1=cx+math.cos(math.radians(a))*175
            y1=cy+math.sin(math.radians(a))*175
            x2=cx+math.cos(math.radians(a))*220
            y2=cy+math.sin(math.radians(a))*220
            draw.line((x1,y1,x2,y2),fill=(*accent,235),width=12)
        title,sub,symbol="KUNDUZ","HAQIQAT VAQTI!","☀"
    _panel(draw,accent,(65,760,W-65,1060),34)
    draw.text((cx,835),symbol,font=_font(65,True,True),fill=light+(255,),anchor="mm")
    draw.text((cx,930),title,font=_font(94,True,True),fill=(255,255,255,255),anchor="mm")
    draw.text((cx,1005),sub,font=_font(27,True),fill=light+(255,),anchor="mm")
    draw.text((cx,1115),"ISHONCH  •  AQL  •  STRATEGIYA",font=_font(19,True),fill=(245,235,238,230),anchor="mm")
    return _png(im)

def welcome_card():
    top,bottom,accent,light=PALETTES["welcome"]
    im=_gradient(top,bottom)
    draw=ImageDraw.Draw(im,"RGBA")
    _stars(draw,accent,seed=31,count=120)
    _city(draw,accent,900,seed=32)
    _frame(draw,accent,"THE CITY NEVER SLEEPS")
    cx=W//2
    # Red eclipse behind the boss silhouette.
    draw.ellipse((cx-220,165,cx+220,605),outline=(*accent,210),width=8)
    draw.ellipse((cx-190,195,cx+190,575),outline=(255,255,255,35),width=2)
    draw.polygon([(cx-195,360),(cx-145,235),(cx+145,235),(cx+195,360),(cx+120,390),(cx-120,390)],fill=(2,3,8,255))
    draw.ellipse((cx-105,350,cx+105,570),fill=(9,8,15,255))
    draw.polygon([(cx-310,900),(cx-210,565),(cx-100,510),(cx,665),(cx+100,510),(cx+210,565),(cx+310,900)],fill=(2,3,9,255))
    _panel(draw,accent,(58,785,W-58,1095),32)
    draw.text((cx,845),"ABE VAYN",font=_font(76,True,True),fill=(255,255,255,255),anchor="mm")
    draw.text((cx,935),"MAFIA",font=_font(108,True,True),fill=light+(255,),anchor="mm",stroke_width=2,stroke_fill=(*accent,170))
    draw.text((cx,1020),"ISHONCH  •  AQL  •  STRATEGIYA",font=_font(20,True),fill=(245,235,240,255),anchor="mm")
    draw.text((cx,1150),"PRIVATE GAME EXPERIENCE  /  EST. 2026",font=_font(14,True),fill=(220,220,230,210),anchor="mm")
    return _png(im)
