# 花蓮縣四維高級中學 招生 Reels「預覽版」（60 秒、9:16）
# 數據卡＋學程圖示＋AI 旁白＋字幕；需要實拍的鏡頭先放佔位框，素材到了再替換。
# 用法：python3 make.py            → 合成旁白（有快取）並輸出 siwei_preview.mp4、subtitles.srt
#       python3 make.py preview DIR → 只輸出每鏡靜態預覽圖
import hashlib, json, math, os, random, subprocess, sys, wave
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
W, H, S, FPS = 1080, 1920, 2, 30
DUR, SHOT = 60.0, 7.5
N = int(DUR * FPS)
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
VOICE = "zh-TW-HsiaoChenNeural"
SR = 48000

# 校徽取色
RED = (196, 38, 40); GREEN = (0, 104, 56); GOLD = (240, 170, 30)
INK = (45, 40, 40); SOFT = (120, 110, 105); WHITE = (255, 255, 255); FB = (24, 119, 242)

# ---------------- 旁白／字幕 ----------------
# 每鏡兩段；None 表示該鏡不配旁白（只出字幕）
NARR = [
    ["國中畢業，下一步要去哪裡？", "選擇四維，大有可為！"],
    ["綜合高中，高一先探索，", "高二再選適合自己的學程。"],
    ["商業、工業、觀光餐飲，三大類七個學程，", "動手學、考證照！"],
    ["想拚升學？", "普通科，一路陪你衝刺繁星。"],
    ["115 年繁星推薦，大學 19 人、科大 13 人，", "台大、政大、臺科大都有學長姐！"],
    ["在四維，老師不只教課本，", "更陪你走過每一個難關。"],
    None,
    ["早鳥專案，12 月 1 日開跑！", "追蹤臉書「四維大小事」，三年後換你發光！"],
]
SHOT7_SUB = "（此處放學生受訪原音）"
TTS_DIR = os.path.join(OUT, "_tts")


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p]).decode())


def tts(text, rate):
    os.makedirs(TTS_DIR, exist_ok=True)
    key = hashlib.md5(f"{VOICE}|{rate}|{text}".encode()).hexdigest()[:12]
    p = os.path.join(TTS_DIR, key + ".mp3")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        cmd = ["edge-tts", "--voice", VOICE, f"--rate={rate:+d}%", "--text", text, "--write-media", p]
        if os.environ.get("HTTPS_PROXY"):
            cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]
        subprocess.run(cmd, check=True, capture_output=True)
    return p


