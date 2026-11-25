# 番茄鐘為什麼能提升效率？— 60 秒 Reels 直式教學短片（程式繪製資訊圖表動畫）
# 用法：python3 render.py  → 輸出 pomodoro_reels.mp4、music.wav、subtitles.srt
import math, random, subprocess, wave, os, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
W, H, S, FPS = 1080, 1920, 2, 30
DUR = 60.0
N = int(DUR * FPS)
SHOT = 7.5
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

RED = (255, 75, 62); GREEN = (46, 230, 166); BLUE = (61, 123, 255)
WHITE = (255, 255, 255); GREY = (160, 172, 205); YEL = (255, 214, 80); CYAN = (90, 220, 255)

# ---------------- 旁白／字幕（每鏡兩段） ----------------
NARR = [
    ["只用一分鐘，看懂背後原理。", "被打斷一次，你可能要二十多分鐘，才找回專注！"],
    ["想像你正在讀書：手機一亮、訊息一跳，", "注意力就像水管被戳了洞，一直漏。"],
    ["心理學把這叫做「警覺性遞減」：", "長時間做同一件事，專注表現會慢慢往下掉。"],
    ["問題來了：硬撐不休息，越讀越累；", "可是一休息，又停不下來。到底該怎麼辦？"],
    ["2011 年有一項實驗發現：在長時間任務中，", "穿插短暫的轉換，表現反而比較不會下滑。"],
    ["番茄鐘就是解法：專心 25 分鐘，休息 5 分鐘；", "每做完四輪，再好好休息久一點。"],
    ["原理有三個：有時限，比較好開始；", "計時中不分心；定時休息，減少疲勞。"],
    ["重點：專注要分段，休息要規律。", "想一想：25 分鐘，真的最適合你嗎？"],
]
CHIP = ["震撼事實", "情境", "情境", "衝突", "衝突", "解法", "解法", "總結＋思考"]
SRC = [None, None, "資料來源：Mackworth (1948)", None,
       "資料來源：Ariga & Lleras, Cognition (2011)", "番茄工作法：Francesco Cirillo",
       "資料來源：Biwer et al., Br J Educ Psychol (2023)", None]


def sub_segments():
    segs = []
    for i, parts in enumerate(NARR):
        st, en = i * SHOT + 0.25, i * SHOT + 7.25
        lens = [len(p.replace(" ", "")) for p in parts]
        tot = sum(lens); t = st
        for p, l in zip(parts, lens):
            d = (en - st) * l / tot
            segs.append((t, t + d, p)); t += d
    return segs

SEGS = sub_segments()
_TJ = os.path.join(OUT, "timings.json")
if os.path.exists(_TJ):  # 有旁白時，字幕對齊實際語音時間
    import json
    SEGS = [(d["start"], d["end"], d["text"]) for d in json.load(open(_TJ, encoding="utf-8"))]

# ---------------- 繪圖工具 ----------------
_fc = {}
def F(sz, scale=S):
    k = max(4, int(sz * scale))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONT, k)
    return _fc[k]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def eob(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def A(col, a): return tuple(col[:3]) + (int(clamp(a) * 255),)
def lerp(a, b, t): return a + (b - a) * t


class C:
    def __init__(s):
        s.im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        s.d = ImageDraw.Draw(s.im, "RGBA")
    def P(s, *v): return [x * S for x in v]
    def circle(s, x, y, r, fill=None, outline=None, w=0):
        s.d.ellipse(s.P(x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=int(w * S))
    def oval(s, x0, y0, x1, y1, fill): s.d.ellipse(s.P(x0, y0, x1, y1), fill=fill)
    def rect(s, x0, y0, x1, y1, fill=None, outline=None, w=0, r=0):
        s.d.rounded_rectangle(s.P(x0, y0, x1, y1), radius=int(r * S), fill=fill, outline=outline, width=int(w * S))
    def line(s, pts, fill, w):
        s.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(w * S), joint="curve")
        for x, y in (pts[0], pts[-1]):
            s.circle(x, y, w / 2, fill=fill)
    def arc(s, x, y, r, a0, a1, fill, w):
        s.d.arc(s.P(x - r, y - r, x + r, y + r), a0, a1, fill=fill, width=int(w * S))
    def poly(s, pts, fill): s.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)
    def text(s, x, y, t, sz, fill=WHITE, anchor="mm", stroke=0, sf=None):
        s.d.text((x * S, y * S), t, font=F(sz), fill=fill, anchor=anchor,
                 stroke_width=int(stroke * S), stroke_fill=sf)


