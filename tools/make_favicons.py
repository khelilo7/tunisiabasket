"""Rebuilds the site icons from the logo. The full logo has its name written under the emblem, which is unreadable at 16-48 px; the icons use the
emblem only (the ball with the Tunisian crescent and the map) on a dark rounded square. Search engines want a square icon whose side is a
multiple of 48 px. Run from the project folder: python tools/make_favicons.py"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "static" / "img" / "logo.png"
BG = (15, 20, 32, 255)


def master(size=768):
    logo = Image.open(LOGO).convert("RGBA")
    w, h = logo.size
    side = int(h * 0.495)                                          # the emblem: above the written name
    emblem = logo.crop(((w - side) // 2, 0, (w + side) // 2, side))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=255)
    img.paste(Image.new("RGBA", (size, size), BG), (0, 0), mask)
    inner = int(size * 0.88)
    e = emblem.resize((inner, inner), Image.LANCZOS)
    img.alpha_composite(e, ((size - inner) // 2, (size - inner) // 2 + int(size * 0.01)))
    return img


def main():
    m = master()
    out = lambda n, s: m.resize((s, s), Image.LANCZOS).save(ROOT / "static" / "img" / n)
    out("favicon-16.png", 16); out("favicon-32.png", 32); out("favicon-48.png", 48); out("favicon-96.png", 96); out("favicon-192.png", 192)
    m.resize((48, 48), Image.LANCZOS).save(ROOT / "static" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("icons written")


if __name__ == "__main__":
    main()
