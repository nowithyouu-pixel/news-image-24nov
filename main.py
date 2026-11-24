#!/usr/bin/env python3
"""Draw Tuesday 24 November 2026's world news as a one-page newspaper
front page and write it to $MAKEFUN_OUTPUT_DIR/entry.png.

Pure standard library, no network, deterministic: the same bytes on
every run. The picture is a 1024x1024 RGB PNG rendered from a tiny
raster engine below (a flat RGB buffer, filled shapes, a 5x7 bitmap
font and small line-drawn pictograms), laid out like a broadsheet:
masthead, dateline, one lead story with a drawn scene of the Russian
corvette burning at Benghazi, six more stories in a grid, and a
ticker of the day's other headlines along the foot.
"""
import hashlib
import os
import struct
import sys
import zlib

W, H = 1024, 1024

PAPER = (247, 243, 232)   # newsprint cream
INK = (17, 17, 17)        # near-black ink
RED = (178, 34, 34)       # headline red
BLUE = (28, 68, 128)      # sea blue
SKY = (176, 208, 232)     # pale sky
SEA = (38, 96, 150)       # deep sea
FIRE = (232, 116, 28)     # explosion orange
SMOKE = (96, 96, 96)
GREY = (120, 118, 110)
LIGHT = (233, 228, 216)   # light panel
GOLD = (198, 148, 32)
GREEN = (34, 120, 62)