def tomato(c, x, y, r, ang=None, disp=None, alpha=1.0, grey=False):
    body = (120, 130, 150) if grey else RED
    light = (150, 160, 180) if grey else (255, 110, 92)
    c.circle(x + r * 0.05, y + r * 0.12, r * 1.02, fill=(0, 0, 20, int(80 * alpha)))
    c.circle(x, y, r, fill=A(body, alpha))
    c.circle(x - r * 0.12, y - r * 0.12, r * 0.84, fill=A(light, alpha))
    c.circle(x - r * 0.05, y - r * 0.05, r * 0.86, fill=A(body, alpha * 0.55))
    c.oval(x - r * 0.62, y - r * 0.72, x - r * 0.1, y - r * 0.4, fill=(255, 255, 255, int(130 * alpha)))
    # 葉子（星形）
    cx, cy = x, y - r * 0.88
    pts = []
    for k in range(10):
        a = math.radians(-90 + k * 36)
        rr = r * (0.42 if k % 2 == 0 else 0.13)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.55))
    c.poly(pts, A((40, 200, 115) if not grey else (110, 140, 125), alpha))
    c.rect(x - r * 0.05, y - r * 1.2, x + r * 0.05, y - r * 0.88, fill=A((30, 150, 90), alpha), r=r * 0.03)
    # 錶盤
    dx, dy, dr = x, y + r * 0.1, r * 0.52
    c.circle(dx, dy, dr, fill=(255, 250, 245, int(240 * alpha)))
    if disp is not None:
        c.text(dx, dy, disp, dr * 0.85, fill=A((215, 45, 35), alpha))
    else:
        for k in range(12):
            a = math.radians(k * 30)
            c.line([(dx + math.cos(a) * dr * 0.78, dy + math.sin(a) * dr * 0.78),
                    (dx + math.cos(a) * dr * 0.9, dy + math.sin(a) * dr * 0.9)], A((200, 80, 70), alpha), max(1.5, r * 0.025))
        a = math.radians(-90 + (ang or 0))
        c.line([(dx, dy), (dx + math.cos(a) * dr * 0.72, dy + math.sin(a) * dr * 0.72)], A((220, 40, 30), alpha), max(2, r * 0.05))
        c.circle(dx, dy, r * 0.06, fill=A((220, 40, 30), alpha))


def glow_line(c, pts, col, w, a=1.0):
    c.line(pts, A(col, 0.18 * a), w * 3.2)
    c.line(pts, A(col, 0.35 * a), w * 1.8)
    c.line(pts, A(col, a), w)


def axes(c, x0, y0, x1, y1, alpha):
    c.line([(x0, y0), (x0, y1), (x1, y1)], A(WHITE, 0.85 * alpha), 5)
    c.poly([(x0 - 14, y0 + 8), (x0 + 14, y0 + 8), (x0, y0 - 18)], A(WHITE, 0.85 * alpha))
    c.poly([(x1 - 8, y1 - 14), (x1 - 8, y1 + 14), (x1 + 18, y1)], A(WHITE, 0.85 * alpha))
    for k in range(1, 5):
        yy = y1 - (y1 - y0) * k / 5
        c.line([(x0 + 10, yy), (x1 - 10, yy)], A(WHITE, 0.08 * alpha), 2)
    c.text(x0 + 10, y0 - 40, "專注表現", 34, A(WHITE, alpha), anchor="lm")
    c.text(x1, y1 + 46, "時間 →", 34, A(WHITE, alpha), anchor="rm")


def pill(c, x, y, txt, sz, bg, fg=WHITE, a=1.0, pad=26):
    w = F(sz).getlength(txt) / S
    c.rect(x - w / 2 - pad, y - sz * 0.78, x + w / 2 + pad, y + sz * 0.78, fill=A(bg, a), r=sz * 0.78)
    c.text(x, y, txt, sz, A(fg, a))