def build_narration():
    segs, clips = [], []
    for i, parts in enumerate(NARR):
        t0 = i * SHOT + 0.3
        if parts is None:
            segs.append((t0, i * SHOT + 7.2, SHOT7_SUB)); continue
        rate, total = -5, 99
        while total > 6.9 and rate < 40:
            rate += 5
            info = [(tts(x, rate), x) for x in parts]
            info = [(p, dur(p), x) for p, x in info]
            total = sum(d for _, d, _ in info) + 0.15
        t = t0
        for p, d, x in info:
            segs.append((t, t + d, x)); clips.append((t, p)); t += d + 0.15
        print(f"shot {i+1}: {total:.2f}s rate +{rate}%", flush=True)
    inputs, filt = [], []
    for k, (t, p) in enumerate(clips):
        inputs += ["-i", p]
        filt.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,adelay={int(t*1000)}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(clips))) +
                f"amix=inputs={len(clips)}:normalize=0,apad,atrim=0:{DUR}[o]")
    nar = os.path.join(OUT, "narration.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[o]", "-ar", str(SR), "-ac", "1", nar], check=True)
    json.dump(segs, open(os.path.join(OUT, "timings.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return segs


# ---------------- 繪圖工具 ----------------
_fc = {}
def F(sz, scale=S):
    k = max(4, int(sz * scale))
    if k not in _fc: _fc[k] = ImageFont.truetype(FONT, k)
    return _fc[k]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def eob(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def A(col, a=1.0): return tuple(col[:3]) + (int(clamp(a) * 255),)


class C:
    def __init__(s):
        s.im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); s.d = ImageDraw.Draw(s.im, "RGBA")
    def P(s, *v): return [x * S for x in v]
    def circle(s, x, y, r, fill=None, outline=None, w=0):
        s.d.ellipse(s.P(x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=int(w * S))
    def rect(s, x0, y0, x1, y1, fill=None, outline=None, w=0, r=0):
        s.d.rounded_rectangle(s.P(x0, y0, x1, y1), radius=int(r * S), fill=fill, outline=outline, width=int(w * S))
    def line(s, pts, fill, w):
        s.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(w * S), joint="curve")
        for x, y in (pts[0], pts[-1]): s.circle(x, y, w / 2, fill=fill)
    def poly(s, pts, fill): s.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)
    def text(s, x, y, t, sz, fill=INK, anchor="mm", stroke=0, sf=None):
        s.d.text((x * S, y * S), t, font=F(sz), fill=fill, anchor=anchor, stroke_width=int(stroke * S), stroke_fill=sf)
    def paste(s, img, x, y, h, alpha=1.0):
        w = img.width * h / img.height
        im = img.resize((max(1, int(w * S)), max(1, int(h * S))), Image.LANCZOS)
        if alpha < 1:
            a = np.asarray(im).copy(); a[..., 3] = (a[..., 3] * alpha).astype(np.uint8); im = Image.fromarray(a)
        s.im.alpha_composite(im, (int((x - w / 2) * S), int((y - h / 2) * S)))


LOGO = Image.open(os.path.join(OUT, "assets", "logo_src.png")).convert("RGBA")
GIRL = Image.open(os.path.join(OUT, "assets", "girl.png")).convert("RGBA")
BOY = Image.open(os.path.join(OUT, "assets", "boy.png")).convert("RGBA")
ADMIT_URL = "https://www.swsh.hlc.edu.tw/ischool/publish_page/652/"


def make_qr():
    import qrcode
    q = qrcode.QRCode(border=2, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(ADMIT_URL); q.make(fit=True)
    return q.make_image(fill_color="black", back_color="white").convert("RGBA")

QR = make_qr()


def mascot(c, img, x, y, h, lt, t0, phase=0.0):
    """Q 版學生：彈出＋輕微上下擺動"""
    q = eob((lt - t0) / 0.45)
    if q <= 0: return
    bob = math.sin(lt * 3.2 + phase) * 7
    c.paste(img, x, y + bob + (1 - q) * 60, h * q + 1)


def pill(c, x, y, txt, sz, bg, fg=WHITE, a=1.0, pad=28):
    w = F(sz).getlength(txt) / S
    c.rect(x - w / 2 - pad, y - sz * 0.8, x + w / 2 + pad, y + sz * 0.8, fill=A(bg, a), r=sz * 0.8)
    c.text(x, y, txt, sz, A(fg, a))


def star(c, x, y, r, col, a=1.0, rot=0):
    pts = []
    for k in range(10):
        ang = math.radians(-90 + rot + k * 36); rr = r if k % 2 == 0 else r * 0.45
        pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
    c.poly(pts, A(col, a))


def heart(c, x, y, r, col, a=1.0):
    c.circle(x - r * 0.5, y - r * 0.2, r * 0.55, fill=A(col, a))
    c.circle(x + r * 0.5, y - r * 0.2, r * 0.55, fill=A(col, a))
    c.poly([(x - r * 1.03, y - r * 0.05), (x + r * 1.03, y - r * 0.05), (x, y + r * 1.05)], A(col, a))


def placeholder(c, x0, y0, x1, y1, label, lt, a=1.0):
    """實拍佔位框：虛線框＋攝影機圖示＋說明"""
    c.rect(x0, y0, x1, y1, fill=A((235, 228, 220), 0.85 * a), r=36)
    # 虛線邊框
    per = 2 * ((x1 - x0) + (y1 - y0)); n = int(per / 34); off = (lt * 40) % 34
    def pt(d):
        d %= per
        if d < x1 - x0: return (x0 + d, y0)
        d -= x1 - x0
        if d < y1 - y0: return (x1, y0 + d)
        d -= y1 - y0
        if d < x1 - x0: return (x1 - d, y1)
        return (x0, y1 - (d - (x1 - x0)))
    for k in range(n):
        p0, p1 = pt(k * 34 + off), pt(k * 34 + off + 16)
        if abs(p0[0] - p1[0]) < 20 and abs(p0[1] - p1[1]) < 20: c.line([p0, p1], A(SOFT, 0.6 * a), 4)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 30
    c.rect(cx - 70, cy - 42, cx + 40, cy + 42, fill=A(SOFT, 0.55 * a), r=12)
    c.poly([(cx + 44, cy), (cx + 82, cy - 30), (cx + 82, cy + 30)], A(SOFT, 0.55 * a))
    c.circle(cx - 15, cy, 22, fill=A((235, 228, 220), a))
    if int(lt * 2) % 2 == 0: c.circle(cx - 52, cy - 26, 7, fill=A(RED, 0.9 * a))
    c.text(cx, cy + 95, label, 34, A(SOFT, a))


# ---------------- 各鏡 ----------------
def shot1(c, lt):
    p = eob(lt / 0.9)
    for k in range(3):
        rr = 230 + 60 * k + 30 * math.sin(lt * 2 + k)
        c.circle(540, 640, rr * p, outline=A([RED, GREEN, GOLD][k], 0.18), w=6)
    c.paste(LOGO, 540, 640, 330 * p + 1, alpha=clamp(lt * 3))
    mascot(c, GIRL, 165, 670, 380, lt, 1.0, 0.0)
    mascot(c, BOY, 915, 670, 380, lt, 1.3, 1.5)
    if lt > 0.8:
        q = ease((lt - 0.8) / 0.6)
        c.text(540, 900 + (1 - q) * 40, "花蓮縣四維高級中學", 70, A(RED, q))
        c.text(540, 975 + (1 - q) * 40, "SI WEI SENIOR HIGH SCHOOL", 30, A(GREEN, q))
    if lt > 3.3:
        q = eob((lt - 3.3) / 0.45)
        pill(c, 540, 1090, "選擇四維，大有可為", 58 * q + 1, GREEN)
        for k in range(6):
            ang = k * 60 + lt * 40
            star(c, 540 + math.cos(math.radians(ang)) * 330, 1090 + math.sin(math.radians(ang)) * 70,
                 14 * q, GOLD, q, rot=lt * 90)
    c.text(540, 1210, "（正式版：以校門全景實拍為背景）", 26, A(SOFT, clamp((lt - 1) * 2)))
    return (540, 800)


def shot2(c, lt):
    placeholder(c, 110, 420, 970, 880, "實拍：高一探索課、分組討論", lt, clamp(lt * 3))
    pill(c, 540, 420, "綜合高中", 40, RED, a=clamp(lt * 3))
    nodes = [(270, 1060, "高一", "先探索", GREEN, 0.5), (810, 1060, "高二", "選學程", RED, 3.6)]
    for x, y, a_, b_, col, t0 in nodes:
        if lt < t0: continue
        q = eob((lt - t0) / 0.4)
        c.circle(x, y, 115 * q, fill=A(col, 0.95))
        c.text(x, y - 28, a_, 46 * q + 1, A(WHITE))
        c.text(x, y + 32, b_, 36 * q + 1, A(WHITE))
    if lt > 2.0:
        q = ease((lt - 2.0) / 1.4)
        xe = 400 + (680 - 400) * q
        c.line([(400, 1060), (xe, 1060)], A(GOLD), 12)
        if q > 0.95: c.poly([(680, 1035), (680, 1085), (715, 1060)], A(GOLD))
        for k in range(3):
            if q > (k + 1) / 4: star(c, 400 + (680 - 400) * (k + 1) / 4, 1010, 14, GOLD, rot=lt * 60)
    return (540, 760)


PROG = [("商", "商業類", ["資料處理", "電子商務", "應用日語"], RED, 0.3),
        ("工", "工業類", ["電機技術", "電子技術", "資訊技術"], (30, 90, 170), 1.4),
        ("餐", "觀光餐飲", ["觀光餐飲學程"], GREEN, 2.5)]

def shot3(c, lt):
    al = clamp(lt * 3)
    c.text(540, 430, "綜合高中", 40, A(SOFT, al))
    c.text(540, 490, "3 大類・7 個學程", 60, A(RED, al))
    for i, (ch, name, items, col, t0) in enumerate(PROG):
        if lt < t0: continue
        k = ease((lt - t0) / 0.45); y = 560 + i * 205; dx = (1 - k) * 600
        c.rect(70 + dx, y, 800 + dx, y + 180, fill=A(WHITE, 0.95 * k), outline=A(col, k), w=5, r=34)
        c.circle(150 + dx, y + 90, 58, fill=A(col, k))
        c.text(150 + dx, y + 90, ch, 56, A(WHITE, k))
        c.text(235 + dx, y + 52, name, 44, A(col, k), anchor="lm")
        x = 235 + dx
        for j, it in enumerate(items):
            q = eob((lt - t0 - 0.35 - j * 0.18) / 0.3)
            if q <= 0: continue
            w = F(30).getlength(it) / S + 36
            c.rect(x, y + 102, x + w, y + 152, fill=A(col, 0.14 * q), outline=A(col, 0.7 * q), w=2, r=25)
            c.text(x + w / 2, y + 127, it, 30 * q + 1, A(INK, q))
            x += w + 14
    mascot(c, GIRL, 925, 890, 400, lt, 0.6)
    if lt > 4.3:
        q = eob((lt - 4.3) / 0.4)
        pill(c, 540, 1195, "動手學・考證照", 46 * q + 1, GOLD, fg=(80, 40, 0))
    return (540, 820)


def shot4(c, lt):
    placeholder(c, 90, 420, 710, 860, "實拍：普通科上課、自習", lt, clamp(lt * 3))
    pill(c, 400, 420, "普通科", 40, GREEN, a=clamp(lt * 3))
    mascot(c, BOY, 860, 650, 420, lt, 0.5)
    steps = [(220, "高一", "打基礎"), (540, "高二", "拚成績"), (860, "高三", "衝繁星")]
    pr = ease((lt - 0.8) / 4.2)
    c.line([(220, 1060), (860, 1060)], A(SOFT, 0.3), 10)
    if pr > 0: c.line([(220, 1060), (220 + 640 * pr, 1060)], A(GREEN), 10)
    for i, (x, a_, b_) in enumerate(steps):
        on = pr >= i / 2 - 1e-3
        q = eob((pr - i / 2) * 6) if on else 0
        if i == 2 and on:
            star(c, x, 1060, 80 + 50 * q, GOLD, rot=lt * 30)
            c.text(x, 1068, a_, 34, A((80, 40, 0)))
        else:
            c.circle(x, 1060, 52 + 10 * q, fill=A(GREEN if on else (200, 195, 190)))
            c.text(x, 1060, a_, 32, A(WHITE))
        c.text(x, 1170, b_, 38, A(GREEN if on else SOFT))
    return (540, 760)


def shot5(c, lt):
    al = clamp(lt * 3)
    c.text(540, 440, "115 年繁星推薦", 64, A(RED, al))
    cards = [(300, "大學繁星", 19, "含公立大學 8 人", RED), (780, "科大繁星", 13, "錄取科技大學", GREEN)]
    for i, (x, t_, n, sub, col) in enumerate(cards):
        k = eob((lt - 0.3 - i * 0.3) / 0.45)
        if k <= 0: continue
        c.rect(x - 215, 530, x + 215, 900, fill=A(WHITE, 0.96), outline=A(col, 1), w=6, r=40)
        c.rect(x - 215, 530, x + 215, 610, fill=A(col, 1), r=40)
        c.rect(x - 215, 580, x + 215, 610, fill=A(col, 1))
        c.text(x, 572, t_, 40, A(WHITE))
        v = int(round(n * ease((lt - 0.6 - i * 0.3) / 1.6)))
        c.text(x - 20, 745, str(v), 170 * k + 1, A(col))
        c.text(x + 120, 790, "人", 46, A(col))
        c.text(x, 860, sub, 30, A(SOFT))
    for j, nm in enumerate(["國立臺灣大學", "國立政治大學", "國立臺灣科技大學"]):
        q = eob((lt - 3.7 - j * 0.35) / 0.35)
        if q > 0: pill(c, 540, 975 + j * 82, nm, 38 * q + 1, GOLD, fg=(80, 40, 0))
    c.text(540, 1222, "資料來源：花蓮縣四維高級中學官網「歷年榜單」（2026-11-25 查詢）", 22, A(SOFT, al))
    return (540, 800)


def shot6(c, lt):
    placeholder(c, 110, 420, 970, 880, "實拍：老師課後指導、和學生聊天", lt, clamp(lt * 3))
    q = eob((lt - 0.6) / 0.5); beat = 1 + 0.08 * max(0, math.sin(lt * 7))
    if q > 0: heart(c, 540, 1000, 62 * q * beat, RED)
    if lt > 1.2:
        k = ease((lt - 1.2) / 0.5)
        c.text(540, 1120, "溫馨關懷・陪伴成長", 52, A(GREEN, k))
        c.text(540, 1195, "做好事、說好話、存好心", 32, A(SOFT, k))
    return (540, 780)


def shot7(c, lt):
    placeholder(c, 110, 420, 970, 1060, "實拍：學生受訪（用自己的話說一句）", lt, clamp(lt * 3))
    k = eob((lt - 0.8) / 0.5)
    if k > 0:
        c.rect(150, 1100, 930, 1230, fill=A(WHITE, 0.97), outline=A(RED, 1), w=5, r=40)
        c.poly([(260, 1100), (320, 1100), (270, 1060)], A(RED, 1))
        c.text(540, 1165, "「我最喜歡四維的……」", 44 * k + 1, A(RED))
    c.text(160, 470, "“", 120, A(RED, 0.5 * clamp(lt * 3)), anchor="lm")
    return (540, 800)


def shot8(c, lt):
    p = eob(lt / 0.7)
    if lt > 4.6:
        for k in range(14):
            ang = math.radians(k * 360 / 14 + lt * 30); d = 170 + 140 * ease((lt - 4.6) / 1.2)
            star(c, 540 + math.cos(ang) * d, 560 + math.sin(ang) * d, 16, [GOLD, RED, GREEN][k % 3],
                 clamp(1.5 - (lt - 4.6) / 1.5), rot=lt * 120)
    c.paste(LOGO, 540, 560, 230 * p + 1, alpha=clamp(lt * 3))
    mascot(c, GIRL, 185, 580, 330, lt, 0.3, 0.0)
    mascot(c, BOY, 895, 580, 330, lt, 0.5, 1.5)
    if lt > 0.5:
        q = eob((lt - 0.5) / 0.4)
        pill(c, 540, 775, "免試早鳥專案", 50 * q + 1, RED)
        c.text(540, 850, "登記期間：115/12/1 – 116/3/31", 34, A(INK, q))
    if lt > 1.8:
        q = ease((lt - 1.8) / 0.4); y = 890
        c.rect(150, y, 930, y + 120, fill=A(WHITE, 0.97 * q), outline=A(FB, q), w=4, r=30)
        c.circle(230, y + 60, 40, fill=A(FB, q)); c.text(232, y + 64, "f", 54, A(WHITE, q))
        c.text(295, y + 40, "臉書：四維大小事", 38, A(INK, q), anchor="lm")
        c.text(295, y + 88, "facebook.com/swshstory", 28, A(FB, q), anchor="lm")
    if lt > 2.6:
        q = ease((lt - 2.6) / 0.4)
        c.rect(150, 1035, 930, 1245, fill=A(WHITE, 0.97 * q), outline=A(RED, q), w=4, r=30)
        c.paste(QR, 268, 1140, 180, alpha=q)
        c.text(385, 1090, "掃描看招生資訊", 38, A(RED, q), anchor="lm")
        c.text(385, 1142, "預約校園參訪・早鳥登記", 30, A(INK, q), anchor="lm")
        c.text(385, 1192, "諮詢：(03)856-1455 #114、118", 28, A(SOFT, q), anchor="lm")
    return (540, 820)


SHOTS = [shot1, shot2, shot3, shot4, shot5, shot6, shot7, shot8]


# ---------------- 背景、字幕、合成 ----------------
def make_bg():
    y = np.linspace(0, 1, H)[:, None, None]
    top = np.array([255, 251, 243]); bot = np.array([255, 238, 226])
    g = np.broadcast_to(top + (bot - top) * y, (H, W, 3))
    img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.ellipse([-300, -250, 500, 550], fill=(0, 104, 56, 18))
    d.ellipse([650, 1350, 1450, 2150], fill=(196, 38, 40, 16))
    d.ellipse([780, -120, 1250, 350], fill=(240, 170, 30, 22))
    img.alpha_composite(ov)
    return img

BG = None
SPARK = [(random.Random(i).uniform(0, W), random.Random(i + 50).uniform(0, H),
          random.Random(i + 9).uniform(3, 7), random.Random(i + 4).uniform(12, 35)) for i in range(30)]
SEGS = []


def wrap(txt, n=15):
    if len(txt) <= n: return [txt]
    mid = len(txt) / 2; PUN = "，。、；：！？"
    cands = [i + 1 for i, ch in enumerate(txt[:-1]) if ch in PUN and abs(i + 1 - mid) < len(txt) * 0.3]
    k = min(cands, key=lambda i: abs(i - mid)) if cands else int(math.ceil(mid))
    return [txt[:k], txt[k:]]


def render(fi):
    global BG
    if BG is None: BG = make_bg()
    t = fi / FPS; si = min(7, int(t / SHOT)); lt = t - si * SHOT
    frame = BG.copy(); d = ImageDraw.Draw(frame, "RGBA")
    for x, y, r, sp in SPARK:
        yy = (y - t * sp) % H
        d.ellipse([x - r, yy - r, x + r, yy + r], fill=(240, 170, 30, 60))
    c = C(); fx, fy = SHOTS[si](c, lt)
    z = 1 + 0.06 * ease(lt / SHOT); cw, ch = W * S / z, H * S / z
    x0 = clamp(fx * S - cw / 2, 0, W * S - cw); y0 = clamp(fy * S - ch / 2, 0, H * S - ch)
    layer = c.im.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    fade = clamp(min(lt / 0.4 if si else 1, (SHOT - lt) / 0.4 if si < 7 else 1))
    if fade < 1:
        a = np.asarray(layer).copy(); a[..., 3] = (a[..., 3] * fade).astype(np.uint8); layer = Image.fromarray(a)
    frame.alpha_composite(layer); d = ImageDraw.Draw(frame, "RGBA")
    # 上方：小校徽＋校名（第 1 鏡除外）＋預覽標記
    if si > 0:
        sm = LOGO.resize((int(LOGO.width * 58 / LOGO.height), 58), Image.LANCZOS)
        nm = "花蓮縣四維高級中學"; tw = F(30, 1).getlength(nm)
        x = int(540 - (sm.width + 12 + tw) / 2)
        frame.alpha_composite(sm, (x, 262)); d.text((x + sm.width + 12, 291), nm, font=F(30, 1), fill=A(RED), anchor="lm")
    d.rounded_rectangle([395, 334, 685, 370], radius=18, fill=(255, 140, 0, 40), outline=(230, 120, 0, 160), width=2)
    d.text((540, 352), "預覽版・實拍畫面待替換", font=F(20, 1), fill=(190, 95, 0, 255), anchor="mm")
    # 字幕
    for st, en, txt in SEGS:
        if st - 0.1 <= t < en + 0.2:
            lines = wrap(txt); fs = F(54, 1); lh = 74; yb = 1330
            mw = max(fs.getlength(l) for l in lines)
            d.rounded_rectangle([540 - mw / 2 - 30, yb - 20, 540 + mw / 2 + 30, yb + lh * len(lines) + 8],
                                radius=24, fill=(120, 20, 25, 205))
            for k, l in enumerate(lines):
                d.text((540, yb + k * lh + lh / 2 - 6), l, font=fs, fill=WHITE, anchor="mm")
            break
    g = clamp(min(t / 0.5, (DUR - t) / 0.9))
    if g < 1: frame = Image.blend(Image.new("RGBA", (W, H), (255, 255, 255, 255)), frame, g)
    return frame.convert("RGB").tobytes()


def init_worker(segs):
    global SEGS; SEGS = segs


# ---------------- 配樂（程式合成：明亮流行感，C–G–Am–F） ----------------
def synth_music(nar_path):
    n = int(DUR * SR); out = np.zeros(n); rs = np.random.RandomState(3)
    def add(t0, sig, g):
        i = int(t0 * SR)
        if i >= n: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i] * g
    def env(d, a, dec):
        tt = np.arange(int(d * SR)) / SR; return np.minimum(1, tt / a) * np.exp(-tt * dec), tt
    beat = 60 / 104
    ch = [[261.63, 329.63, 392.0], [196.0, 246.94, 293.66], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63]]
    for b in range(int(DUR / beat)):
        tb = b * beat; c3 = ch[(b // 4) % 4]
        e, tt = env(0.3, 0.002, 10); add(tb, np.sin(2 * np.pi * np.cumsum(50 + 70 * np.exp(-tt * 30)) / SR) * e, 0.45)
        if b % 2:
            e, tt = env(0.15, 0.002, 22); add(tb, rs.randn(len(tt)) * e, 0.10)
        e, tt = env(0.04, 0.001, 80); add(tb + beat / 2, rs.randn(len(tt)) * e, 0.035)
        e, tt = env(beat, 0.01, 3); add(tb, np.sin(2 * np.pi * c3[0] / 2 * tt) * e, 0.18)
        for k in range(4):
            f = c3[k % 3] * (2 if k == 3 else 1)
            e, tt = env(0.3, 0.003, 9)
            add(tb + k * beat / 4, (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 3 * f * tt)) * e, 0.05)
        if b % 4 == 0:
            e, tt = env(beat * 4, 0.4, 0.5); add(tb, sum(np.sin(2 * np.pi * f * tt) for f in c3) * e, 0.035)
    e, tt = env(3, 0.01, 1.3)
    add(57.0, sum(np.sin(2 * np.pi * f * tt) for f in [523.25, 659.25, 783.99, 1046.5]) * e, 0.08)
    t_all = np.arange(n) / SR
    out *= np.clip((DUR - t_all) / 2.0, 0, 1) * np.clip(t_all / 0.3, 0, 1)
    out /= np.max(np.abs(out)) + 1e-9
    with wave.open(nar_path) as w:
        v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
    v = np.pad(v, (0, max(0, n - len(v))))[:n]
    duck = np.clip(np.convolve(np.abs(v), np.ones(4800) / 4800, "same") / 0.02, 0, 1)
    duck = np.convolve(duck, np.ones(9600) / 9600, "same")
    mix = out * 0.4 * (1 - 0.72 * duck) + v / (np.max(np.abs(v)) + 1e-9) * 0.9
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.9
    p = os.path.join(OUT, "mix.wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.stack([mix, mix], 1) * 32767).astype(np.int16).tobytes())
    return p


def write_srt(segs):
    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    with open(os.path.join(OUT, "subtitles.srt"), "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(segs, 1): f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "preview":
        tj = os.path.join(OUT, "timings.json")
        init_worker(json.load(open(tj, encoding="utf-8")) if os.path.exists(tj) else [])
        for i in range(8):
            Image.frombytes("RGB", (W, H), render(int((i * SHOT + 6.0) * FPS))).save(os.path.join(sys.argv[2], f"s{i+1}.png"))
        sys.exit()
    segs = build_narration(); write_srt(segs)
    wav = synth_music(os.path.join(OUT, "narration.wav"))
    mp4 = os.path.join(OUT, "siwei_preview.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264",
                           "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", "-t", str(DUR), mp4], stdin=subprocess.PIPE)
    with Pool(4, initializer=init_worker, initargs=(segs,)) as pool:
        for k, b in enumerate(pool.imap(render, range(N), chunksize=6)):
            ff.stdin.write(b)
            if k % 300 == 0: print(f"frame {k}/{N}", flush=True)
    ff.stdin.close(); ff.wait(); print("done", mp4)
