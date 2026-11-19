"""Shareable leaderboard images: one picture per important stat, a podium (ties share a step) and the rest of the top 10 under it.

    python tools/leader_images.py            # writes exports/leaders/<stat>.png (1080x1350, ready for Instagram / Facebook)
    python tools/leader_images.py --out DIR  # somewhere else

Ranking is the site's own (qualified players, per-game averages as displayed). Players with the same displayed value share the same rank
("competition" ranking: 1, 2, 2, 4...); the podium holds everyone ranked 1 to 3, the list under it completes the top 10.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
import brand  # noqa: E402
import stats  # noqa: E402

W, H, M = 1080, 1350, 48
BG_TOP, BG_BOT, PANEL, TEXT, MUTED, ACCENT = (9, 13, 28), (22, 30, 56), (26, 34, 62), (244, 246, 251), (150, 160, 185), (255, 138, 31)
MEDAL = {1: (245, 197, 66), 2: (201, 209, 219), 3: (208, 138, 78)}
STATS = [("pts", "POINTS", "per game", "{:.1f}"), ("reb", "REBOUNDS", "per game", "{:.1f}"), ("ast", "ASSISTS", "per game", "{:.1f}"),
         ("stl", "STEALS", "per game", "{:.1f}"), ("blk", "BLOCKS", "per game", "{:.1f}"), ("p3m", "THREE-POINTERS MADE", "per game", "{:.1f}"),
         ("pir", "EFFICIENCY (PIR)", "per game", "{:.1f}")]
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
FACE = {"reg": 0, "bold": 1, "cond": 4, "black": 9, "med": 10}


def font(kind, size):
    try:
        return ImageFont.truetype(FONT, size, index=FACE[kind])
    except OSError:
        return ImageFont.load_default()


def ranked(players, key, n=10):
    """[(rank, player)] best first, equal displayed values share a rank; at most n players (ties are never split by luck: ordered by PIR then name)."""
    pool = [p for p in players if p["qualified"] and (key != "fg_pct" or p["fga"] >= 4)]
    pool.sort(key=lambda p: (-p[key], -p["pir"], p["name"]))
    out = []
    for i, p in enumerate(pool[:n]):
        rank = out[-1][0] if out and out[-1][1][key] == p[key] else i + 1
        out.append((rank, p))
    cut = pool[n:n + 1]                               # a tie that continues past the 10th row is told in the footer
    hidden = sum(1 for p in pool[n:] if out and p[key] == out[-1][1][key]) if cut else 0
    return out, hidden


def photo_of(pid):
    ref = (stats.load_photos().get(pid) or "").split("?")[0]
    for path in ((config.DATA_DIR / "photos" / Path(ref).name) if ref.startswith("/photo/") else None, ROOT / "static" / ref.lstrip("/") if ref else None,
                 config.DATA_DIR / "photos" / f"{pid}.jpg"):
        if path and path.is_file():
            try:
                return Image.open(path).convert("RGB")
            except OSError:
                pass
    return None


def logo_of(code, size):
    f = ROOT / "static" / "img" / "teams" / f"{code}.png"
    if not f.is_file():
        return None
    return Image.open(f).convert("RGBA").resize((size, size), Image.LANCZOS)


def circle(img, d):
    img = ImageOps.fit(img, (d * 2, d * 2), Image.LANCZOS, centering=(0.5, 0.25))     # faces sit in the upper part of a portrait
    mask = Image.new("L", (d * 2, d * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * 2 - 1, d * 2 - 1), fill=255)
    img.putalpha(mask)
    return img.resize((d, d), Image.LANCZOS)


def avatar(p, d, ring):
    """Round portrait with a medal ring; no photo: the club logo on a dark disc."""
    big = d * 3
    base = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    dr = ImageDraw.Draw(base)
    dr.ellipse((0, 0, big - 1, big - 1), fill=ring)
    inner = big - 2 * (big // 24)
    ph = photo_of(p["id"])
    if ph:
        base.alpha_composite(circle(ph, inner), (big // 24, big // 24))
    else:
        disc = Image.new("RGBA", (inner, inner), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((0, 0, inner - 1, inner - 1), fill=(14, 20, 40))
        lg = logo_of(p["team"], int(inner * 0.66))
        if lg:
            disc.alpha_composite(lg, ((inner - lg.width) // 2, (inner - lg.height) // 2))
        base.alpha_composite(disc, (big // 24, big // 24))
    return base.resize((d, d), Image.LANCZOS)


def fit(draw, text, kind, size, max_w):
    while size > 14 and draw.textlength(text, font=font(kind, size)) > max_w:
        size -= 1
    return font(kind, size)


def name_lines(draw, name, kind, size, max_w):
    """The name on one line if it fits, else split in two (first word(s) / last word(s)); shrinks if still too wide."""
    name = " ".join(w.capitalize() if w.isupper() else w for w in name.split())
    if draw.textlength(name, font=font(kind, size)) <= max_w:
        return [name], font(kind, size)
    parts = name.split()
    if len(parts) > 1:
        best = min(range(1, len(parts)), key=lambda k: abs(len(" ".join(parts[:k])) - len(" ".join(parts[k:]))))
        lines = [" ".join(parts[:best]), " ".join(parts[best:])]
    else:
        lines = [name]
    f = font(kind, size)
    while size > 16 and max(draw.textlength(t, font=f) for t in lines) > max_w:
        size -= 1
        f = font(kind, size)
    return lines, f


def centered(draw, xy, text, f, fill, anchor="mm"):
    draw.text(xy, text, font=f, fill=fill, anchor=anchor)


def render(key, title, unit, fmt, d, upto):
    rows, hidden = ranked(d["players"], key)
    img = Image.new("RGB", (W, H), BG_TOP)
    px = ImageDraw.Draw(img)
    for y in range(H):                                                    # vertical gradient
        t = y / (H - 1)
        px.line((0, y, W, y), fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img = img.convert("RGBA")
    dr = ImageDraw.Draw(img)

    # header
    brand.header(img, f"PRO A  ·  {d['season']}  ·  AFTER {upto}".upper(), M, 36, 96)
    dr.text((M, 168), title, font=fit(dr, title, "black", 64, W - 2 * M), fill=TEXT)
    dr.text((M, 244), f"{unit}  ·  top 10", font=font("med", 26), fill=MUTED)
    dr.rectangle((M, 288, M + 90, 293), fill=ACCENT)

    # podium: everyone ranked 1..3, steps ordered 2 - 1 - 3, each as wide as the players on it
    pod = [(r, p) for r, p in rows if r <= 3]
    steps = {r: [p for rr, p in pod if rr == r] for r in sorted({r for r, _ in pod})}
    present = sorted(steps)
    order = [2, 1, 3] if present == [1, 2, 3] else [2, 1] if present == [1, 2] else present      # classic podium: silver, gold, bronze
    total = sum(len(steps[r]) for r in order)
    base, x, avail = 752, M, W - 2 * M
    gap = 14
    heights = {1: 128, 2: 94, 3: 68}
    for r in order:
        n = len(steps[r])
        sw = int((avail - gap * (len(order) - 1)) * n / total)
        h, col = heights[r], MEDAL[r]
        dr.rounded_rectangle((x, base - h, x + sw, base), radius=18, fill=PANEL, outline=col, width=3)
        centered(dr, (x + sw / 2, base - h / 2), str(r), font("black", 64 if r == 1 else 52), col)
        slot = sw / n
        for k, p in enumerate(steps[r]):
            cx = x + slot * k + slot / 2
            ad = int(min(168 if r == 1 else 140, slot - 26))
            lines, nf = name_lines(dr, p["name"], "bold", 30 if slot > 250 else 26, slot - 16)
            vf = fit(dr, fmt.format(p[key]), "black", 52 if r == 1 else 44, slot - 10)
            block = ad + 14 + len(lines) * (nf.size + 2) + 6 + vf.size                  # avatar, name, value: stacked right above the step
            top = base - h - 16 - block
            img.alpha_composite(avatar(p, ad, col), (int(cx - ad / 2), top))
            lg = logo_of(p["team"], 44)
            if lg:
                img.alpha_composite(lg, (int(cx + ad / 2 - 40), top + ad - 44))
            y = top + ad + 14
            for t in lines:
                centered(dr, (cx, y + nf.size / 2), t, nf, TEXT)
                y += nf.size + 2
            centered(dr, (cx, y + 6 + vf.size / 2), fmt.format(p[key]), vf, col)
        x += sw + gap

    # the rest of the top 10
    rest = [(r, p) for r, p in rows if r > 3]
    y, rh = base + 30, 64
    for i, (r, p) in enumerate(rest):
        if i % 2 == 0:
            dr.rounded_rectangle((M, y, W - M, y + rh - 6), radius=14, fill=(20, 28, 52))
        centered(dr, (M + 40, y + rh / 2 - 3), str(r), font("black", 32), MUTED)
        lg = logo_of(p["team"], 46)
        if lg:
            img.alpha_composite(lg, (M + 84, y + 8))
        name = " ".join(w.capitalize() if w.isupper() else w for w in p["name"].split())
        dr.text((M + 150, y + rh / 2 - 3), name, font=fit(dr, name, "bold", 32, 560), fill=TEXT, anchor="lm")
        dr.text((W - M - 190, y + rh / 2 - 3), p["team"], font=font("med", 24), fill=MUTED, anchor="rm")
        dr.text((W - M - 20, y + rh / 2 - 3), fmt.format(p[key]), font=font("black", 38), fill=TEXT, anchor="rm")
        y += rh

    # footer
    note = f"Min. {rows[0][1]['games_needed']} games played" if rows else ""
    if hidden:
        note += f"  ·  {hidden} more player{'s' if hidden > 1 else ''} tied with the 10th"
    dr.text((M, H - 118), note, font=font("reg", 22), fill=MUTED)
    brand.footer(img)
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "exports" / "leaders"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    d = stats.build()
    played = [r["matchday"] for r in stats.load_official()["results"]]
    upto = f"J{max(played)}" if played else "J0"
    for key, title, unit, fmt in STATS:
        path = out / f"leaders-{key}.png"
        render(key, title, unit, fmt, d, upto).save(path, optimize=True)
        print(path)


if __name__ == "__main__":
    main()