# ---------------- 各鏡 ----------------
def shot1(c, lt):
    cx, cy = 540, 680
    # 專注力圓環 → 碎裂
    if lt < 1.3:
        rot = lt * 120
        for k in range(12):
            a0 = rot + k * 30
            c.arc(cx, cy, 270, a0, a0 + 22, A(CYAN, 0.9), 16)
    rnd = random.Random(7)
    if lt >= 1.3:
        u = lt - 1.3
        for k in range(36):
            a = math.radians(k * 10 + rnd.uniform(-4, 4))
            sp = rnd.uniform(260, 620)
            d = 270 + sp * (1 - math.exp(-u * 2.2))
            px, py = cx + math.cos(a) * d, cy + math.sin(a) * d + 120 * u * u
            al = clamp(1 - u / 2.2)
            sz = rnd.uniform(8, 18)
            c.poly([(px - sz, py), (px, py - sz * 0.7), (px + sz, py + sz * 0.3)], A(CYAN, al))
        c.circle(cx, cy, 270 + 300 * ease(u / 0.5), outline=A(WHITE, clamp(0.6 - u)), w=6)
    r = 30 + 150 * eob(lt / 0.9)
    tomato(c, cx, cy, r, ang=lt * 540)
    # 震撼數字
    p = eob((lt - 0.5) / 0.6)
    if lt > 0.5:
        sz = 40 + 130 * p
        c.text(540, 1050, "20+ 分鐘", sz, A(WHITE, clamp((lt - 0.5) * 4)), stroke=6, sf=A(RED, clamp((lt - 0.5) * 4)))
        c.text(540, 1050 - sz * 0.95, "被打斷一次，找回專注要…", sz * 0.3, A(YEL, clamp((lt - 0.8) * 3)))
    if lt > 2.6:
        c.text(540, 1160, "※ 研究者受訪時引述的觀察數據，詳見資料來源", 25, A(GREY, clamp((lt - 2.6) * 2)))
    return (540, 900)


HOLES = [(360, 1.2), (560, 2.6), (760, 4.0)]

def shot2(c, lt):
    y, x0, x1 = 800, 200, 900
    # 書本
    bx, by = 135, y
    c.rect(bx - 62, by - 48, bx, by + 48, fill=A(WHITE, 0.95), r=8)
    c.rect(bx, by - 48, bx + 62, by + 48, fill=A((225, 235, 255), 0.95), r=8)
    c.line([(bx, by - 48), (bx, by + 48)], A(BLUE, 1), 4)
    for k in range(3):
        c.line([(bx - 50, by - 22 + k * 20), (bx - 12, by - 22 + k * 20)], A(BLUE, 0.6), 3)
    c.text(bx, by + 82, "讀書", 30)
    # 水管
    c.rect(x0, y - 36, x1, y + 36, fill=A((30, 60, 140), 0.9), outline=A(CYAN, 0.9), w=4, r=36)
    opened = [hx for hx, ht in HOLES if lt > ht + 0.35]
    for i in range(16):
        dx = x0 + 20 + ((i * 46 + lt * 180) % (x1 - x0 - 40))
        loss = sum(1 for hx in opened if hx < dx)
        al = 1 - 0.28 * loss
        c.rect(dx - 14, y - 9, dx + 14, y + 9, fill=A(CYAN, al), r=9)
    # 專注燈泡
    br = 1 - 0.27 * len(opened)
    gx = 965
    c.circle(gx, y, 70, fill=A(YEL, 0.15 * br))
    c.circle(gx, y, 50, fill=A(YEL, 0.25 + 0.75 * br))
    c.text(gx, y + 92, "專注力", 30)
    # 通知、破洞、漏水
    for hx, ht in HOLES:
        if lt < ht: continue
        u = lt - ht
        p = eob(u / 0.35)
        bw, bh = 170 * p, 72 * p
        by2 = 600
        c.rect(hx - bw / 2, by2 - bh / 2, hx + bw / 2, by2 + bh / 2, fill=A(WHITE, 0.97), r=18 * p)
        if p > 0.6:
            c.text(hx + 10, by2, "新訊息", 30 * p, A((40, 50, 80), 1))
            c.circle(hx - bw / 2 + 24, by2, 11 * p, fill=A(RED, 1))
        c.circle(hx + bw / 2 - 4, by2 - bh / 2 + 4, 14 * p, fill=A(RED, 1))
        if u > 0.2:
            k = ease((u - 0.2) / 0.2)
            tip = lerp(by2 + bh / 2, y - 30, k)
            c.poly([(hx - 14, by2 + bh / 2), (hx + 14, by2 + bh / 2), (hx, tip)], A(YEL, 0.95))
        if u > 0.35:
            c.circle(hx, y + 26, 14, fill=(5, 10, 30, 255))
            for j in range(5):
                v = ((u - 0.35) * 1.3 + j * 0.2) % 1.0
                c.circle(hx + math.sin(j * 2.1) * 10, y + 40 + v * 220, 10 * (1 - v * 0.4), fill=A(CYAN, 1 - v))
    if lt > 4.6:
        c.text(540, 1090, "注意力，一直在漏！", 58, A(YEL, clamp((lt - 4.6) * 3)), stroke=3, sf=(10, 20, 60, 255))
    return (540, 820)


def curve_decline(xn): return 0.95 - 0.5 * xn ** 1.35 + 0.025 * math.sin(xn * 20)

