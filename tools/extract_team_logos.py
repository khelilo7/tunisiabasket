"""Cut the 12 team logos out of the federation result graphics (tests/results_images + seed/official.json).

Every result bar ends in a circular cap holding a club logo, and each team appears 22 times (11 matchdays x home/away).
For each team we cut the circle from every appearance and keep the sharpest one from the biggest image.
Output: static/img/teams/<CODE>.png (128 px, transparent outside the circle).  Run:  python tools/extract_team_logos.py
Better source files? Drop a square PNG named <CODE>.png into static/img/teams/ and the site uses it.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import results_parser as rp  # noqa: E402

SIZE = 128
CAP_EDGE = 4.42  # distance from the red X to the bar's end, in bar heights (same template in every image)


def sharpness(img):
    g = np.array(img.convert("L"), dtype=float)
    return float(np.var(np.diff(g, axis=0)) + np.var(np.diff(g, axis=1)))


def main():
    off = json.loads((root / "seed" / "official.json").read_text())
    cands = {}
    for md in range(1, 12):
        rgb = Image.open(root / "tests" / "results_images" / f"{md}.jpg").convert("RGB")
        arr = np.array(rgb)
        bars = rp.find_bars(rgb)
        for (y0, y1), g in zip(bars, [r for r in off["results"] if r["matchday"] == md]):
            u = y1 - y0
            mid = arr[y0:y1, int(.30 * arr.shape[1]):int(.70 * arr.shape[1])].astype(int)
            red = (mid[..., 0] > 140) & (mid[..., 1] < 90) & (mid[..., 2] < 90)
            cx = int(.30 * arr.shape[1]) + int(np.median(np.where(red)[1]))
            for side, team in (("L", g["home"]), ("R", g["away"])):
                left = round(cx - CAP_EDGE * u if side == "L" else cx + CAP_EDGE * u - u)
                crop = rgb.crop((left, y0, left + u, y0 + u))
                cands.setdefault(team, []).append((u, sharpness(crop), crop))
    out = root / "static" / "img" / "teams"
    out.mkdir(parents=True, exist_ok=True)
    for team, lst in sorted(cands.items()):
        umax = max(c[0] for c in lst)
        _, _, crop = max((c for c in lst if c[0] >= umax - 1), key=lambda c: c[1])
        img = crop.resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (SIZE * 4, SIZE * 4), 0)
        ImageDraw.Draw(mask).ellipse((2, 2, SIZE * 4 - 3, SIZE * 4 - 3), fill=255)
        img.putalpha(mask.resize((SIZE, SIZE), Image.LANCZOS))
        img.save(out / f"{team}.png", optimize=True)
        print("saved", out / f"{team}.png")


if __name__ == "__main__":
    main()