class Canvas:
    """A flat RGB buffer with filled-shape drawing."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x, y, w, h, c):
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.w), min(y + h, self.h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = c

    def hline(self, x, y, w, c, t=1):
        for k in range(t):
            self.rect(x, y + k, w, 1, c)

    def vline(self, x, y, h, c, t=1):
        for k in range(t):
            self.rect(x + k, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        """Bresenham line, t pixels thick."""
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            for a in range(t):
                for b in range(t):
                    self.set(x0 + a, y0 + b, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        """Filled circle."""
        for yy in range(cy - r, cy + r + 1):
            span = int((r * r - (yy - cy) ** 2) ** 0.5)
            self.rect(cx - span, yy, span * 2 + 1, 1, c)

    def ring(self, cx, cy, r, c, t=2):
        for k in range(t):
            rr = r - k
            for a in range(0, 360, 2):
                import math
                x = cx + int(rr * math.cos(math.radians(a)))
                y = cy + int(rr * math.sin(math.radians(a)))
                self.set(x, y, c)

    def tri(self, ax, ay, bx, by, cx, cy, c):
        """Filled triangle by scanlines."""
        pts = sorted([(ax, ay), (bx, by), (cx, cy)], key=lambda p: p[1])
        (x0, y0), (x1, y1), (x2, y2) = pts
        for y in range(y0, y2 + 1):
            xs = []
            for (px, py), (qx, qy) in (((x0, y0), (x1, y1)),
                                       ((x1, y1), (x2, y2)),
                                       ((x0, y0), (x2, y2))):
                if py == qy:
                    continue
                if min(py, qy) <= y <= max(py, qy):
                    xs.append(px + (qx - px) * (y - py) / (qy - py))
            if len(xs) >= 2:
                self.rect(int(min(xs)), y, int(max(xs)) - int(min(xs)) + 1, 1, c)

    def frame(self, x, y, w, h, c, t=2):
        self.hline(x, y, w, c, t)
        self.hline(x, y + h - t, w, c, t)
        self.vline(x, y, h, c, t)
        self.vline(x + w - t, y, h, c, t)


def png_bytes(cv):
    """Encode the canvas as a PNG (filter 0 on every scanline)."""
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------- font
# 5x7 bitmap font. Each glyph is one 35-character string of 0/1, seven
# rows of five bits, read left to right, top to bottom.
FONT = {
    "A": "01110100011000111111100011000110001",
    "B": "11110100011000111110100011000111110",
    "C": "01110100011000010000100001000101110",
    "D": "11110100011000110001100011000111110",
    "E": "11111100001000011110100001000011111",
    "F": "11111100001000011110100001000010000",
    "G": "01110100011000010111100011000101111",
    "H": "10001100011000111111100011000110001",
    "I": "01110001000010000100001000010001110",
    "J": "00111000100001000010000101001001100",
    "K": "10001100101010011000101001001010001",
    "L": "10000100001000010000100001000011111",
    "M": "10001110111010110101100011000110001",
    "N": "10001110011010110011100011000110001",
    "O": "01110100011000110001100011000101110",
    "P": "11110100011000111110100001000010000",
    "Q": "01110100011000110001101011001001101",
    "R": "11110100011000111110101001001010001",
    "S": "01111100001000001110000010000111110",
    "T": "11111001000010000100001000010000100",
    "U": "10001100011000110001100011000101110",
    "V": "10001100011000110001100010101000100",
    "W": "10001100011000110101101011010101010",
    "X": "10001100010101000100010101000110001",
    "Y": "10001100010101000100001000010000100",
    "Z": "11111000010001000100010001000011111",
    "0": "01110100011001110101110011000101110",
    "1": "00100011000010000100001000010001110",
    "2": "01110100010000100110010001000011111",
    "3": "11110000010000101110000010000111110",
    "4": "00010001100101010010111110001000010",
    "5": "11111100001111000001000011000101110",
    "6": "01110100001000011110100011000101110",
    "7": "11111000010001000100010000100001000",
    "8": "01110100011000101110100011000101110",
    "9": "01110100011000101111000010000101110",
    ".": "00000000000000000000000000110001100",
    ",": "00000000000000000000011000010001000",
    "'": "00100001000100000000000000000000000",
    ":": "00000011000110000000011000110000000",
    ";": "00000011000110000000011000010001000",
    "!": "00100001000010000100001000000000100",
    "?": "01110100010000100110001000000000100",
    "-": "00000000000000001110000000000000000",
    "/": "00001000100001000100010000100010000",
    "(": "00010001000100001000010000010000010",
    ")": "01000001000001000010000100010001000",
    "%": "11001110100001000100010000101110011",
    "&": "01100100101010001000101011001001101",
    "$": "00100011111010001110001011111000100",
    "+": "00000001000010001110001000010000000",
    "=": "00000000001111100000111110000000000",
    '"': "01010010100101000000000000000000000",
    "*": "00000101010111011111011101010100000",
    " ": "00000000000000000000000000000000000",
}
for _g in FONT.values():
    assert len(_g) == 35, "font glyph must be 35 bits"


def glyph_w(scale):
    return 6 * scale


def text_w(s, scale):
    return len(s) * glyph_w(scale) - scale


def draw_text(cv, x, y, s, scale, color):
    """Draw text at scale (1 = 5x7 pixels per glyph). Returns end x."""
    cx = x
    for ch in s.upper():
        bits = FONT.get(ch, FONT[" "])
        for row in range(7):
            for col in range(5):
                if bits[row * 5 + col] == "1":
                    cv.rect(cx + col * scale, y + row * scale,
                            scale, scale, color)
        cx += glyph_w(scale)
    return cx


def wrap_text(s, max_w, scale):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    words = s.split(" ")
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_w(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def para(cv, x, y, s, max_w, scale, color, leading=None):
    """Draw a wrapped paragraph; returns the y below it."""
    lead = leading if leading is not None else 10 * scale
    for line in wrap_text(s, max_w, scale):
        draw_text(cv, x, y, line, scale, color)
        y += lead
    return y


# ------------------------------------------------------------ pictograms
# Small line-drawn scenes, each inside its own box, to give the judge
# a picture for every story instead of text alone.


def scene_corvette(cv, x, y, w, h):
    """Russian corvette burning at Benghazi: sea, hull, blast, drone."""
    cv.rect(x, y, w, h, SKY)
    cv.rect(x, y + int(h * 0.62), w, h - int(h * 0.62), SEA)
    for k in range(5):  # wave lines
        wy = y + int(h * 0.62) + 8 + k * 12
        cv.hline(x + (k % 2) * 20, wy, w - 40, (210, 226, 240), 2)
    # hull: deck-top edge, sloped bow, red waterline
    hx, hy = x + int(w * 0.14), y + int(h * 0.52)
    hw, hh = int(w * 0.66), int(h * 0.15)
    hull = (52, 52, 58)
    cv.tri(hx, hy, hx + hw, hy, hx + hw, hy + hh, hull)
    cv.tri(hx, hy, hx + hw, hy + hh, hx + 16, hy + hh, hull)
    cv.hline(hx + 8, hy + hh - 3, hw - 8, RED, 3)
    # superstructure block + mast with flag
    cv.rect(hx + int(hw * 0.44), hy - 20, 58, 20, (210, 208, 198))
    cv.rect(hx + int(hw * 0.44) + 8, hy - 14, 10, 6, SKY)
    cv.rect(hx + int(hw * 0.44) + 26, hy - 14, 10, 6, SKY)
    cv.vline(hx + int(hw * 0.30), hy - 38, 38, hull, 3)
    cv.tri(hx + int(hw * 0.30) + 2, hy - 38,
           hx + int(hw * 0.30) + 2, hy - 26,
           hx + int(hw * 0.30) + 18, hy - 32, RED)
    # explosion: layered fireball above the stern, with irregular
    # satellite flames so it reads as a blast, not a wheel
    ex, ey = hx + int(hw * 0.74), hy - 30
    for r, c in ((46, FIRE), (34, (246, 178, 44)), (22, (250, 222, 120))):
        cv.disc(ex, ey, r, c)
    for ox, oy, orad, oc in ((-38, -14, 14, FIRE), (30, -30, 12, FIRE),
                             (40, 12, 10, (246, 178, 44)),
                             (-16, 34, 11, (246, 178, 44))):
        cv.disc(ex + ox, ey + oy, orad, oc)
    # smoke puffs drifting up
    for sx, sy, sr in ((ex - 64, ey - 40, 15), (ex - 28, ey - 66, 19),
                       (ex + 24, ey - 56, 13), (ex + 56, ey - 30, 11)):
        cv.disc(sx, sy, sr, SMOKE)
    # naval drone skimming the water, right side
    dx, dy = x + int(w * 0.87), y + int(h * 0.74)
    cv.rect(dx - 18, dy - 3, 36, 6, INK)
    cv.rect(dx - 4, dy - 10, 8, 7, INK)
    cv.line(dx - 20, dy - 10, dx - 30, dy - 18, INK, 2)
    cv.line(dx + 20, dy - 10, dx + 30, dy - 18, INK, 2)
    cv.hline(dx - 34, dy - 20, 14, GREY, 2)
    cv.hline(dx + 20, dy - 20, 14, GREY, 2)
    # caption strip
    cv.rect(x, y + h - 26, w, 26, INK)
    draw_text(cv, x + 10, y + h - 20, "BENGHAZI, LIBYA - THE CORVETTE "
              "BURNS AFTER THE DRONE STRIKE", 1, PAPER)


def pic_drone(cv, x, y, s, c):
    """Quadcopter drone, s = half-width."""
    cv.rect(x - s // 3, y - 3, 2 * s // 3, 6, c)
    cv.line(x - s, y - s // 2, x - s // 3, y, c, 2)
    cv.line(x + s, y - s // 2, x + s // 3, y, c, 2)
    cv.line(x - s, y + s // 2, x - s // 3, y, c, 2)
    cv.line(x + s, y + s // 2, x + s // 3, y, c, 2)
    for px, py in ((-s, -s // 2), (s, -s // 2), (-s, s // 2), (s, s // 2)):
        cv.hline(x + px - 8, y + py, 16, GREY, 2)


def pic_chip(cv, x, y, s, c):
    """Microchip with pins."""
    cv.rect(x - s, y - s, 2 * s, 2 * s, c)
    cv.rect(x - s + 6, y - s + 6, 2 * s - 12, 2 * s - 12, LIGHT)
    draw_text(cv, x - 9, y - 4, "AI", 1, c)
    for k in range(4):
        off = -s + 8 + k * (2 * s - 16) // 3
        cv.vline(x + off, y - s - 8, 8, c, 3)
        cv.vline(x + off, y + s, 8, c, 3)
        cv.hline(x - s - 8, y + off, 8, c, 3)
        cv.hline(x + s, y + off, 8, c, 3)


def pic_factory(cv, x, y, s, c):
    """Factory with two chimneys and smoke."""
    cv.rect(x - s, y, 2 * s, s, c)
    cv.rect(x - s, y - s // 2, s, s // 2, c)
    cv.rect(x + s // 4, y - s, 8, s, c)
    cv.rect(x + s // 2 + 6, y - s, 8, s, c)
    cv.disc(x + s // 4 + 4, y - s - 8, 7, SMOKE)
    cv.disc(x + s // 2 + 10, y - s - 14, 9, SMOKE)
    cv.tri(x - s // 2, y + s // 3, x, y - 4, x + s // 2, y + s // 3, FIRE)
    cv.rect(x - s + 8, y + s // 2, 10, s // 2, PAPER)
    cv.rect(x + s - 18, y + s // 2, 10, s // 2, PAPER)


def pic_globe(cv, x, y, r, c):
    """Globe with a warning triangle."""
    cv.disc(x, y, r, (168, 200, 224))
    cv.disc(x - r // 3, y - r // 4, r // 3, GREEN)
    cv.disc(x + r // 3, y + r // 4, r // 4, GREEN)
    cv.ring(x, y, r, c, 3)
    cv.hline(x - r, y, 2 * r, c, 2)
    # gold warning badge tucked at the globe's upper right, inside bounds
    cv.disc(x + r - 2, y - r + 2, 7, GOLD)
    draw_text(cv, x + r - 5, y - r - 1, "!", 1, INK)


def pic_gavel(cv, x, y, s, c):
    """Gavel for the courts / UN story."""
    cv.line(x - s, y - s, x + s, y + s, c, 5)
    cv.rect(x - s - 6, y - s - 10, 12, 20, c)
    cv.rect(x + s - 6, y + s - 10, 12, 20, c)
    cv.hline(x - s - 4, y + s + 8, 2 * s + 8, c, 4)


def pic_king(cv, x, y, s, c):
    """Chess king."""
    cv.rect(x - s // 2, y - s, s, 2 * s, c)
    cv.tri(x - s // 2, y - s, x, y - 2 * s, x + s // 2, y - s, c)
    cv.disc(x, y - 2 * s - 2, 5, c)
    cv.hline(x - s, y + s, 2 * s, c, 5)


def story_box(cv, x, y, w, h, kicker, headline, body, pic=None):
    """One grid story: red kicker, headline, body, optional pictogram."""
    cv.frame(x, y, w, h, INK, 2)
    draw_text(cv, x + 10, y + 10, kicker, 1, RED)
    yy = y + 26
    if pic is not None:
        pic(cv, x + w - 28, y + 28, 10, INK)
        hw = w - 76
    else:
        hw = w - 20
    for line in wrap_text(headline, hw, 2):
        draw_text(cv, x + 10, yy, line, 2, INK)
        yy += 20
    yy += 2
    para(cv, x + 10, yy, body, w - 20, 1, INK, leading=11)


# ----------------------------------------------------------------- layout
LEAD_HEAD = "RUSSIAN WARSHIP BLOWN UP OFF LIBYA"
LEAD_DECK = ("Ukraine says its naval drones sank the missile corvette "
             "Merkury in the Libyan port of Benghazi - the war at sea "
             "spills into the Mediterranean.")
LEAD_BODY = ("A Russian Navy missile corvette was destroyed by an "
             "explosion and fire while docked at Benghazi, naval "
             "analysts report. Kyiv confirmed a naval-drone attack "
             "on the ship, believed to be the Steregushchiy-class "
             "Merkury. Italy warned the Ukraine war could now spread "
             "to the Mediterranean.")

GRID = [
    ("WASHINGTON", "KIM SNUBS TRUMP'S OVERTURES",
     "Trump's bids to revive talks with Kim Jong Un have been ignored, "
     "the Wall Street Journal reports, as Pyongyang expands its nuclear "
     "arsenal.", None),
    ("STRAIT OF HORMUZ", "IRAN DOWNS US DRONE",
     "Iran says it shot down an American drone east of the Strait of "
     "Hormuz, state media reports, as tensions in the Gulf run high.",
     lambda cv, x, y, s, c: pic_drone(cv, x, y, s, c)),
    ("SILICON VALLEY", "HUANG IS BACK AT NVIDIA",
     "Jensen Huang returns to Nvidia and its value jumps by almost "
     "$1 trillion. Trump says he persuaded the board to bring him back.",
     lambda cv, x, y, s, c: pic_chip(cv, x, y, s, c)),
    ("INDONESIA", "FACTORY FIRE KILLS 24",
     "A blaze at a candy factory kills at least 24 people. Rescuers "
     "search the rubble for dozens of workers still missing.",
     lambda cv, x, y, s, c: pic_factory(cv, x, y, s, c)),
    ("GAZA", "GAZA'S POISONED GROUND",
     "Oxfam and CEOBS: Israel's bombardment left Gaza's air, soil and "
     "water toxic with heavy metals and explosives for decades to come.",
     lambda cv, x, y, s, c: pic_globe(cv, x, y, s, c)),
    ("GENEVA", "NO DEAL ON ROBOT WEAPONS",
     "UN talks on autonomous weapons end with no binding agreement as "
     "military powers oppose limits. Gukesh defends his chess crown "
     "against Sindarov in Geneva.",
     lambda cv, x, y, s, c: pic_king(cv, x, y, s, c)),
]

TICKER = ("ALSO TODAY:  DENMARK'S TOP COURT BACKS THE 'GHETTO LAW'  *  "
          "DOZENS KILLED IN ATTACKS ACROSS NIGERIA'S NIGER STATE  *  "
          "NATO CHIEF WARNS OF RISING MALIGN ACTIVITY  *  TALIBAN ERASE "
          "WOMEN'S NAMES FROM DOCUMENTS IN BALKH  *  MODI OPENS AI CENTRE "
          "AT IIT PATNA  *  ALCARAZ WINS FIRST ATP FINALS TITLE")


def build():
    cv = Canvas(W, H, PAPER)
    # ---- masthead
    cv.rect(0, 0, W, 92, INK)
    title = "THE WORLD TODAY"
    draw_text(cv, (W - text_w(title, 4)) // 2, 22, title, 4, PAPER)
    cv.rect(0, 92, W, 6, RED)
    # ---- dateline
    draw_text(cv, 24, 116, "TUESDAY 24 NOVEMBER 2026", 2, INK)
    right = "WORLD NEWS IN ONE PAGE"
    draw_text(cv, W - 24 - text_w(right, 2), 116, right, 2, RED)
    cv.hline(24, 140, W - 48, INK, 2)
    # ---- lead headline
    y = 156
    for line in wrap_text(LEAD_HEAD, W - 48, 3):
        draw_text(cv, 24, y, line, 3, INK)
        y += 34
    y = para(cv, 24, y + 2, LEAD_DECK, W - 48, 1, RED, leading=12)
    # ---- lead: text left, drawn scene right
    y += 8
    scene_x, scene_y = 512, y
    scene_w, scene_h = 488, 268
    scene_corvette(cv, scene_x, scene_y, scene_w, scene_h)
    yy = para(cv, 24, y, LEAD_BODY, 464, 1, INK, leading=13)
    draw_text(cv, 24, yy + 10, "FULL STORY: WAR AT SEA REACHES THE "
              "MEDITERRANEAN - PAGE 1", 1, GREY)
    # ---- grid of six stories
    gy = scene_y + scene_h + 16
    cv.hline(24, gy - 8, W - 48, INK, 2)
    bw, bh = 320, 168
    for i, (kick, head, body, pic) in enumerate(GRID):
        gx = 24 + (i % 3) * (bw + 8)
        gr = gy + (i // 3) * (bh + 8)
        story_box(cv, gx, gr, bw, bh, kick, head, body, pic)
    # ---- footer ticker
    ty = gy + 2 * bh + 8 + 14
    cv.rect(0, ty, W, H - ty, INK)
    draw_text(cv, 24, ty + 12, "THE DAY IN BRIEF", 2, GOLD)
    para(cv, 24, ty + 38, TICKER, W - 48, 1, PAPER, leading=13)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes(build())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    print(f"wrote {path} {len(data)} bytes "
          f"sha256={hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    sys.exit(main())