def shot3(c, lt):
    X0, Y0, X1, Y1 = 170, 480, 940, 1120
    al = clamp(lt * 3)
    axes(c, X0, Y0, X1, Y1, al)
    c.text(X1, Y0 - 40, "概念示意圖", 26, A(GREY, al), anchor="rm")
    pr = ease((lt - 0.3) / 3.8)
    if pr > 0:
        n = max(2, int(80 * pr))
        pts = [(X0 + 20 + (X1 - X0 - 60) * (i / 79), Y1 - (Y1 - Y0) * curve_decline(i / 79)) for i in range(n)]
        glow_line(c, pts, RED, 8)
        c.circle(*pts[-1], 16, fill=A(WHITE, 1))
        c.circle(*pts[-1], 26, fill=A(RED, 0.35))
    if lt > 4.2:
        p = eob((lt - 4.2) / 0.4)
        pill(c, 640, 760, "警覺性遞減", 50 * p + 1, RED)
        c.text(640, 838, "vigilance decrement", 28, A(GREY, clamp((lt - 4.5) * 3)))
        c.poly([(610, 800), (650, 800), (700, 880)], A(RED, p))
    return (600, 800)


def battery(c, x, y, w, h, lvl, al=1.0):
    c.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, outline=A(WHITE, al), w=7, r=18)
    c.rect(x - w * 0.18, y - h / 2 - 22, x + w * 0.18, y - h / 2, fill=A(WHITE, al), r=6)
    col = GREEN if lvl > 0.5 else (YEL if lvl > 0.22 else RED)
    hh = (h - 30) * lvl
    if hh > 2:
        c.rect(x - w / 2 + 15, y + h / 2 - 15 - hh, x + w / 2 - 15, y + h / 2 - 15, fill=A(col, al), r=8)


def shot4(c, lt):
    al = clamp(lt * 3)
    # 左：硬撐
    c.rect(80, 450, 520, 940, fill=A((20, 40, 110), 0.75 * al), outline=A(RED, 0.8 * al), w=4, r=30)
    c.text(300, 510, "硬撐不休息", 40, A(WHITE, al))
    lvl = 1 - 0.95 * ease((lt - 0.3) / 3.2)
    battery(c, 300, 740, 150, 300, lvl, al)
    if lvl < 0.2 and int(lt * 4) % 2 == 0:
        c.text(300, 900, "好累…", 32, A(RED, al))
    # 右：停不下來
    c.rect(560, 450, 1000, 940, fill=A((20, 40, 110), 0.75 * al), outline=A(YEL, 0.8 * al), w=4, r=30)
    c.text(780, 510, "一休息就停不下來", 36, A(WHITE, al))
    px0, py0, px1, py1 = 690, 570, 870, 905
    c.rect(px0, py0, px1, py1, fill=A((10, 14, 30), al), outline=A(WHITE, al), w=6, r=26)
    off = (lt * 160) % 90
    for k in range(6):
        yy = py0 + 30 + k * 90 - off
        if py0 + 18 < yy < py1 - 70:
            c.rect(px0 + 18, yy, px1 - 18, yy + 66, fill=A([BLUE, RED, GREEN][k % 3], 0.55 * al), r=10)
    c.text(780, 925, "∞ 無限滑", 28, A(YEL, al))
    # 中間：番茄搖擺＋問號
    sw = math.sin(lt * 5) * 18 * (1 if lt < 6 else 0.3)
    tomato(c, 540 + sw, 1120, 72, ang=lt * 90, alpha=al)
    if lt > 3.6:
        p = eob((lt - 3.6) / 0.4)
        c.text(540, 990 + math.sin(lt * 4) * 8, "?", 90 * p + 1, A(YEL, 1), stroke=4, sf=(10, 20, 60, 255))
    return (540, 760)


def curve_stable(xn):
    # 鋸齒：慢慢下滑，每次切換後回升
    seg = xn % 0.33
    return 0.93 - 0.18 * seg + 0.012 * math.sin(xn * 18)

