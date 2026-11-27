#!/usr/bin/env python3
"""Yoto art for the Vietnamese song cards: a 16×16 pixel icon and a cover each.

    yoto-card-art [out dir]

For every card in CARDS writes <out>/<card>/icon.png (16×16, transparent — the
player shows it on black, so everything is drawn in colours that carry there),
cover.png (638×1011, the shape of a Yoto card) and preview.png (the icon blown
up, for looking at on a Mac). The cover is the same pixel art, large, over the
card's colour, with the title under it — so the card and the player match.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── the pixels ──────────────────────────────────────────────────────────────
# One grid per card; '.' is transparent, every other letter is looked up in INK.
ART = {
    # a cassette — what the 2000s played on
    "Vietnamese 2000s": [
        "................",
        "................",
        "................",
        ".oooooooooooooo.",
        ".oLLLLLLLLLLLLo.",
        ".oLrrrrrrrrrrLo.",
        ".oLLLLLLLLLLLLo.",
        ".oLLwwLLLLwwLLo.",
        ".oLwkkwLLwkkwLo.",
        ".oLLwwLLLLwwLLo.",
        ".oLLLLLLLLLLLLo.",
        ".ooookkkkkkoooo.",
        ".oookkkkkkkkooo.",
        ".oooooooooooooo.",
        "................",
        "................",
    ],
    # headphones — the 2010s of phones and earbuds
    "Vietnamese 2010s": [
        "................",
        ".....hhhhhh.....",
        "...hhhhhhhhhh...",
        "..hhh......hhh..",
        "..hh........hh..",
        ".hh..........hh.",
        ".hh..........hh.",
        ".hh...n......hh.",
        "ccch..nn....hccc",
        "cCch..n.n...hcCc",
        "cCch..n.....hcCc",
        "cCch.nn.....hcCc",
        "cCch.nn.....hcCc",
        "ccch........hccc",
        ".cc..........cc.",
        "................",
    ],
    # a phone playing — streaming, the 2020s
    "Vietnamese 2020s": [
        "....pppppppp....",
        "....pSSSSSSp....",
        "....pSSSSSSp....",
        "....pSSwwSSp....",
        "....pSSwwwSp....",
        "....pSSwSwwp....",
        "....pSSwSSSp....",
        "....pSSwSSSp....",
        "....pSwwSSSp....",
        "....pwwwSSSp....",
        "....pwwSSSSp....",
        "....pSSSSSSp....",
        "....pSSSSSSp....",
        "....pppppppp....",
        "....ppp..ppp....",
        "....pppppppp....",
    ],
    # đèn ông sao — the star lantern every Vietnamese child carries at Trung Thu
    "Vietnamese Kids": [
        ".......yy.......",
        ".......yy.......",
        "......yRRy......",
        "......yRRy......",
        "yyyyyyRRRRyyyyyy",
        ".yRRRRRRRRRRRRy.",
        "..yRRRRRRRRRRy..",
        "...yRRRRRRRRy...",
        "....yRRRRRRy....",
        "....yRRRRRRy....",
        "...yRRRyyRRRy...",
        "...yRRy..yRRy...",
        "..yRy..b...yRy..",
        "..yy...b....yy..",
        ".......b........",
        ".......b........",
    ],
}

INK = {
    "o": (240, 132, 48, 255),   # cassette shell
    "L": (255, 236, 196, 255),  # label
    "r": (216, 40, 40, 255),    # label stripe
    "w": (255, 255, 255, 255),
    "k": (70, 70, 80, 255),     # reels, tape window
    "h": (70, 170, 255, 255),   # headband
    "c": (40, 110, 220, 255),   # ear cup
    "C": (140, 200, 255, 255),
    "n": (255, 214, 70, 255),   # music note
    "p": (200, 200, 215, 255),  # phone body
    "S": (160, 60, 220, 255),   # screen
    "y": (255, 214, 40, 255),   # lantern edge
    "R": (230, 30, 40, 255),    # lantern paper
    "b": (150, 100, 50, 255),   # stick
}

CARDS = {  # title on the cover, subtitle, background
    "Vietnamese 2000s": ("Nhạc Việt", "2000s", (32, 44, 70)),
    "Vietnamese 2010s": ("Nhạc Việt", "2010s", (20, 34, 58)),
    "Vietnamese 2020s": ("Nhạc Việt", "2020s", (40, 20, 60)),
    "Vietnamese Kids": ("Nhạc Thiếu Nhi", "Vietnamese Kids", (14, 72, 84)),
}

COVER = (638, 1011)
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"   # has Vietnamese


def icon(name):
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(ART[name]):
        assert len(row) == 16, (name, y)
        for x, ch in enumerate(row):
            if ch != ".":
                px[x, y] = INK[ch]
    return img


def cover(name, ic):
    title, sub, bg = CARDS[name]
    img = Image.new("RGB", COVER, bg)
    d = ImageDraw.Draw(img)
    # pixel grid backdrop, faint, so the big icon reads as pixel art
    step = 32
    grid = tuple(min(255, c + 10) for c in bg)
    for x in range(0, COVER[0], step):
        d.line([(x, 0), (x, COVER[1])], fill=grid)
    for y in range(0, COVER[1], step):
        d.line([(0, y), (COVER[0], y)], fill=grid)
    big = ic.resize((16 * 30, 16 * 30), Image.NEAREST)
    img.paste(big, ((COVER[0] - big.width) // 2, 110), big)
    for text, size, y in ((title, 78, 660), (sub, 64, 770)):
        f = ImageFont.truetype(FONT, size)
        w = d.textlength(text, font=f)
        d.text(((COVER[0] - w) / 2, y), text, font=f, fill=(255, 255, 255))
    return img


def main():
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Library/CloudStorage/SynologyDrive-SynologySync/mp3/.yoto-art")
    for name in ART:
        dst = out / name
        dst.mkdir(parents=True, exist_ok=True)
        ic = icon(name)
        ic.save(dst / "icon.png")
        cover(name, ic).save(dst / "cover.png")
        prev = Image.new("RGBA", (16 * 20, 16 * 20), (0, 0, 0, 255))
        prev.alpha_composite(ic.resize(prev.size, Image.NEAREST))
        prev.save(dst / "preview.png")
    print("art →", out)


if __name__ == "__main__":
    main()
