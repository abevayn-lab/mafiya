from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

W, H = 900, 1200

PALETTES = {
    "mafia": ((18, 10, 20), (112, 25, 42), (245, 190, 145)),
    "doctor": ((7, 25, 35), (15, 105, 112), (170, 235, 220)),
    "detective": ((10, 19, 43), (44, 76, 132), (190, 215, 255)),
    "civilian": ((28, 26, 17), (120, 91, 40), (255, 225, 160)),
    "night": ((5, 10, 26), (27, 42, 79), (180, 200, 255)),
    "day": ((65, 34, 17), (190, 116, 48), (255, 225, 165)),
    "welcome": ((12, 9, 22), (100, 26, 51), (245, 195, 150)),
}

ROLE_DATA = {
    "mafia": ("MAFIYA", "TUN HUKMDORI", "TUNDA NISHON TANLANG", "♠"),
    "doctor": ("SHIFOKOR", "JAMOANING HIMOYACHISI", "HAR TUN BIR KISHINI ASRANG", "+"),
    "detective": ("KOMISSAR", "HAQIQAT IZLOVCHI", "HAR TUN BIR ROLNI TEKSHIRING", "?"),
    "civilian": ("TINCH AHOLI", "SHAHAR FUQAROSI", "KUNDUZI MAFIYANI TOPING", "✦"),
}