def shot5(c, lt):
    X0, Y0, X1, Y1 = 170, 560, 940, 1140
    al = clamp(lt * 3)
    axes(c, X0, Y0, X1, Y1, al)
    c.text(X1, Y0 - 40, "概念示意，非原始數據", 26, A(GREY, al), anchor="rm")
    # 圖例
    c.line([(150, 440), (210, 440)], A(GREY, al), 8); c.text(225, 440, "一直做同一件事", 32, A(WHITE, al), anchor="lm")
    c.line([(560, 440), (620, 440)], A(GREEN, al), 8); c.text(635, 440, "穿插短暫轉換", 32, A(WHITE, al), anchor="lm")
    pr = ease((lt - 0.4) / 4.0)
    if pr > 0:
        n = max(2, int(90 * pr))
        xs = [i / 89 for i in range(n)]
        g = [(X0 + 20 + (X1 - X0 - 60) * x, Y1 - (Y1 - Y0) * curve_decline(x)) for x in xs]
        s = [(X0 + 20 + (X1 - X0 - 60) * x, Y1 - (Y1 - Y0) * curve_stable(x)) for x in xs]
        glow_line(c, g, GREY, 7, 0.8)
        glow_line(c, s, GREEN, 8)
        for sp in (0.33, 0.66):
            if xs[-1] > sp:
                sx = X0 + 20 + (X1 - X0 - 60) * sp
                sy = Y1 - (Y1 - Y0) * curve_stable(sp + 0.001)
                k = clamp((xs[-1] - sp) * 8)
                for j in range(8):
                    a = math.radians(j * 45)
                    c.line([(sx + math.cos(a) * 14, sy + math.sin(a) * 14),
                            (sx + math.cos(a) * (14 + 22 * k), sy + math.sin(a) * (14 + 22 * k))], A(YEL, 1 - k * 0.5), 4)
                c.text(sx, sy - 62, "切換", 26, A(YEL, 1))
    if lt > 4.8:
        p = eob((lt - 4.8) / 0.4)
        pill(c, 820, 660, "表現較穩", 40 * p + 1, GREEN, fg=(10, 40, 30))
        pill(c, 820, 1010, "逐漸下滑", 34 * p + 1, (110, 120, 150))
    return (560, 820)


SEQ6 = [(25, RED), (5, GREEN), (25, RED), (5, GREEN), (25, RED), (5, GREEN), (25, RED), (20, BLUE)]
TOT6 = sum(m for m, _ in SEQ6)
def p6(lt): return ease((lt - 0.4) / 5.6)
def work_ends():
    acc, ends = 0, []
    for m, col in SEQ6:
        acc += m
        if col == RED: ends.append(acc / TOT6)
    return ends

def shot6(c, lt):
    cx, cy, R = 540, 760, 285
    al = clamp(lt * 3)
    c.text(205, 405, "● 專注 25 分", 30, A(RED, al), anchor="mm")
    c.text(470, 405, "● 休息 5 分", 30, A(GREEN, al), anchor="mm")
    c.text(780, 405, "● 長休息 15–30 分", 30, A(BLUE, al), anchor="mm")
    p = p6(lt)
    acc = 0
    for m, col in SEQ6:
        a0 = -90 + 360 * acc / TOT6 + 0.8
        a1 = -90 + 360 * (acc + m) / TOT6 - 0.8
        c.arc(cx, cy, R, a0, a1, A(col, 0.22 * al), 54)
        lit_end = -90 + 360 * min(p, (acc + m) / TOT6)
        if lit_end > a0:
            c.arc(cx, cy, R, a0, min(a1, lit_end), A(col, al), 54)
        acc += m
    ha = math.radians(-90 + 360 * p)
    c.line([(cx + math.cos(ha) * 140, cy + math.sin(ha) * 140), (cx + math.cos(ha) * (R + 40), cy + math.sin(ha) * (R + 40))], A(WHITE, al), 7)
    c.circle(cx + math.cos(ha) * (R + 40), cy + math.sin(ha) * (R + 40), 12, fill=A(WHITE, al))
    tomato(c, cx, cy + 10, 110, ang=360 * p * 4, alpha=al)
    ends = work_ends()
    for i, e in enumerate(ends):
        on = p >= e - 1e-4
        k = eob((p - e) * 25) if on else 0
        tomato(c, 330 + i * 140, 1125, 26 + 6 * k, ang=0, alpha=al, grey=not on)
    return (540, 760)


def stopwatch(c, x, y, r, t):
    c.circle(x, y + 6, r, outline=WHITE + (255,), w=7)
    c.rect(x - 12, y - r - 22, x + 12, y - r - 4, fill=A(WHITE, 1), r=4)
    a = math.radians(-90 + t * 200)
    c.line([(x, y + 6), (x + math.cos(a) * r * 0.7, y + 6 + math.sin(a) * r * 0.7)], A(RED, 1), 6)

