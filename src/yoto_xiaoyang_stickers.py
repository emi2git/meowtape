#!/usr/bin/env python3
"""Yoto card stickers for 小羊上山 levels 1–6, from each level's box-set sleeve.

    yoto-xiaoyang-stickers [folder]

<folder> (default ~/Downloads/xiao yang shang shan book/Yoto stickers) holds
sleeves/L1.jpg … L6.jpg: the publisher's box pictures (Douban), which show the
box a little turned, spine on the left. For each level:

  - the front face is cut out by its four corners and squared up
  - the card is portrait: the front's title band on top, the picture above it
    on the sleeve cropped to fill the rest — which already says 儿童汉语分级读物 N,
    so nothing is added
  - sticker cut line 52 × 83.6 mm, r 2.5 mm: 1 mm inside a Yoto card
    (54 × 85.6 mm) all round, so an imperfect hand cut still sits flat
  - 2 mm of bleed past the cut line

Writes L1.png … L6.png (300 dpi, with bleed) and yoto-stickers-A4.pdf: all six
on one A4 page, thin grey cut lines, nothing to scale when printing (print at
100% / "actual size").
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

DPI = 600
MM = DPI / 25.4
CUT_W, CUT_H, RADIUS, BLEED = 52.0, 83.6, 2.5, 2.0
TITLE_H, SCALLOP_H, STRIP_H = 11.8, 0.6, 3.0     # the title band, identical on every card

# front face corners in each sleeve picture: top-left, top-right, bottom-right, bottom-left
CORNERS = {
    1: [(431, 10), (3224, 235), (3222, 2875), (431, 3099)],
    2: [(105, 5), (800, 50), (794, 738), (105, 795)],
    3: [(128, -1), (777, 49), (777, 742), (128, 800)],
    4: [(133, 61), (758, 102), (758, 685), (133, 734)],
    5: [(234, -2), (1197, 82), (1197, 1000), (234, 1067)],
    6: [(213, 52), (1236, 118), (1237, 1073), (213, 1155)],
}
# where the picture's subject sits across its width, 0 = left edge
# (chosen so the sleeve's round badges are either whole or left out, never sliced)
FOCUS = {1: 0.71, 2: 0.47, 3: 0.41, 4: 0.495, 5: 0.52, 6: 0.685}


def px(mm):
    return int(round(mm * MM))


def perspective_coeffs(dst, src):
    a, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    return np.linalg.solve(np.array(a, float), np.array(b, float))


def front(path, q):
    im = Image.open(path).convert("RGB")
    w = (np.hypot(*np.subtract(q[1], q[0])) + np.hypot(*np.subtract(q[2], q[3]))) / 2
    h = (np.hypot(*np.subtract(q[3], q[0])) + np.hypot(*np.subtract(q[2], q[1]))) / 2
    W, H = int(w), int(h)
    f = im.transform((W, H), Image.PERSPECTIVE, perspective_coeffs([(0, 0), (W, 0), (W, H), (0, H)], q),
                     Image.BICUBIC)
    m = int(W * 0.012)                      # the box edge's soft outline
    return f.crop((m, m, W - m, H - m))


def band_top(f):
    """first row of the white title band"""
    a = np.asarray(f.convert("L")).astype(float)
    H = a.shape[0]
    white = (a > 235).mean(1)
    return next(y for y in range(int(H * .5), int(H * .9)) if white[y] > 0.8)


def rebuild_band(band, bw):
    """the title band, rebuilt at the same size on every card: its white title
    area, the scalloped edge, and the shiny coloured strip under it. The strip on
    the box carries the publishers' names in tiny type, blurred and half cut off
    by the box's bottom edge, so it's repainted as its own plain colour, column
    by column so a gradient survives."""
    a = np.asarray(band).astype(float)
    h = a.shape[0]
    white = (a.mean(2) > 235).mean(1)
    y0 = next(y for y in range(int(h * .6), h) if white[y] < 0.05)       # strip
    ys = y0
    while ys > 0 and white[ys - 1] < 0.97:                                # scallops
        ys -= 1
    strip = np.median(a[y0:], axis=0)[None].astype(np.uint8)
    parts = [band.crop((0, 0, band.width, ys)).resize((bw, px(TITLE_H)), Image.LANCZOS),
             band.crop((0, ys, band.width, y0)).resize((bw, px(SCALLOP_H)), Image.LANCZOS),
             Image.fromarray(strip).resize((bw, px(STRIP_H)), Image.LANCZOS)]
    out = Image.new("RGB", (bw, sum(p.height for p in parts)), "white")
    y = 0
    for part in parts:
        out.paste(part, (0, y))
        y += part.height
    return out


def card(level, sleeves):
    f = front(sleeves / f"L{level}.jpg", CORNERS[level])
    W, H = f.size
    top = band_top(f)
    art, band = f.crop((0, 0, W, top)), f.crop((0, top, W, H))

    cw, ch = px(CUT_W + 2 * BLEED), px(CUT_H + 2 * BLEED)
    # the band spans the cut width exactly (its text must not be cut); bleed is
    # its own edge pixels stretched outward
    bw = px(CUT_W)
    band = rebuild_band(band, bw)
    bh = band.height
    out = Image.new("RGB", (cw, ch), "white")
    b = px(BLEED)
    # title band on top, bleed above it is its own top row stretched
    out.paste(band, (b, b))
    # (a few rows in: the very top row carries specks of the box edge)
    top_row = band.crop((0, 4, bw, 5)).filter(ImageFilter.MedianFilter(9))
    out.paste(top_row.resize((bw, b)), (b, 0))
    out.paste(band.crop((0, 0, 1, bh)).resize((b, bh)), (0, b))
    out.paste(band.crop((bw - 1, 0, bw, bh)).resize((b, bh)), (b + bw, b))
    out.paste(Image.new("RGB", (b, b), top_row.getpixel((0, 0))), (0, 0))
    out.paste(Image.new("RGB", (b, b), top_row.getpixel((bw - 1, 0))), (cw - b, 0))
    # picture: everything under the band, bleed included, keeping its top-left anchored
    # to the band so the sky meets the strip
    ah = ch - b - bh
    scale = max(cw / art.width, ah / art.height)
    aw = int(art.width * scale)
    art = art.resize((aw, int(art.height * scale)), Image.LANCZOS)
    x = int(np.clip(FOCUS[level] * aw - cw / 2, 0, aw - cw))
    print(f"L{level}: picture {x / aw:.2f}–{(x + cw) / aw:.2f} of its width, {DPI / scale:.0f} source dpi")
    out.paste(art.crop((x, art.height - ah, x + cw, art.height)), (0, b + bh))
    return out


def main():
    if sys.argv[1:2] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path.home() / "Downloads/xiao yang shang shan book/Yoto stickers"
    sleeves = folder / "sleeves"
    cards = {n: card(n, sleeves) for n in range(1, 7)}
    for n, c in cards.items():
        c.save(folder / f"L{n}.png", dpi=(DPI, DPI))

    # A4 sheet: 3 × 2, cut lines on top of the art
    page = Image.new("RGB", (px(210), px(297)), "white")
    d = ImageDraw.Draw(page)
    gap = 8.0
    cols, rows = 3, 2
    x0 = (210 - cols * CUT_W - (cols - 1) * gap) / 2
    y0 = 20.0
    for i, n in enumerate(range(1, 7)):
        cx = x0 + (i % cols) * (CUT_W + gap)
        cy = y0 + (i // cols) * (CUT_H + gap)
        page.paste(cards[n], (px(cx - BLEED), px(cy - BLEED)))
    # bleed from neighbours never overlaps (gap 8 mm > 2 × 2 mm); white gutters between
    for i in range(6):
        cx = x0 + (i % cols) * (CUT_W + gap)
        cy = y0 + (i // cols) * (CUT_H + gap)
        d.rounded_rectangle([px(cx), px(cy), px(cx + CUT_W), px(cy + CUT_H)], radius=px(RADIUS),
                            outline=(150, 150, 150), width=max(2, DPI // 150))
    note_y = y0 + rows * (CUT_H + gap) + 2
    font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", px(3))
    d.text((px(x0), px(note_y)), "小羊上山 Yoto stickers · print at 100% (actual size) · cut on the grey lines · "
           f"{CUT_W:g} × {CUT_H:g} mm", fill=(120, 120, 120), font=font)
    page.save(folder / "yoto-stickers-A4.pdf", resolution=DPI)
    page.resize((page.width // 3, page.height // 3), Image.LANCZOS).save(folder / "preview-A4.png")
    print(f"6 cards → {folder}")


if __name__ == "__main__":
    main()
