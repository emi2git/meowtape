#!/usr/bin/env python3
"""Yoto icons for the 小羊上山 recordings — 16×16, the size a Yoto Mini shows.

One lamb on a mountain, with the middle six rows left empty so a track number
can sit there. Writes the empty one plus a numbered one per track, and a big
preview sheet to look at them with, since 16 px is unreadable on a Mac screen.

    yoto-xiaoyang-icons [out dir] [how many tracks]

Icons are PNGs with a transparent background: on the player that reads as black,
so everything here is drawn in colours that carry against it.
"""

import sys
from pathlib import Path

from PIL import Image

# ── the picture ─────────────────────────────────────────────────────────────
# .  nothing (transparent)      W  wool        d  face and legs
# g  sunlit slope               G  slope       s  snow
# y  sun
# A lamb seen head-on. Sixteen pixels is too few for a body, four legs and a
# head that still reads as a sheep — a face does: ears out to the sides, two
# eyes, a muzzle. The sun went, too; at this size every extra thing costs
# clarity.
ART = [
    ".....WWWWWW.....",
    "....WWWWWWWW....",
    "..wwWWdWWdWWww..",   # ears out to the sides, eyes in
    "....WWWWWWWW....",
    ".....WWddWW.....",   # muzzle
    "......WWWW......",
    "................",
    "................",   # ┐
    "................",   # │
    "................",   # ├ the track number goes here
    "................",   # │
    "................",   # ┘
    "................",
    "...gsg....gsg...",
    "..ggggg..ggggg..",
    "GGGGGGGGGGGGGGGG",
]

INK = {
    "W": (255, 255, 255, 255),
    "w": (198, 198, 198, 255),
    "d": (74, 74, 74, 255),
    "g": (94, 178, 74, 255),
    "G": (47, 125, 50, 255),
    "s": (255, 255, 255, 255),
    "y": (255, 201, 74, 255),
}

NUMBER = (255, 255, 255, 255)

# 3×5 digits — the largest that leaves both numerals room side by side
DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}

TOP = 7          # first free row
LEFT = 4         # first column of the left numeral (3 wide, 1 gap, 3 wide)


def base():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(ART):
        for x, ch in enumerate(row):
            if ch in INK:
                px[x, y] = INK[ch]
    return img


def numbered(n):
    """The same icon with n printed across its empty middle."""
    img = base()
    px = img.load()
    text = "%02d" % n
    for i, ch in enumerate(text[-2:]):
        ox = LEFT + i * 4
        for dy, row in enumerate(DIGITS[ch]):
            for dx, bit in enumerate(row):
                if bit == "1":
                    px[ox + dx, TOP + dy] = NUMBER
    return img


def preview(icons, scale=22, pad=6):
    """All of them side by side, blown up, on the player's black."""
    w = (16 * scale + pad) * len(icons) + pad
    sheet = Image.new("RGBA", (w, 16 * scale + pad * 2), (17, 17, 17, 255))
    for i, ic in enumerate(icons):
        big = ic.resize((16 * scale, 16 * scale), Image.NEAREST)
        sheet.alpha_composite(big, (pad + i * (16 * scale + pad), pad))
    return sheet


def main():
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Library/CloudStorage/SynologyDrive-SynologySync/mp3/yoto-icons")
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    out.mkdir(parents=True, exist_ok=True)

    made = [base()]
    made[0].save(out / "xiaoyang-base.png")
    for n in range(1, count + 1):
        ic = numbered(n)
        ic.save(out / ("xiaoyang-%02d.png" % n))
        made.append(ic)

    preview(made).save(out / "xiaoyang-preview.png")
    print("%d icons → %s" % (len(made), out))


if __name__ == "__main__":
    main()