def bell_mute(c, x, y, r):
    c.circle(x, y - r * 0.15, r * 0.6, fill=A(YEL, 1))
    c.rect(x - r * 0.6, y - r * 0.15, x + r * 0.6, y + r * 0.45, fill=A(YEL, 1), r=4)
    c.rect(x - r * 0.8, y + r * 0.38, x + r * 0.8, y + r * 0.55, fill=A(YEL, 1), r=6)
    c.circle(x, y + r * 0.72, r * 0.15, fill=A(YEL, 1))
    c.line([(x - r * 0.85, y - r * 0.8), (x + r * 0.85, y + r * 0.9)], A(RED, 1), 9)

CARD_T = [0.9, 3.0, 5.0]
CARDS = [("有時限", "比較容易開始", RED), ("計時中不分心", "減少被打斷", YEL), ("定時休息", "減少疲勞感", GREEN)]

def shot7(c, lt):
    al = clamp(lt * 3)
    c.text(540, 430, "番茄鐘有效的 3 個原理", 50, A(WHITE, al))
    for i, (t0, (ti, su, col)) in enumerate(zip(CARD_T, CARDS)):
        if lt < t0: continue
        k = ease((lt - t0) / 0.45)
        y = 500 + i * 215
        dx = (1 - k) * 700
        c.rect(110 + dx, y, 970 + dx, y + 180, fill=A((18, 40, 115), 0.9 * k), outline=A(col, k), w=5, r=34)
        ix, iy = 225 + dx, y + 90
        c.circle(ix, iy, 72, fill=A(col, 0.18 * k))
        u = lt - t0
        if i == 0: stopwatch(c, ix, iy, 46, u)
        elif i == 1: bell_mute(c, ix, iy, 46)
        else: battery(c, ix, iy, 58, 104, clamp(0.15 + 0.85 * ease(u / 1.4)))
        c.text(335 + dx, y + 64, ti, 50, A(WHITE, k), anchor="lm")
        c.text(335 + dx, y + 126, su, 34, A(col, k), anchor="lm")
    return (540, 780)


def shot8(c, lt):
    al = clamp(lt * 3)
    if lt < 3.8:
        disp = "25"
    elif lt < 4.6:
        disp = "25" if int(lt * 12) % 2 == 0 else "?"
    else:
        disp = "?"
    tomato(c, 540, 540, 130, disp=disp, alpha=al)
    p = ease((lt - 0.5) / 0.5)
    c.rect(110, 740, 970, 910, fill=A((255, 255, 255), 0.95 * p), r=34)
    c.text(540, 796, "專注要分段", 54, A(RED, p))
    c.text(540, 862, "休息要規律", 54, A((30, 120, 90), p))
    if lt > 3.8:
        q = eob((lt - 3.8) / 0.45)
        c.rect(110, 940, 970, 1130, fill=A((20, 40, 120), 0.95), outline=A(YEL, 1), w=6, r=34)
        c.text(540, 995, "想一想", 44 * q + 1, A(YEL, 1))
        c.text(540, 1072, "25 分鐘，真的最適合你嗎？", 44 * q + 1, A(WHITE, 1))
    if lt > 5.0:
        c.text(540, 1175, "※ 番茄鐘效果因人而異，可試著調整時間長度", 25, A(GREY, clamp((lt - 5) * 2)))
    return (540, 1000)


SHOTS = [shot1, shot2, shot3, shot4, shot5, shot6, shot7, shot8]

# ---------------- 背景 ----------------
def make_bg():
    y = np.linspace(0, 1, H)[:, None]
    top = np.array([10, 22, 78]); bot = np.array([22, 96, 235])
    g = (top + (bot - top) * (y ** 1.2)[..., None]).repeat(W, axis=1)
    x = np.linspace(-1, 1, W)[None, :]
    vign = 1 - 0.25 * (x ** 2)
    g = g * vign[..., None]
    img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    for gx in range(0, W, 90): d.line([(gx, 0), (gx, H)], fill=(255, 255, 255, 10), width=1)
    for gy in range(0, H, 90): d.line([(0, gy), (W, gy)], fill=(255, 255, 255, 10), width=1)
    return img

BG = None
PART = [(random.Random(i).uniform(0, W), random.Random(i + 99).uniform(0, H),
         random.Random(i + 7).uniform(2, 5), random.Random(i + 3).uniform(15, 45)) for i in range(45)]


def wrap(txt, n=15):
    if len(txt) <= n: return [txt]
    PUN = "，。、；：！？"
    mid = len(txt) / 2
    cands = [i + 1 for i, ch in enumerate(txt[:-1]) if ch in PUN and abs(i + 1 - mid) < len(txt) * 0.3]
    k = min(cands, key=lambda i: abs(i - mid)) if cands else int(math.ceil(mid))
    return [txt[:k], txt[k:]]


