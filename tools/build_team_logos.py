"""Build the team logos shown on the site from the original club logos in assets/team-logos-src/<CODE>.<png|jpg>.

Every logo is cropped to its real content (some come on big white canvases, one on a grey gradient with a copyright line),
backgrounds that are not white are removed, and the logo is scaled to the SAME size and centred on a white round badge.
Output: static/img/teams/<CODE>.png (256 x 256, transparent outside the badge).   Run:  python tools/build_team_logos.py
To change a logo: replace its file in assets/team-logos-src/ and run the script again.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

root = Path(__file__).resolve().parent.parent
SRC, OUT = root / "assets" / "team-logos-src", root / "static" / "img" / "teams"
SIZE = 256          # badge diameter
INNER = 172         # longest side of every logo (same for all, and the corners of a tall or wide logo stay inside the circle)
TOLERANCE = {"SN": 38}          # colour distance still counted as background (default 28)
CROP = {"SN": (440, 30, 760, 570)}  # SN comes with a copyright line and lots of grey: keep only the emblem


def flood_border(candidate):
    """True for candidate pixels connected to the image border (the background); needs no extra libraries."""
    h, w = candidate.shape
    seen = np.zeros_like(candidate, dtype=bool)
    stack = [(y, x) for y in (0, h - 1) for x in range(w)] + [(y, x) for x in (0, w - 1) for y in range(h)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and candidate[y, x] and not seen[y, x]:
            seen[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return seen


def subject(path, code):
    img = Image.open(path).convert("RGBA")
    if code in CROP:
        img = img.crop(CROP[code])
    flat = Image.new("RGBA", img.size, (255, 255, 255, 255))
    flat.alpha_composite(img)
    rgb = np.array(flat.convert("RGB")).astype(int)
    ring = np.concatenate([rgb[:2].reshape(-1, 3), rgb[-2:].reshape(-1, 3), rgb[:, :2].reshape(-1, 3), rgb[:, -2:].reshape(-1, 3)])
    bg_colour = np.median(ring, axis=0)
    bg = flood_border(np.sqrt(((rgb - bg_colour) ** 2).sum(2)) <= TOLERANCE.get(code, 28))
    alpha = Image.fromarray(((~bg) * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.7))
    out = flat.copy()
    out.putalpha(alpha)
    box = Image.fromarray((~bg * 255).astype("uint8")).getbbox()
    return out.crop(box)


def badge(logo):
    k = INNER / max(logo.size)
    logo = logo.resize((max(1, round(logo.width * k)), max(1, round(logo.height * k))), Image.LANCZOS)
    big = SIZE * 4   # draw the disc at 4x and shrink: smooth edge
    disc = Image.new("L", (big, big), 0)
    ImageDraw.Draw(disc).ellipse((4, 4, big - 5, big - 5), fill=255)
    canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    canvas.paste(Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255)), (0, 0), disc.resize((SIZE, SIZE), Image.LANCZOS))
    ring = Image.new("L", (big, big), 0)
    ImageDraw.Draw(ring).ellipse((4, 4, big - 5, big - 5), outline=255, width=10)
    canvas.paste(Image.new("RGBA", (SIZE, SIZE), (120, 128, 150, 120)), (0, 0), ring.resize((SIZE, SIZE), Image.LANCZOS))
    canvas.alpha_composite(logo, ((SIZE - logo.width) // 2, (SIZE - logo.height) // 2))
    return canvas


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in SRC.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not files:
        sys.exit(f"no logos in {SRC}")
    for f in files:
        code = f.stem.upper()
        badge(subject(f, code)).save(OUT / f"{code}.png", optimize=True)
        print("built", OUT / f"{code}.png")


if __name__ == "__main__":
    main()
