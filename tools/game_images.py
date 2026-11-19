"""Two portrait posters (1080x1350, Facebook / Instagram) for one game, in the new brand: the game MVP, and the result poster of a close game.

    python tools/game_images.py mvp      --game d261e62f48390ee9 --team JSK --number 2 --photo mnafedh.jpg [--site https://tunisiabasket.com] [--out FILE]
    python tools/game_images.py thriller --game d261e62f48390ee9 --photo duel.jpg --headline "A THRILLER IN GORJANI" [--out FILE]

The numbers come from the box score of --game on the live site. The players are cut out of their photos with Apple's Vision framework (tools/cutout_mask.swift, macOS only, nothing
to install): in the MVP photo only the person in the middle is kept (not the defender at the edge), in the result photo everybody in the foreground; the old background is
replaced by the poster's own. Lettering: Barlow Condensed (assets/brand/fonts, SIL OFL).
"""
import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand  # noqa: E402
from leader_images import logo_of  # noqa: E402

W, H, M = 1080, 1350, 48
NAVY, PANEL, TEXT, MUTED = (11, 16, 26), (24, 32, 52), (244, 246, 251), (150, 160, 185)
RED, BRIGHT_RED, GOLD = (217, 50, 58), (238, 75, 82), (245, 197, 66)
TEAM = {"JSK": (31, 166, 84), "CA": (214, 36, 52), "USM": (56, 132, 224)}          # the colour a club glows with
FONTS = ROOT / "assets" / "brand" / "fonts"
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]


font, spaced, footer = brand.font, brand.spaced, brand.footer


# ------------------------------------------------------------------ data
def fetch(site, gid):
    req = urllib.request.Request(f"{site.rstrip('/')}/api/games/{gid}", headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def team_totals(t):
    keys = ("pts", "fgm", "fga", "p3m", "p3a", "ftm", "fta")
    tot = {k: sum(p.get(k) or 0 for p in t["players"] if not p.get("dnp")) for k in keys}
    tot["bench"] = (t.get("extra") or {}).get("bench")
    return tot


def day_text(game):
    y, m, d = (int(x) for x in game["date"].split("-"))
    return f"{d} {MONTHS[m - 1]} {y}"


# ------------------------------------------------------------------ cut-outs
def vision_mask(photo):
    """One byte per pixel (0 = background, 1.. = each person or object in the foreground) from Apple's Vision framework, at the photo's size."""
    with tempfile.TemporaryDirectory() as tmp:
        exe, pgm = Path(tmp) / "mask", Path(tmp) / "mask.pgm"
        subprocess.run(["swiftc", "-O", str(Path(__file__).with_name("cutout_mask.swift")), "-o", str(exe)], check=True, capture_output=True)
        subprocess.run([str(exe), str(photo), str(pgm)], check=True, capture_output=True)
        m = Image.open(pgm)
        m.load()
    return np.array(m.resize(Image.open(photo).size, Image.NEAREST))


def cutout(photo, keep="center"):
    """The photo as RGBA with only the wanted people left (soft edges), cropped to them. keep: "center" = the one standing in the middle, "all" = everybody."""
    im = Image.open(photo).convert("RGB")
    lab = vision_mask(photo)
    ids = [i for i in np.unique(lab) if i]
    if isinstance(keep, tuple):                          # the person at that point of the photo (fractions of the width and height)
        h, w = lab.shape
        at = lab[min(h - 1, int(keep[1] * h)), min(w - 1, int(keep[0] * w))]
        ids = [at] if at else ids
    elif keep == "center":
        h, w = lab.shape
        mid = lab[h // 3: 2 * h // 3, int(w * 0.40): int(w * 0.60)]
        ids = [max(ids, key=lambda i: int((mid == i).sum()))]
    mask = Image.fromarray(np.isin(lab, ids).astype(np.uint8) * 255)
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(max(1.5, im.width / 700))).point(lambda v: 0 if v < 90 else min(255, int((v - 90) * 255 / 120)))
    rgba = im.convert("RGBA")
    rgba.putalpha(mask)
    return rgba.crop(rgba.getbbox())


# ------------------------------------------------------------------ pieces
def gradient(top, bottom):
    a = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - a) + np.array(bottom)[None, None, :] * a)
    return Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8)).convert("RGBA")


def glow(img, cx, cy, r, color, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r * 0.45)))