def render(fi):
    global BG
    if BG is None: BG = make_bg()
    t = fi / FPS
    si = min(7, int(t / SHOT)); lt = t - si * SHOT
    frame = BG.copy()
    d = ImageDraw.Draw(frame, "RGBA")
    for px, py, r, sp in PART:
        yy = (py - t * sp) % H
        d.ellipse([px - r, yy - r, px + r, yy + r], fill=(160, 220, 255, 40))
    c = C()
    fx, fy = SHOTS[si](c, lt)
    # 推近：每鏡緩慢放大 12%
    z = 1 + 0.12 * ease(lt / SHOT)
    cw, ch = W * S / z, H * S / z
    x0 = clamp(fx * S - cw / 2, 0, W * S - cw); y0 = clamp(fy * S - ch / 2, 0, H * S - ch)
    layer = c.im.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    fade = clamp(min(lt / 0.45, (SHOT - lt) / 0.45)) if 0 < si < 7 else (
        clamp((SHOT - lt) / 0.45) if si == 0 else clamp(lt / 0.45))
    if fade < 1:
        a = np.asarray(layer).copy(); a[..., 3] = (a[..., 3] * fade).astype(np.uint8)
        layer = Image.fromarray(a, "RGBA")
    frame.alpha_composite(layer)
    d = ImageDraw.Draw(frame, "RGBA")
    # 段落標籤與資料來源（固定在上方安全區）
    chip = CHIP[si]
    f = F(30, 1); w = f.getlength(chip)
    d.rounded_rectangle([540 - w / 2 - 26, 278, 540 + w / 2 + 26, 330], radius=26, fill=(255, 255, 255, 230))
    d.text((540, 304), chip, font=f, fill=(20, 40, 110, 255), anchor="mm")
    if SRC[si]:
        d.text((540, 360), SRC[si], font=F(24, 1), fill=(200, 215, 245, 230), anchor="mm")
    # 逐字字幕
    for st, en, txt in SEGS:
        if st <= t < en:
            lines = wrap(txt)
            fs = F(54, 1); lh = 74
            tot = lh * len(lines)
            yb = 1330
            maxw = max(fs.getlength(l) for l in lines)
            d.rounded_rectangle([540 - maxw / 2 - 30, yb - 22, 540 + maxw / 2 + 30, yb + tot + 10],
                                radius=24, fill=(5, 12, 40, 165))
            for k, l in enumerate(lines):
                d.text((540, yb + k * lh + lh / 2 - 6), l, font=fs, fill=(255, 255, 255, 255),
                       anchor="mm", stroke_width=3, stroke_fill=(10, 20, 60, 255))
    # 片頭／片尾黑場
    g = clamp(min(t / 0.5, (DUR - t) / 0.9))
    if g < 1:
        frame = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), frame, g)
    return frame.convert("RGB").tobytes()


