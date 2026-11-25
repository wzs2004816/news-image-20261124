#!/usr/bin/env python3
"""news-image-20261124: sum up Tuesday 24 November 2026 in one image.

Pure Python 3 stdlib. Reads atlas.bin / atlas.json / map.txt (data files
shipped in this repo, generated at build time from system DejaVu fonts and
Natural Earth land polygons) and draws a 1024x1024 newspaper front page to
$MAKEFUN_OUTPUT_DIR/entry.png. Deterministic: no randomness, no clock, no
network; two runs write byte-identical files.
"""
import json
import os
import struct
import sys
import zlib

W, H = 1024, 1024

PAPER = (246, 241, 230)
INK = (25, 23, 19)
RED = (166, 38, 29)
NAVY = (29, 58, 95)
NAVY_DARK = (16, 32, 56)
GOLD = (192, 138, 30)
TEAL = (14, 107, 92)
GREY = (107, 101, 90)
WHITE = (255, 255, 255)
CARD = (255, 253, 247)
LINE = (25, 23, 19)

REGION_COLORS = {
    "NA": (29, 78, 137), "EU": (122, 31, 31), "ME": (138, 90, 0),
    "AF": (14, 107, 92), "SA": (179, 71, 0), "EA": (91, 45, 142),
    "SEA": (46, 125, 50), "OC": (69, 90, 100),
}
REGION_NAMES = {
    "NA": "NORTH AMERICA", "EU": "EUROPE", "ME": "MIDDLE EAST",
    "AF": "AFRICA", "SA": "SOUTH ASIA", "EA": "EAST ASIA",
    "SEA": "SOUTHEAST ASIA", "OC": "OCEANIA",
}

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.clip = None
        self.buf = bytearray(bytes(bg) * (w * h))

    def set_clip(self, x, y, w, h):
        self.clip = (x, y, x + w, y + h)

    def clear_clip(self):
        self.clip = None

    def _in_clip(self, x, y):
        if self.clip is None:
            return 0 <= x < self.w and 0 <= y < self.h
        cx0, cy0, cx1, cy1 = self.clip
        return cx0 <= x < cx1 and cy0 <= y < cy1

    def _off(self, x, y):
        return (y * self.w + x) * 3

    def set_px(self, x, y, color):
        if self._in_clip(x, y):
            o = self._off(x, y)
            self.buf[o:o + 3] = bytes(color)

    def blend_px(self, x, y, color, alpha):
        if self._in_clip(x, y) and alpha:
            o = self._off(x, y)
            b = self.buf
            if alpha >= 255:
                b[o:o + 3] = bytes(color)
            else:
                a = alpha
                b[o] = (color[0] * a + b[o] * (255 - a)) // 255
                b[o + 1] = (color[1] * a + b[o + 1] * (255 - a)) // 255
                b[o + 2] = (color[2] * a + b[o + 2] * (255 - a)) // 255

    def rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if self.clip is not None:
            x0 = max(x0, self.clip[0])
            y0 = max(y0, self.clip[1])
            x1 = min(x1, self.clip[2])
            y1 = min(y1, self.clip[3])
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            o = self._off(x0, yy)
            self.buf[o:o + len(row)] = row

    def hline(self, x, y, w, color, thick=1):
        self.rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.rect(x, y, thick, h, color)

    def frame(self, x, y, w, h, color, thick=1):
        self.rect(x, y, w, thick, color)
        self.rect(x, y + h - thick, w, thick, color)
        self.rect(x, y, thick, h, color)
        self.rect(x + w - thick, y, thick, h, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x0 + dx * t))
            y = int(round(y0 + dy * t))
            self.rect(x - thick // 2, y - thick // 2, thick, thick, color)

    def circle(self, cx, cy, r, color):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.set_px(xx, yy, color)

    def disc(self, cx, cy, r, color):
        self.circle(cx, cy, r, color)

    def ring(self, cx, cy, r, color, thick=1):
        for yy in range(cy - r - 1, cy + r + 2):
            for xx in range(cx - r - 1, cx + r + 2):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if (r - thick) ** 2 <= d2 <= (r + 1) ** 2:
                    self.set_px(xx, yy, color)

    def poly(self, pts, color):
        """Scanline-fill a polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        ymin, ymax = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(ymin, ymax + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = int(round(xs[i]))
                xb = int(round(xs[i + 1]))
                if xb > xa:
                    self.rect(xa, y, xb - xa, 1, color)


# ---------------------------------------------------------------- fonts
class FontSet:
    def __init__(self, base):
        with open(os.path.join(base, "atlas.json"), encoding="utf-8") as f:
            lines = f.read().splitlines()
        with open(os.path.join(base, "atlas.bin"), "rb") as f:
            self.blob = f.read()
        self.fonts = {}
        for line in lines:
            d = json.loads(line)
            glyphs = {}
            for ch, off, w, h, dx, dy, adv in d["glyphs"]:
                glyphs[ch] = (off, w, h, dx, dy, adv)
            self.fonts[d["name"]] = {
                "size": d["size"], "ascent": d["ascent"],
                "descent": d["descent"], "glyphs": glyphs,
            }

    def width(self, name, s):
        f = self.fonts[name]
        total = 0
        for ch in s:
            g = f["glyphs"].get(ch)
            total += g[5] if g else f["glyphs"][" "][5]
        return total

    def wrap(self, name, s, maxw, max_lines=None):
        """Greedy word wrap; returns lines, each <= maxw wide."""
        words = s.split(" ")
        lines = []
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if self.width(name, trial) <= maxw:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
                # A single word wider than the box: hard-split it.
                while self.width(name, cur) > maxw and len(cur) > 1:
                    cut = len(cur) - 1
                    while cut > 1 and self.width(name, cur[:cut]) > maxw:
                        cut -= 1
                    lines.append(cur[:cut] + "-")
                    cur = cur[cut:]
        if cur:
            lines.append(cur)
        if max_lines is not None and len(lines) > max_lines:
            raise ValueError("wrap overflow: %r needs %d lines (max %d)"
                             % (s, len(lines), max_lines))
        return lines


AUDIT = {"draws": 0, "violations": 0}


def draw_text(cv, fonts, name, x, y, s, color, align="l", maxw=None):
    """Draw text with its top at y. Raises if it exceeds maxw."""
    f = fonts.fonts[name]
    w = fonts.width(name, s)
    if maxw is not None and w > maxw:
        AUDIT["violations"] += 1
        raise ValueError("width audit FAIL: %r is %dpx > %dpx (%s)"
                         % (s, w, maxw, name))
    AUDIT["draws"] += 1
    if align == "c":
        x -= w // 2
    elif align == "r":
        x -= w
    pen = x
    blob = fonts.blob
    for ch in s:
        g = f["glyphs"].get(ch)
        if g is None:
            g = f["glyphs"][" "]
        off, gw, gh, dx, dy, adv = g
        if gw and gh:
            gx0 = pen + dx
            gy0 = y + dy
            for row in range(gh):
                base = off + row * gw
                yy = gy0 + row
                if yy < 0 or yy >= cv.h:
                    continue
                for col in range(gw):
                    a = blob[base + col]
                    if a:
                        cv.blend_px(gx0 + col, yy, color, a)
        pen += adv
    return w


def draw_lines(cv, fonts, name, x, y, lines, color, leading, maxw):
    for i, ln in enumerate(lines):
        draw_text(cv, fonts, name, x, y + i * leading, ln, color, maxw=maxw)


# ---------------------------------------------------------------- png
def write_png(cv, path):
    raw = bytearray()
    w, h = cv.w, cv.h
    buf = cv.buf
    prev = bytes(w * 3)
    for y in range(h):
        row = bytes(buf[y * w * 3:(y + 1) * w * 3])
        if y == 0:
            raw.append(0)
            raw += row
        else:
            raw.append(2)  # Up filter
            raw += bytes((a - b) & 0xFF for a, b in zip(row, prev))
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- scenes
# Every scene is drawn with canvas primitives inside its own box (x, y, w, h).

def scene_chip(cv, fonts, x, y, w, h):
    """Hero 1: a chip riding a rising market chart."""
    cv.rect(x, y, w, h, (13, 46, 32))
    # grid lines
    for gy in range(y + 18, y + h - 8, 18):
        cv.hline(x + 8, gy, w - 16, (30, 80, 58))
    for gx in range(x + 18, x + w - 8, 22):
        cv.vline(gx, y + 8, h - 16, (30, 80, 58))
    # rising chart line
    pts = [(x + 10, y + h - 26), (x + 44, y + h - 44), (x + 74, y + h - 34),
           (x + 108, y + h - 62), (x + 142, y + h - 52), (x + 176, y + h - 84),
           (x + 210, y + h - 74), (x + 246, y + h - 108), (x + w - 14, y + 22)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                (86, 214, 120), 4)
    # arrow head
    cv.poly([(x + w - 14, y + 22), (x + w - 30, y + 24), (x + w - 16, y + 38)],
            (86, 214, 120))
    # chip
    cx, cy, cw, chh = x + w // 2 - 48, y + h // 3, 96, max(36, h // 2)
    for px in range(cx - 14, cx + cw + 14, 12):
        cv.vline(px, cy - 10, 10, (192, 138, 30), 3)
        cv.vline(px, cy + chh, 10, (192, 138, 30), 3)
    for py in range(cy - 8, cy + chh + 8, 12):
        cv.hline(cx - 10, py, 10, (192, 138, 30), 3)
        cv.hline(cx + cw, py, 10, (192, 138, 30), 3)
    cv.rect(cx, cy, cw, chh, (24, 24, 28))
    cv.frame(cx, cy, cw, chh, (192, 138, 30), 2)
    cv.rect(cx + 24, cy + 12, 48, 24, (58, 66, 84))
    cv.frame(cx + 24, cy + 12, 48, 24, (140, 170, 210), 1)
    draw_text(cv, fonts, "sansb16", cx + cw // 2, cy + 16, "NVDA",
              (255, 255, 255), align="c")
    draw_text(cv, fonts, "sansb16", x + 14, y + 8, "+31%",
              (86, 214, 120))


def scene_warship(cv, fonts, x, y, w, h):
    """Hero 2: sea drones strike a warship off Libya."""
    cv.rect(x, y, w, h, (18, 44, 74))
    sea_top = y + h * 3 // 5
    # sky glow + sun
    cv.rect(x, y, w, sea_top - 10, (214, 122, 54))
    cv.rect(x, sea_top - 10, w, 10, (232, 164, 90))
    cv.disc(x + w - 44, y + 26, 14, (255, 214, 130))
    # sea
    cv.rect(x, sea_top, w, h - h * 3 // 5, (10, 40, 70))
    for wy in range(sea_top + 12, y + h - 6, 14):
        for wx in range(x + 8, x + w - 8, 26):
            cv.hline(wx, wy, 14, (52, 110, 158), 2)
    # warship (burning) — light hull against the dark sea
    hx, hy = x + 52, sea_top + 2
    cv.poly([(hx, hy), (hx + 160, hy), (hx + 148, hy + 20),
             (hx + 12, hy + 20)], (126, 134, 144))
    cv.rect(hx + 34, hy - 22, 40, 22, (96, 104, 116))
    cv.rect(hx + 84, hy - 12, 24, 12, (96, 104, 116))
    cv.vline(hx + 54, hy - 38, 18, (96, 104, 116), 3)
    cv.rect(hx + 112, hy - 16, 20, 5, (70, 76, 86))
    # flame: jagged red-orange-yellow layers rising mid-ship
    fx = hx + 100
    cv.poly([(fx - 16, hy), (fx - 10, hy - 24), (fx - 4, hy - 12),
             (fx + 2, hy - 38), (fx + 8, hy - 14), (fx + 14, hy - 26),
             (fx + 18, hy)], (226, 60, 20))
    cv.poly([(fx - 9, hy), (fx - 5, hy - 18), (fx, hy - 8),
             (fx + 5, hy - 26), (fx + 10, hy)], (255, 140, 20))
    cv.poly([(fx - 4, hy), (fx - 1, hy - 12), (fx + 3, hy - 6),
             (fx + 5, hy)], (255, 214, 60))
    # smoke column
    for sx, sy, sr in [(fx + 2, hy - 46, 8), (fx + 8, hy - 58, 10),
                       (fx + 2, hy - 70, 8)]:
        cv.disc(sx, sy, sr, (96, 96, 104))
    # sea drones closing in
    for dx in (x + 20, x + 236):
        cv.poly([(dx, y + h - 30), (dx + 26, y + h - 30),
                 (dx + 20, y + h - 18), (dx + 6, y + h - 18)], (220, 224, 230))
        cv.line(dx + 2, y + h - 24, dx - 14, y + h - 14, (220, 224, 230), 2)
    draw_text(cv, fonts, "sansb11", x + 10, y + h - 16, "7 SEA DRONES",
              (255, 255, 255))


def scene_kyiv(cv, fonts, x, y, w, h):
    """Hero 3: Kyiv skyline under a night drone attack."""
    cv.rect(x, y, w, h, (26, 22, 48))
    for sy in range(y + 6, y + 46, 9):
        for sx in range(x + 6, x + w - 6, 17):
            if (sx * 7 + sy * 13) % 29 < 6:
                cv.set_px(sx, sy, (220, 220, 200))
    # dusk band
    cv.rect(x, y + 46, w, 18, (122, 52, 52))
    cv.rect(x, y + 64, w, 8, (176, 92, 60))
    # skyline
    base = y + h - 8
    towers = [(0, 58), (34, 84), (74, 66), (104, 96), (150, 72),
              (186, 88), (222, 62), (252, 80)]
    for tx, th in towers:
        cv.rect(x + tx, base - th, 30, th, (12, 12, 20))
        for wy in range(base - th + 8, base - 6, 12):
            for wx in range(x + tx + 5, x + tx + 25, 10):
                if (wx + wy) % 23 < 9:
                    cv.rect(wx, wy, 3, 4, (255, 196, 90))
    # drones + explosion bursts over the skyline
    for dx, dy in [(x + 60, y + 22), (x + 150, y + 14), (x + 220, y + 30)]:
        cv.line(dx - 7, dy, dx + 7, dy, (255, 90, 60), 2)
        cv.line(dx, dy - 7, dx, dy + 7, (255, 90, 60), 2)
        cv.disc(dx, dy, 2, (255, 220, 180))
    for bx, by, br in [(x + 120, y + 34, 13), (x + 208, y + 26, 10)]:
        cv.poly([(bx - br, by), (bx - br // 2, by - br // 2),
                 (bx, by - br), (bx + br // 2, by - br // 2),
                 (bx + br, by), (bx + br // 2, by + br // 2),
                 (bx, by + br), (bx - br // 2, by + br // 2)],
                (255, 120, 40))
        cv.disc(bx, by, br // 2, (255, 214, 90))
    draw_text(cv, fonts, "sansb11", x + 10, y + h - 16, "KYIV REGION",
              (255, 255, 255))


def scene_satellite(cv, fonts, x, y, w, h):
    """Spot: a satellite over Earth."""
    cv.rect(x, y, w, h, (10, 18, 42))
    for i in range(22):
        sx = x + 4 + (i * 53) % (w - 8)
        sy = y + 3 + (i * 29) % (h - 18)
        cv.set_px(sx, sy, (230, 230, 210))
    # Earth arc along the bottom (shallow planet limb)
    cv.disc(x + w // 2, y + h + 70, 90, (52, 140, 190))
    cv.disc(x + w // 2, y + h + 70, 84, (38, 110, 160))
    # satellite body + panels
    bx, by = x + w // 2 - 12, y + 6
    cv.rect(bx, by, 24, 12, (200, 205, 212))
    cv.frame(bx, by, 24, 12, (120, 128, 140), 1)
    cv.rect(bx - 26, by + 3, 22, 7, (40, 90, 160))
    cv.rect(bx + 28, by + 3, 22, 7, (40, 90, 160))
    cv.line(bx + 12, by + 12, bx + 12, by + 18, (200, 205, 212), 2)
    cv.disc(bx + 12, by + 20, 4, (220, 225, 232))
    cv.line(bx + 34, by + 6, bx + 52, by - 2, (255, 176, 32), 2)


def scene_gavel(cv, fonts, x, y, w, h):
    """Spot: a gavel over a law book."""
    cv.rect(x, y, w, h, (96, 62, 34))
    # law book at the bottom
    cv.rect(x + 12, y + h - 13, w - 24, 10, (196, 40, 28))
    cv.frame(x + 12, y + h - 13, w - 24, 10, (255, 255, 255), 1)
    draw_text(cv, fonts, "sansb10", x + w // 2, y + h - 12, "GROK",
              (255, 255, 255), align="c")
    # gavel: handle + head
    cv.line(x + 26, y + h - 16, x + w - 30, y + 8, (210, 170, 110), 6)
    cv.rect(x + w - 58, y + 2, 30, 12, (150, 110, 60))
    cv.frame(x + w - 58, y + 2, 30, 12, (90, 64, 30), 1)
    cv.rect(x + 20, y + h - 24, 26, 10, (150, 110, 60))


def scene_capitol(cv, fonts, x, y, w, h):
    """Spot: a capitol dome and columns."""
    cv.rect(x, y, w, h, (232, 226, 214))
    cx = x + w // 2
    # dome (stacked bars)
    for r in range(13, 0, -1):
        cv.hline(cx - r, y + 20 - r, r * 2, (255, 255, 255))
    cv.rect(cx - 2, y + 2, 4, 7, (166, 38, 29))
    cv.disc(cx, y + 2, 2, (166, 38, 29))
    cv.rect(cx - 15, y + 20, 30, 4, (255, 255, 255))
    # columns
    for i in range(5):
        colx = x + 16 + i * ((w - 32 - 8) // 4)
        cv.rect(colx, y + 26, 8, h - 32, (255, 255, 255))
        cv.rect(colx - 1, y + 24, 10, 3, (200, 196, 186))
    cv.rect(x + 8, y + h - 5, w - 16, 3, (200, 196, 186))


def scene_train(cv, fonts, x, y, w, h):
    """Spot: the Saryu-Kamala Express crossing a bridge."""
    cv.rect(x, y, w, h, (168, 208, 232))
    cv.disc(x + w - 18, y + 9, 6, (255, 226, 130))
    cv.rect(x, y + h - 8, w, 8, (120, 170, 120))
    # bridge
    cv.rect(x, y + h - 12, w, 3, (90, 70, 50))
    for bx in range(x + 8, x + w - 8, 16):
        cv.vline(bx, y + h - 12, 4, (90, 70, 50), 2)
    # train: saffron / white / green
    tx, ty, tw, th = x + 12, y + 6, w - 24, 18
    cv.rect(tx, ty, tw, 6, (255, 153, 51))
    cv.rect(tx, ty + 6, tw, 6, (255, 255, 255))
    cv.rect(tx, ty + 12, tw, 6, (19, 136, 8))
    for wx in range(tx + 7, tx + tw - 8, 16):
        cv.rect(wx, ty + 7, 10, 4, (40, 80, 120))
    # wheels + track
    for wx in range(tx + 12, tx + tw - 8, 24):
        cv.disc(wx, ty + th + 1, 3, (30, 30, 34))
    cv.hline(x, ty + th + 5, w, (60, 60, 64), 2)


def scene_ship(cv, fonts, x, y, w, h):
    """Spot: a cargo ship under tow."""
    cv.rect(x, y, w, h, (196, 214, 226))
    sea_top = y + h - 12
    cv.rect(x, sea_top, w, 12, (34, 90, 130))
    for wy in range(sea_top + 3, y + h - 2, 5):
        for wx in range(x + 6, x + w - 6, 22):
            cv.hline(wx, wy, 10, (120, 180, 210), 1)
    # tug ahead
    cv.poly([(x + 10, sea_top - 8), (x + 34, sea_top - 8),
             (x + 30, sea_top), (x + 14, sea_top)], (40, 40, 46))
    cv.rect(x + 17, sea_top - 18, 11, 10, (200, 60, 40))
    # tow line
    cv.line(x + 36, sea_top - 5, x + 66, sea_top - 9, (30, 30, 34), 1)
    # cargo ship
    sx = x + 66
    cv.poly([(sx, sea_top - 12), (sx + 96, sea_top - 12),
             (sx + 88, sea_top), (sx + 8, sea_top)], (52, 58, 66))
    for i, cc in enumerate([(200, 60, 40), (40, 90, 160), (192, 138, 30)]):
        cv.rect(sx + 12 + i * 26, sea_top - 26, 22, 13, cc)
    cv.rect(sx + 58, sea_top - 34, 16, 8, (230, 230, 228))


# Small 16x16 icons for the timeline strip.
def icon_sun(cv, x, y, c):
    cv.disc(x + 8, y + 8, 5, c)
    for a in range(8):
        dx = [0, 5, 7, 5, 0, -5, -7, -5][a]
        dy = [-7, -5, 0, 5, 7, 5, 0, -5][a]
        cv.line(x + 8, y + 8, x + 8 + dx, y + 8 + dy, c, 1)


def icon_train(cv, x, y, c):
    cv.rect(x + 3, y + 2, 10, 11, c)
    cv.rect(x + 5, y + 4, 3, 3, (255, 255, 255))
    cv.rect(x + 9, y + 4, 3, 3, (255, 255, 255))
    cv.hline(x + 1, y + 14, 14, c, 2)


def icon_gavel(cv, x, y, c):
    cv.line(x + 2, y + 13, x + 13, y + 3, c, 2)
    cv.rect(x + 10, y + 2, 5, 4, c)


def icon_rocket(cv, x, y, c):
    cv.poly([(x + 8, y + 1), (x + 12, y + 8), (x + 8, y + 11), (x + 4, y + 8)], c)
    cv.poly([(x + 8, y + 11), (x + 10, y + 15), (x + 6, y + 15)], (255, 120, 40))


def icon_capitol(cv, x, y, c):
    cv.poly([(x + 8, y + 1), (x + 13, y + 6), (x + 3, y + 6)], c)
    cv.rect(x + 3, y + 8, 2, 6, c)
    cv.rect(x + 7, y + 8, 2, 6, c)
    cv.rect(x + 11, y + 8, 2, 6, c)
    cv.hline(x + 2, y + 14, 12, c, 2)


def icon_ball(cv, x, y, c):
    cv.disc(x + 8, y + 8, 7, c)
    cv.line(x + 2, y + 6, x + 14, y + 6, (255, 255, 255), 1)
    cv.line(x + 2, y + 10, x + 14, y + 10, (255, 255, 255), 1)
    cv.line(x + 8, y + 2, x + 8, y + 14, (255, 255, 255), 1)


# ---------------------------------------------------------------- the day
# Every story was first reported on Tuesday 24 November 2026 in some time
# zone (Asian morning editions and overnight wires count). Neighbouring-day
# stories deliberately left out are listed in EXCLUDED below.

HEROES = [
    {
        "kicker": "MARKETS · NORTH AMERICA",
        "headline": "Huang is back — markets roar",
        "deck": "Huang returns as Nvidia CEO after a Trump push; shares "
                "+31%. Nasdaq +6.5%, S&P +4.7% — best day since April 2025.",
        "region": "NA", "scene": scene_chip,
    },
    {
        "kicker": "UKRAINE · AFRICA",
        "headline": "Fallout grows from Kyiv's Libya strike",
        "deck": "UN mission seeks a probe into the sinking of Russian "
                "corvette Merkury off Benghazi; Kremlin warns of Baltic "
                "escalation.",
        "region": "AF", "scene": scene_warship,
    },
    {
        "kicker": "WAR IN UKRAINE · EUROPE",
        "headline": "Russian strikes kill 14 in Kyiv region",
        "deck": "Overnight drone and missile strikes hit homes around the "
                "capital. Zelensky calls for four-way talks "
                "'as soon as possible'.",
        "region": "EU", "scene": scene_kyiv,
    },
]

SECOND = [
    ("NATO vows space defence as allies warn of a Russian orbital weapon",
     scene_satellite, "EU"),
    ("States sue Musk firms over sexualised images made by chatbot Grok",
     scene_gavel, "NA"),
    ("Trump targets Newsom and Democrats in DOJ speech on violent crime",
     scene_capitol, "NA"),
    ("Modi and Nepal PM flag off Saryu–Kamala Express to Janakpur",
     scene_train, "SA"),
    ("Drone-hit Russian cargo ship arrives in St Petersburg under tow",
     scene_ship, "EU"),
]

# (region, headline) — 36 items, each wrapped to at most 2 lines.
GRID = [
    ("NA", "Rep. Jimmy Gomez resigns after ethics panel finds evidence of sexual misconduct"),
    ("NA", "UN chief calls for an AI risk-management framework within a year"),
    ("SEA", "Trump offers the Philippines $2.4bn for self-defence — with a catch"),
    ("EU", "Moscow accuses Estonia of hostile acts 'on verge of triggering open war'"),
    ("ME", "Gaza students set to begin studies in Ireland after winning visa battle"),
    ("SEA", "More bodies recovered from Indonesia candy factory fire"),
    ("AF", "Drones hit homes and a UN building in Sudan's capital"),
    ("EA", "North Korea's Kim visits factory sites after 'Trump snub'"),
    ("EA", "North Korea ready to expand ties with other countries"),
    ("SEA", "Thai court upholds verdict for opposition lawmaker"),
    ("EA", "Taiwan warns Canada's Carney that deeper China ties carry risks"),
    ("SA", "Pakistan, Malaysia discuss military cooperation as Munir meets Anwar"),
    ("EU", "Thousands protest closure of Turkey media outlets"),
    ("EU", "Macron eyes constitutional changes to curb spending"),
    ("EU", "Burnham: 'unthinkable' to join EU without UK referendum"),
    ("EU", "GTA VI hacker Arion Kurtaj, 21, gets 7-year sentence; walks free on time served"),
    ("EU", "Thousands evacuated from UK concert after 'unknown substance' released"),
    ("EU", "Report: William plans to strip Harry and Meghan of titles when he is king"),
    ("SA", "Report: Chinese satellites made 37 odd moves over Pahalgam before 2025 attack"),
    ("SA", "Man attacks five police with knife inside Delhi's Jama Masjid station, flees"),
    ("SA", "Congress's 'Gyanesh Theft Arrangers' GTA jibe at Modi-Shah sparks row"),
    ("SA", "BJP chief: Rahul Gandhi advocates for votes of infiltrators"),
    ("SA", "Pilots' federation urges ministry to act as SpiceJet crisis deepens"),
    ("SA", "India's oil import bill up about 60% in October as crude prices rise"),
    ("NA", "Washington 38, Cincinnati 33 — Commanders upset Bengals on MNF"),
    ("OC", "De Villiers: Australia started ball-tampering before Sandpaper"),
    ("NA", "Storms and airline glitches threaten messy Thanksgiving travel"),
    ("EA", "Chinese state media hits out at 'deflation trap' warnings, defends economy"),
    ("NA", "Vance tapped as Trump's emissary to Nvidia board amid CEO turmoil"),
    ("SEA", "Myanmar's military-backed government calls ASEAN decision unfair"),
    ("ME", "Israel leadership rivals clash over Iran threat ahead of coalition talks"),
    ("NA", "Trump pauses planned detonation of degraded explosives"),
    ("SA", "Nepal PM Balendra Shah in India for economic and energy talks"),
    ("SA", "'Our Ram is incomplete without Nepal': Modi hails India-Nepal bond"),
    ("ME", "Eisenkot has until 6 Dec to build a government to replace Netanyahu"),
    ("EA", "Kospi +6.2%, Nikkei +2% as Asia rebounds on Huang's return"),
]

TIMELINE = [
    ("ASIA · MORNING", "Kospi +6.2%, Nikkei +2% as Asian stocks rebound", icon_sun),
    ("ASIA · MIDDAY", "Modi and Nepal PM flag off Saryu–Kamala Express", icon_train),
    ("EUROPE · MORNING", "GTA VI hacker sentenced; UK concert evacuated", icon_gavel),
    ("EUROPE · AFTERNOON", "NATO vows space defence; Kyiv strikes kill 14", icon_rocket),
    ("AMERICA · MORNING", "Trump DOJ speech; states sue Musk over Grok", icon_capitol),
    ("AMERICA · EVENING", "Washington 38, Cincinnati 33 to close NFL Week 11", icon_ball),
]

EXCLUDED = ("Left out — first reported on a neighbouring day: COP31 collapse "
            "(23 Nov) · CrowdStrike–Zscaler $43.9bn (23 Nov) · Democrats' "
            "258th House seat (22 Nov) · Pant 128, Wellington (22 Nov) · "
            "Peru quake (20 Nov) · ICJ Rohingya verdict (19 Nov) · Trump "
            "card-cap vow (21 Nov) · Houthi/Iran tanker strikes (21–22 Nov).")

SOURCES = ("Sources: AP, Reuters, Bloomberg, CNN, SCMP, Al Jazeera, BBC, "
           "The Times, Le Monde, The Japan Times, The Hindu, Manila Times, "
           "Arab News — 24 Nov 2026 editions.")

# Map markers: (lon, lat, label) — numbered in story order.
MARKERS = [
    (-74.0, 40.7, "1"), (30.5, 50.4, "2"), (20.1, 32.1, "3"),
    (-0.1, 51.5, "4"), (77.2, 28.6, "5"), (106.8, -6.2, "6"),
    (116.4, 39.9, "7"), (127.0, 37.5, "8"), (55.3, 25.2, "9"),
    (151.2, -33.9, "10"),
]


# ---------------------------------------------------------------- layout
MARGIN = 28
RIGHT = W - MARGIN


def region_counts():
    counts = {}
    for h in HEROES:
        counts[h["region"]] = counts.get(h["region"], 0) + 1
    for _headline, _scene, region in SECOND:
        counts[region] = counts.get(region, 0) + 1
    for region, _headline in GRID:
        counts[region] = counts.get(region, 0) + 1
    return counts


def draw_masthead(cv, fonts):
    draw_text(cv, fonts, "serif46", W // 2, 6, "THE WORLD IN ONE PAGE",
              INK, align="c", maxw=968)
    draw_text(cv, fonts, "sansb13", MARGIN, 58, "44 STORIES · 8 REGIONS",
              INK, maxw=300)
    draw_text(cv, fonts, "sansb16", W // 2, 56, "TUESDAY, 24 NOVEMBER 2026",
              RED, align="c", maxw=500)
    draw_text(cv, fonts, "sansb13", RIGHT, 58, "15 SCENES DRAWN", INK,
              align="r", maxw=300)
    cv.hline(MARGIN, 76, W - 2 * MARGIN, INK, 2)
    cv.hline(MARGIN, 79, W - 2 * MARGIN, INK, 1)


def draw_heroes(cv, fonts):
    y0, hh = 88, 216
    for i, hero in enumerate(HEROES):
        cx = MARGIN + i * 336
        cw = 320
        cv.rect(cx, y0, cw, hh, CARD)
        cv.frame(cx, y0, cw, hh, INK, 1)
        cv.set_clip(cx + 8, y0 + 8, cw - 16, 92)
        hero["scene"](cv, fonts, cx + 8, y0 + 8, cw - 16, 92)
        cv.clear_clip()
        cv.frame(cx + 8, y0 + 8, cw - 16, 92, INK, 1)
        # region chip + kicker
        cv.rect(cx + 8, y0 + 106, 10, 10, REGION_COLORS[hero["region"]])
        draw_text(cv, fonts, "sansb11", cx + 22, y0 + 105, hero["kicker"],
                  RED, maxw=cw - 30)
        lines = fonts.wrap("serif24", hero["headline"], cw - 16, max_lines=2)
        draw_lines(cv, fonts, "serif24", cx + 8, y0 + 120, lines, INK, 27,
                   cw - 16)
        deck = fonts.wrap("sans12", hero["deck"], cw - 16, max_lines=3)
        draw_lines(cv, fonts, "sans12", cx + 8, y0 + 176, deck, INK, 13,
                   cw - 16)


def draw_map(cv, fonts, map_rows):
    y0, hh = 312, 108
    x0, mw = MARGIN, 560
    cv.rect(x0, y0, mw, hh, NAVY_DARK)
    display = map_rows[::2]
    for r, row in enumerate(display):
        yy = y0 + (r * hh) // len(display)
        for c, ch in enumerate(row):
            if ch == "1":
                cv.rect(x0 + c * 4, yy, 2, 2, GOLD)
    draw_text(cv, fonts, "sansb10", x0 + 6, y0 + 4, "WHERE THE DAY HAPPENED",
              WHITE, maxw=300)
    for lon, lat, label in MARKERS:
        mx = x0 + int((lon + 180.0) / 360.0 * mw)
        my = y0 + int((85.0 - lat) / 145.0 * hh)
        cv.disc(mx, my, 8, RED)
        cv.ring(mx, my, 8, WHITE, 1)
        draw_text(cv, fonts, "sansb10", mx, my - 5, label, WHITE,
                  align="c", maxw=16)
    # region panel
    px = 604
    draw_text(cv, fonts, "sansb12", px, y0 + 2,
              "THE DAY BY REGION — 44 STORIES", INK, maxw=392)
    counts = region_counts()
    order = ["NA", "EU", "SA", "EA", "SEA", "ME", "AF", "OC"]
    cols = [order[:4], order[4:]]
    for ci, col in enumerate(cols):
        colx = px + ci * 200
        for ri, code in enumerate(col):
            ry = y0 + 22 + ri * 22
            draw_text(cv, fonts, "sansb11", colx, ry, REGION_NAMES[code],
                      INK, maxw=120)
            n = counts.get(code, 0)
            draw_text(cv, fonts, "sansb13", colx + 176, ry - 1, str(n),
                      INK, align="r", maxw=24)
            bar_w = int(n * 176 / 10)
            cv.rect(colx, ry + 13, bar_w, 5, REGION_COLORS[code])


def draw_timeline(cv, fonts):
    y0 = 428
    cv.hline(MARGIN, y0, W - 2 * MARGIN, INK, 1)
    slot_w = 161
    for i, (label, text, icon) in enumerate(TIMELINE):
        sx = MARGIN + i * slot_w
        if i:
            cv.vline(sx - 4, y0 + 4, 36, (200, 196, 186), 1)
        icon(cv, sx + 2, y0 + 5, RED)
        draw_text(cv, fonts, "sansb10", sx + 20, y0 + 8, label, RED, maxw=140)
        lines = fonts.wrap("sans10", text, slot_w - 6, max_lines=2)
        draw_lines(cv, fonts, "sans10", sx + 2, y0 + 22, lines, INK, 12,
                   slot_w - 6)
    cv.hline(MARGIN, y0 + 44, W - 2 * MARGIN, INK, 1)


def draw_second(cv, fonts):
    y0, hh = 480, 100
    for i, (headline, scene, region) in enumerate(SECOND):
        cx = MARGIN + i * 194
        cw = 188
        cv.rect(cx, y0, cw, hh, CARD)
        cv.frame(cx, y0, cw, hh, INK, 1)
        cv.rect(cx, y0, cw, 3, REGION_COLORS[region])
        cv.set_clip(cx + 6, y0 + 8, cw - 12, 40)
        scene(cv, fonts, cx + 6, y0 + 8, cw - 12, 40)
        cv.clear_clip()
        cv.frame(cx + 6, y0 + 8, cw - 12, 40, INK, 1)
        lines = fonts.wrap("sansb12", headline, cw - 12, max_lines=4)
        draw_lines(cv, fonts, "sansb12", cx + 6, y0 + 52, lines, INK, 14,
                   cw - 12)


def draw_grid(cv, fonts):
    y0 = 588
    draw_text(cv, fonts, "sansb13", MARGIN, y0, "MORE FROM THE DAY — 36 STORIES",
              INK, maxw=400)
    # colour legend, right aligned
    lx = RIGHT
    for code in ["OC", "AF", "ME", "SEA", "EA", "SA", "EU", "NA"]:
        wcode = fonts.width("sans9", code)
        lx -= wcode
        draw_text(cv, fonts, "sans9", lx, y0 + 2, code, GREY, maxw=30)
        lx -= 12
        cv.rect(lx, y0 + 3, 8, 8, REGION_COLORS[code])
        lx -= 6
    row_y = y0 + 18
    for i, (region, headline) in enumerate(GRID):
        col = i % 3
        row = i // 3
        cx = MARGIN + col * 328
        ry = row_y + row * 30
        cv.rect(cx, ry + 3, 10, 10, REGION_COLORS[region])
        lines = fonts.wrap("sansb12", headline, 296, max_lines=2)
        draw_lines(cv, fonts, "sansb12", cx + 16, ry, lines, INK, 15, 296)
        if row < 11:
            cv.hline(cx, ry + 29, 312, (224, 220, 212), 1)


def draw_footer(cv, fonts):
    y0 = 980
    draw_text(cv, fonts, "sans9", MARGIN, y0, SOURCES, GREY, maxw=968)
    draw_text(cv, fonts, "sansb10", MARGIN, y0 + 12, "DATE CHECK — ", RED,
              maxw=90)
    pre = fonts.width("sansb10", "DATE CHECK — ")
    lines = fonts.wrap("sans9", EXCLUDED, 968 - pre, max_lines=2)
    draw_lines(cv, fonts, "sans9", MARGIN + pre, y0 + 12, lines, INK, 11,
               968 - pre)


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    fonts = FontSet(base)
    with open(os.path.join(base, "map.txt"), encoding="utf-8") as f:
        map_rows = f.read().splitlines()
    total = len(HEROES) + len(SECOND) + len(GRID)
    assert total == 44, "story count %d != 44" % total
    counts = region_counts()
    assert len(counts) == 8, "regions %d != 8" % len(counts)
    assert sum(counts.values()) == 44

    cv = Canvas(W, H, PAPER)
    draw_masthead(cv, fonts)
    draw_heroes(cv, fonts)
    draw_map(cv, fonts, map_rows)
    draw_timeline(cv, fonts)
    draw_second(cv, fonts)
    draw_grid(cv, fonts)
    draw_footer(cv, fonts)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(cv, path)
    sys.stderr.write("wrote %s (%d bytes); text draws %d, width violations %d\n"
                     % (path, size, AUDIT["draws"], AUDIT["violations"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