def fade_bottom(img, y0, y1, color=NAVY, top_alpha=0, bottom_alpha=240):
    a = np.zeros((H, W), np.uint8)
    a[y0:y1] = np.linspace(top_alpha, bottom_alpha, y1 - y0)[:, None]
    a[y1:] = bottom_alpha
    layer = Image.new("RGBA", img.size, (*color, 0))
    layer.putalpha(Image.fromarray(a))
    img.alpha_composite(layer)


def header(img, game, subtitle="PRO A  ·  2026-2027"):
    brand.header(img, subtitle, M, 36, 64, right=[(f"DAY {game['matchday'].lstrip('J')}", 74, "black", 44, TEXT), (day_text(game), 112, "semi", 28, MUTED)])


def pill(img, cx, y, label, fill=(255, 138, 31), ink=(26, 18, 5), size=38):
    d = ImageDraw.Draw(img)
    f = font("black", size)
    w = sum(d.textlength(c, font=f) for c in label) + 3 * (len(label) - 1) + 64
    d.rounded_rectangle((cx - w / 2, y, cx + w / 2, y + size + 28), radius=(size + 28) // 2, fill=fill)
    spaced(d, cx, y + size + 6, label, f, ink, 3, "m")


def stat_boxes(img, y, items, hot=None, h=112):
    d = ImageDraw.Draw(img)
    gap = 14
    w = (W - 2 * M - gap * (len(items) - 1)) / len(items)
    for i, (v, label) in enumerate(items):
        x = M + i * (w + gap)
        d.rounded_rectangle((x, y, x + w, y + h), radius=20, fill=PANEL, outline=BRIGHT_RED if label == hot else None, width=3)
        d.text((x + w / 2, y + h * 0.58), str(v), font=font("black", 66), fill=TEXT, anchor="ms")
        d.text((x + w / 2, y + h - 14), label, font=font("semi", 26), fill=MUTED, anchor="ms")


def backdrop(photo, color, strength=0.55):
    """The photo again, blurred and darkened, as the poster's background, tinted with the club's colour."""
    bg = ImageOps.fit(Image.open(photo).convert("RGB"), (W, H), Image.LANCZOS, centering=(0.5, 0.45)).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.42).convert("RGBA")
    base = gradient((16, 22, 38), NAVY)
    base.alpha_composite(Image.blend(base, bg, strength))
    glow(base, W // 2, 560, 520, color, 95)
    return base


# ------------------------------------------------------------------ the posters
def mvp(args):
    g = fetch(args.site, args.game)
    t = next(t for t in g["teams"] if t["code"] == args.team)
    o = next(t2 for t2 in g["teams"] if t2["code"] != args.team)
    p = next(p for p in t["players"] if p["number"] == args.number and not p.get("dnp"))
    color = TEAM.get(t["code"], (255, 138, 31))
    img = backdrop(args.photo, color)
    cut = cutout(args.photo, "center")
    s = 1000 / cut.height
    sub = cut.resize((round(cut.width * s), 1000), Image.LANCZOS)
    glow(img, W // 2, 690, 330, color, 70)                                          # a light of the club's colour behind him
    img.alpha_composite(sub, ((W - sub.width) // 2, 215))
    fade_bottom(img, 740, 990)
    d = ImageDraw.Draw(img)
    header(img, g)
    pill(img, W // 2, 132, "GAME MVP", size=34)
    first, last = p["name"].title().rsplit(" ", 1)[0], p["name"].title().rsplit(" ", 1)[-1]
    d.text((W // 2, 828), f"{p['p3m']} THREES  ·  {p['pts']} POINTS", font=font("black", 38), fill=GOLD, anchor="ms")
    d.text((W // 2, 880), first.upper(), font=font("semi", 52), fill=MUTED, anchor="ms")
    d.text((W // 2, 1018), last.upper(), font=font("black", 172), fill=TEXT, anchor="ms")
    lg = logo_of(t["code"], 52)
    label = t["name"].upper()
    f = font("semi", 38)
    wlab = d.textlength(label, font=f)
    x0 = (W - (60 + wlab)) / 2
    if lg:
        img.alpha_composite(lg, (int(x0), 1030))
    d.text((x0 + 64, 1069), label, font=f, fill=MUTED, anchor="ls")
    stat_boxes(img, 1108, [(p["pts"], "PTS"), (p["reb"], "REB"), (p["ast"], "AST"), (p["stl"], "STL"), (p["pir"], "PIR")], hot="PIR")
    score = f"{t['code']} {t['points']} – {o['points']} {o['code']}"
    shots = f"{p['fgm']}/{p['fga']} FG  ·  {p['p3m']}/{p['p3a']} 3PT  ·  {p['ftm']}/{p['fta']} FT"
    d.text((W // 2, 1268), f"{score}   ·   {shots}", font=font("semi", 34), fill=TEXT, anchor="ms")
    footer(img)
    return img


def thriller(args):
    g = fetch(args.site, args.game)
    a, b = g["teams"]                                                              # the order of the box score: home team first
    ta, tb = team_totals(a), team_totals(b)
    win = a if a["points"] > b["points"] else b
    ca, cb = TEAM.get(a["code"], (90, 100, 130)), TEAM.get(b["code"], (90, 100, 130))
    img = gradient((18, 24, 42), NAVY)
    left, right = Image.new("RGBA", (W, H), (*ca, 0)), Image.new("RGBA", (W, H), (*cb, 0))
    ramp = np.tile(np.clip(np.linspace(190, -40, W)[None, :], 0, 255), (H, 1)).astype(np.uint8)       # each club's colour fades in from its own side
    left.putalpha(Image.fromarray(ramp)), right.putalpha(Image.fromarray(ramp[:, ::-1].copy()))
    img.alpha_composite(left), img.alpha_composite(right)
    glow(img, W // 2, 700, 430, (255, 255, 255), 26)
    cut = cutout(args.photo, "all")
    s = min(700 / cut.height, 880 / cut.width)
    sub = cut.resize((round(cut.width * s), round(cut.height * s)), Image.LANCZOS)
    img.alpha_composite(sub, ((W - sub.width) // 2, 392))
    fade_bottom(img, 890, 1075)
    d = ImageDraw.Draw(img)
    header(img, g)
    pill(img, W // 2, 150, "THRILLER")
    for t, x, other in ((a, 270, b), (b, W - 270, a)):                             # the score, the winner lit
        won = t is win
        lg = logo_of(t["code"], 88)
        if lg:
            img.alpha_composite(lg, (x - 44, 222))
        d.text((x, 452), str(t["points"]), font=font("black", 190), fill=TEXT if won else MUTED, anchor="ms")
        d.text((x, 492), t["name"].upper(), font=font("semi", 34), fill=TEXT if won else MUTED, anchor="ms")
    d.text((W // 2, 404), "–", font=font("black", 110), fill=MUTED, anchor="ms")
    d.text((W // 2, 1004), args.headline, font=font("black", 84), fill=TEXT, anchor="ms")
    d.text((W // 2, 1052), args.subline.format(winner=win["name"], loser=(a if win is b else b)["name"]), font=font("semi", 34), fill=MUTED, anchor="ms")
    chips = [("3PT", f"{ta['p3m']}/{ta['p3a']}", f"{tb['p3m']}/{tb['p3a']}"), ("FT", f"{ta['ftm']}/{ta['fta']}", f"{tb['ftm']}/{tb['fta']}")]
    if ta["bench"] is not None and tb["bench"] is not None:
        chips.append(("BENCH PTS", str(ta["bench"]), str(tb["bench"])))
    w = (W - 2 * M - 14 * (len(chips) - 1)) / len(chips)
    for i, (label, va, vb) in enumerate(chips):
        x = M + i * (w + 14)
        d.rounded_rectangle((x, 1100, x + w, 1212), radius=20, fill=PANEL)
        d.text((x + w / 2, 1136), label, font=font("semi", 25), fill=MUTED, anchor="ms")
        d.text((x + w * 0.27, 1190), va, font=font("black", 56), fill=TEXT, anchor="ms")
        d.text((x + w * 0.73, 1190), vb, font=font("black", 56), fill=TEXT, anchor="ms")
        d.text((x + w / 2, 1190), "·", font=font("black", 56), fill=MUTED, anchor="ms")
    if args.top:
        d.text((W // 2, 1262), args.top, font=font("semi", 30), fill=TEXT, anchor="ms")
    footer(img)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("mvp", "thriller"):
        s = sub.add_parser(name)
        s.add_argument("--game", required=True)
        s.add_argument("--photo", required=True)
        s.add_argument("--site", default="https://tunisiabasket.com")
        s.add_argument("--out")
        if name == "mvp":
            s.add_argument("--team", required=True)
            s.add_argument("--number", type=int, required=True)
        else:
            s.add_argument("--headline", default="A THRILLER IN GORJANI")
            s.add_argument("--subline", default="{winner} steal it from {loser}")
            s.add_argument("--top", default="", help="one line under the chips, for example the two top scorers")
    a = ap.parse_args()
    img = (mvp if a.cmd == "mvp" else thriller)(a)
    out = Path(a.out or ROOT / "exports" / f"game-{a.cmd}-{a.game}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