# ---------------- 配樂與音效（程式合成，無版權疑慮） ----------------
SR = 48000
def synth_music():
    n = int(DUR * SR); out = np.zeros(n)
    t_all = np.arange(n) / SR
    def add(t0, sig, gain=1.0):
        i = int(t0 * SR)
        if i >= n: return
        j = min(n, i + len(sig)); out[i:j] += sig[: j - i] * gain
    def env(d, a=0.005, dec=8.0):
        tt = np.arange(int(d * SR)) / SR
        return np.minimum(1, tt / a) * np.exp(-tt * dec), tt
    BPM = 120; beat = 60 / BPM
    chords = [[261.63, 329.63, 392.0], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66]]
    roots = [65.41, 55.0, 43.65, 49.0]
    drums_off = lambda tt: 26.0 <= tt < 30.0 or tt >= 57.0
    nb = int(DUR / beat)
    for b in range(nb):
        tb = b * beat
        ch = chords[(b // 4) % 4]; rt = roots[(b // 4) % 4]
        if not drums_off(tb):
            e, tt = env(0.35, 0.002, 9)
            f = 45 + 80 * np.exp(-tt * 30)
            add(tb, np.sin(2 * np.pi * np.cumsum(f) / SR) * e, 0.55)
            e, tt = env(0.05, 0.001, 70)
            nz = np.random.RandomState(b).randn(len(tt)); nz = np.diff(nz, prepend=0)
            add(tb + beat / 2, nz * e, 0.06)
            if b % 2 == 1:
                e, tt = env(0.18, 0.002, 18)
                nz = np.random.RandomState(b + 500).randn(len(tt))
                add(tb, (nz * 0.6 + np.sin(2 * np.pi * 190 * tt)) * e, 0.16)
        for h in range(2):
            e, tt = env(beat / 2, 0.01, 5)
            sig = np.sign(np.sin(2 * np.pi * rt * 2 * tt)) * 0.5 + np.sin(2 * np.pi * rt * tt)
            add(tb + h * beat / 2, sig * e, 0.13 if tb < 57 else 0.06)
        for k in range(4):
            fr = ch[(b * 4 + k) % 3] * (2 if k % 2 else 1)
            e, tt = env(0.22, 0.003, 14)
            sig = np.sin(2 * np.pi * fr * tt) + 0.3 * np.sin(2 * np.pi * fr * 2 * tt)
            add(tb + k * beat / 4, sig * e, 0.07)
        if b % 4 == 0:
            e, tt = env(beat * 4, 0.3, 0.6)
            sig = sum(np.sin(2 * np.pi * f * tt) for f in ch)
            add(tb, sig * e, 0.045)
    def ding(t0, f=1320, g=0.25):
        e, tt = env(0.8, 0.002, 6)
        add(t0, (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.01 * tt)) * e, g)
    def sweep(t0, f0, f1, d, g=0.2):
        tt = np.arange(int(d * SR)) / SR
        f = f0 + (f1 - f0) * tt / d
        e = np.sin(np.pi * tt / d)
        add(t0, np.sin(2 * np.pi * np.cumsum(f) / SR) * e, g)
    # 開場重擊
    e, tt = env(1.6, 0.003, 2.5)
    add(0.0, (np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-tt * 6)) / SR) + 0.25 * np.random.RandomState(1).randn(len(tt)) * np.exp(-tt * 10)) * e, 0.8)
    add(8.8, np.zeros(1))
    sweep(1.3, 600, 1800, 0.5, 0.12)
    for hx, ht in HOLES: ding(SHOT + ht, 1480, 0.22)
    sweep(2 * SHOT + 0.8, 900, 300, 1.6, 0.18)
    for k in range(8):
        e, tt = env(0.03, 0.001, 120)
        add(26.0 + k * 0.5, np.sin(2 * np.pi * 2400 * tt) * e, 0.25)
    sweep(4 * SHOT + 0.8, 300, 950, 1.4, 0.16)
    ends = work_ends(); ts = np.arange(0, SHOT, 0.005)
    for i, e_ in enumerate(ends):
        hit = next((x for x in ts if p6(x) >= e_ - 1e-4), None)
        if hit is not None: ding(5 * SHOT + hit, 1046.5 * (1.12 ** i), 0.22)
    for i, t0 in enumerate(CARD_T): ding(6 * SHOT + t0, [784, 988, 1175][i], 0.2)
    e, tt = env(3.0, 0.05, 1.2)
    add(57.0, sum(np.sin(2 * np.pi * f * tt) for f in [261.63, 329.63, 392.0, 523.25]) * e, 0.12)
    fade = np.clip((DUR - t_all) / 2.0, 0, 1) * np.clip(t_all / 0.02, 0, 1)
    out *= fade
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.85
    nar = os.path.join(OUT, "narration.wav")
    if os.path.exists(nar):  # 旁白出現時把配樂壓低（約 -12 dB）
        with wave.open(nar) as w:
            v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        v = np.pad(v, (0, max(0, n - len(v))))[:n]
        envv = np.convolve(np.abs(v), np.ones(4800) / 4800, mode="same")
        duck = np.clip(envv / 0.02, 0, 1)
        duck = np.convolve(duck, np.ones(9600) / 9600, mode="same")
        out = out * 0.45 * (1 - 0.72 * duck) + v / (np.max(np.abs(v)) + 1e-9) * 0.9
        out = out / (np.max(np.abs(out)) + 1e-9) * 0.9
    st = np.stack([out, out], axis=1)
    path = os.path.join(OUT, "music.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())
    return path


def write_srt():
    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    with open(os.path.join(OUT, "subtitles.srt"), "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(SEGS, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        for i in range(8):
            for lt in (1.5, 6.0):
                fi = int((i * SHOT + lt) * FPS)
                Image.frombytes("RGB", (W, H), render(fi)).save(os.path.join(sys.argv[2], f"s{i+1}_{lt}.png"))
        sys.exit()
    write_srt()
    wav = synth_music()
    mp4 = os.path.join(OUT, "pomodoro_reels.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(DUR), mp4],
                          stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, b in enumerate(pool.imap(render, range(N), chunksize=6)):
            ff.stdin.write(b)
            if k % 150 == 0: print(f"frame {k}/{N}", flush=True)
    ff.stdin.close(); ff.wait()
    print("done", mp4)