def _font(size, bold=False):
    candidates = [
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
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            glow = max(0, 1 - math.sqrt(((x - W * .5) / (W * .8)) ** 2 + ((y - H * .42) / (H * .9)) ** 2))
            px[x, y] = tuple(min(255, int(v + glow * 13)) for v in c)
    return im

def _ornaments(draw, accent):
    for r in (260, 330, 405):
        draw.ellipse((W//2-r, 245-r, W//2+r, 245+r), outline=(*accent, 45), width=3)
    for x in range(55, W, 90):
        draw.line((x, 0, x-160, H), fill=(255,255,255,9), width=1)
    draw.line((54, 90, 220, 90), fill=(*accent, 190), width=4)
    draw.line((W-220, H-100, W-54, H-100), fill=(*accent, 190), width=4)

def _silhouette(draw, role, accent):
    # A clean, original noir-style character silhouette, different for each role.
    cx = W // 2
    draw.ellipse((cx-185, 180, cx+185, 550), fill=(5, 7, 14, 125), outline=(*accent, 150), width=5)
    if role == "mafia":
        # Hat, shadowed face and coat
        draw.polygon([(cx-185, 315), (cx-125, 220), (cx+120, 220), (cx+185, 315)], fill=(8, 8, 14, 255))
        draw.rounded_rectangle((cx-140, 290, cx+140, 500), radius=75, fill=(18, 13, 20, 255))
        draw.polygon([(cx-280, 790), (cx-175, 510), (cx+175, 510), (cx+280, 790)], fill=(9, 8, 15, 255))
        draw.polygon([(cx-90, 510), (cx, 675), (cx+90, 510)], fill=(*accent, 210))
    elif role == "doctor":
        draw.ellipse((cx-108, 250, cx+108, 470), fill=(24, 37, 43, 255))
        draw.rounded_rectangle((cx-150, 430, cx+150, 760), radius=70, fill=(205, 221, 215, 255))
        draw.polygon([(cx-60, 450), (cx, 580), (cx+60, 450)], fill=(18, 105, 112, 255))
        draw.rounded_rectangle((cx-28, 515, cx+28, 650), radius=12, fill=(17, 104, 112, 255))
        draw.rounded_rectangle((cx-90, 565, cx+90, 610), radius=12, fill=(17, 104, 112, 255))
    elif role == "detective":
        draw.polygon([(cx-190, 340), (cx-110, 215), (cx+130, 215), (cx+190, 340)], fill=(9, 13, 26, 255))
        draw.ellipse((cx-105, 275, cx+105, 495), fill=(27, 32, 43, 255))
        draw.polygon([(cx-280, 790), (cx-180, 500), (cx+180, 500), (cx+280, 790)], fill=(10, 17, 34, 255))
        draw.line((cx-90, 370, cx+90, 370), fill=(*accent, 230), width=13)
        draw.ellipse((cx-20, 350, cx+20, 390), fill=(*accent, 255))
    else:
        draw.ellipse((cx-110, 260, cx+110, 490), fill=(60, 43, 29, 255))
        draw.rounded_rectangle((cx-160, 455, cx+160, 790), radius=85, fill=(44, 47, 39, 255))
        draw.polygon([(cx-75, 475), (cx, 590), (cx+75, 475)], fill=(*accent, 210))
    # Soft halo behind the figure
    draw.ellipse((cx-230, 160, cx+230, 620), outline=(*accent, 110), width=4)

def _png(im):
    out = BytesIO()
    im.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out

def role_card(role):
    top, bottom, accent = PALETTES.get(role, PALETTES["civilian"])
    im = _gradient(top, bottom).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    _ornaments(draw, accent)
    _silhouette(draw, role, accent)
    name, subtitle, hint, symbol = ROLE_DATA[role]
    draw.rounded_rectangle((58, 825, W-58, 1115), radius=36, fill=(4, 7, 16, 205), outline=(*accent, 180), width=3)
    draw.text((W//2, 865), "SIZNING ROLINGIZ", font=_font(31, True), fill=(*accent, 255), anchor="mm")
    draw.text((W//2, 940), name, font=_font(64, True), fill=(255,255,255,255), anchor="mm", stroke_width=1, stroke_fill=(*accent, 150))
    draw.text((W//2, 1000), subtitle, font=_font(23, True), fill=(*accent, 255), anchor="mm")
    draw.text((W//2, 1060), hint, font=_font(22), fill=(235,235,240,255), anchor="mm")
    draw.text((W//2, 700), symbol, font=_font(100, True), fill=(*accent, 225), anchor="mm")
    return _png(im)

def phase_card(phase):
    key = "night" if phase == "night" else "day"
    top, bottom, accent = PALETTES[key]
    im = _gradient(top, bottom).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    _ornaments(draw, accent)
    cx, cy = W//2, 430
    if key == "night":
        draw.ellipse((cx-150, cy-150, cx+150, cy+150), fill=(*accent, 245))
        draw.ellipse((cx-75, cy-190, cx+205, cy+85), fill=(*bottom, 255))
        for x, y, r in [(170,220,7),(700,170,9),(760,450,6),(190,530,5),(590,620,7)]:
            draw.ellipse((x-r,y-r,x+r,y+r), fill=(255,255,255,220))
        title, sub = "TUN", "SHAHAR UYQUDA..."
    else:
        draw.ellipse((cx-145, cy-145, cx+145, cy+145), fill=(*accent, 255))
        for a in range(0, 360, 45):
            x1 = cx + math.cos(math.radians(a))*190
            y1 = cy + math.sin(math.radians(a))*190
            x2 = cx + math.cos(math.radians(a))*245
            y2 = cy + math.sin(math.radians(a))*245
            draw.line((x1,y1,x2,y2), fill=(*accent,220), width=13)
        title, sub = "KUNDUZ", "SHAHAR UYG'ONDI!"
    draw.text((cx, 820), title, font=_font(105, True), fill=(255,255,255,255), anchor="mm")
    draw.text((cx, 930), sub, font=_font(32, True), fill=(*accent,255), anchor="mm")
    draw.text((cx, 1080), "ABE VAYN  •  MAFIA", font=_font(28, True), fill=(*accent,255), anchor="mm")
    return _png(im)

def welcome_card():
    top, bottom, accent = PALETTES["welcome"]
    im = _gradient(top, bottom).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")
    _ornaments(draw, accent)
    cx = W//2
    draw.ellipse((cx-190, 200, cx+190, 580), fill=(4,6,13,100), outline=(*accent,180), width=5)
    draw.polygon([(cx-240,520),(cx-150,360),(cx+150,360),(cx+240,520)], fill=(10,8,16,255))
    draw.text((cx, 670), "ABE VAYN", font=_font(86, True), fill=(255,255,255,255), anchor="mm")
    draw.text((cx, 780), "MAFIA", font=_font(112, True), fill=(*accent,255), anchor="mm")
    draw.text((cx, 920), "ISHONCH  •  AQL  •  STRATEGIYA", font=_font(27, True), fill=(235,235,240,255), anchor="mm")
    return _png(im)
