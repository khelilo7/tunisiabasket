"""The brand pieces every poster shares: the header (mark, TUNISIA BASKET, a subtitle) and the footer (tunisiabasket.com). Lettering: Barlow Condensed (assets/brand/fonts, SIL OFL)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "brand" / "fonts"
TEXT, MUTED, BRIGHT_RED = (244, 246, 251), (150, 160, 185), (238, 75, 82)


def font(kind, size):
    return ImageFont.truetype(str(FONTS / ("BarlowCondensed-ExtraBold.ttf" if kind == "black" else "BarlowCondensed-SemiBold.ttf")), size)


def spaced(d, x, y, s, f, fill, track, anchor="l"):
    """Capitals with extra letter spacing (baseline y); anchor l / m / r on x."""
    w = sum(d.textlength(c, font=f) for c in s) + track * (len(s) - 1)
    x0 = x if anchor == "l" else x - w / 2 if anchor == "m" else x - w
    for c in s:
        d.text((x0, y), c, font=f, fill=fill, anchor="ls")
        x0 += d.textlength(c, font=f) + track
    return w


def mark(size):
    return Image.open(ROOT / "static" / "img" / "logo.png").convert("RGBA").resize((size, size), Image.LANCZOS)


def lockup(img, x, y, size, align="l"):
    """The mark and TUNISIA BASKET (BASKET in the logo red) with the mark's top at y; returns the width."""
    f = font("black", int(size * 0.62))
    d = ImageDraw.Draw(img)
    w1, w2 = d.textlength("TUNISIA ", font=f), d.textlength("BASKET", font=f)
    total = size + 14 + w1 + w2
    x0 = x if align == "l" else x - total / 2
    img.alpha_composite(mark(size), (int(x0), int(y)))
    base = y + size * 0.74
    d.text((x0 + size + 14, base), "TUNISIA ", font=f, fill=TEXT, anchor="ls")
    d.text((x0 + size + 14 + w1, base), "BASKET", font=f, fill=BRIGHT_RED, anchor="ls")
    return total


def header(img, subtitle, M=48, y=36, size=64, right=None):
    """The top-left brand with a spaced subtitle under it; right = [(text, y, kind, size, fill)] drawn against the right margin."""
    d = ImageDraw.Draw(img)
    lockup(img, M, y, size)
    spaced(d, M + size + 14, y + size + 18, subtitle, font("semi", 25), MUTED, 3)
    for text, ty, kind, sz, fill in right or []:
        d.text((img.width - M, ty), text, font=font(kind, sz), fill=fill, anchor="rs")


def footer(img):
    """tunisiabasket.com centred at the bottom, with the mark."""
    W, H = img.size
    d = ImageDraw.Draw(img)
    f = font("black", 44)
    wa, wb, wc = d.textlength("tunisia", font=f), d.textlength("basket", font=f), d.textlength(".com", font=f)
    x0 = (W - (46 + 12 + wa + wb + wc)) / 2
    img.alpha_composite(mark(46), (int(x0), H - 72))
    y = H - 33
    d.text((x0 + 58, y), "tunisia", font=f, fill=TEXT, anchor="ls")
    d.text((x0 + 58 + wa, y), "basket", font=f, fill=BRIGHT_RED, anchor="ls")
    d.text((x0 + 58 + wa + wb, y), ".com", font=f, fill=TEXT, anchor="ls")
