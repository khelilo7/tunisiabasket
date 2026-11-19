"""Poster (portrait 1080x1350, Facebook / Instagram) announcing the player of the round chosen by the fans, with his photo, his numbers of that game and the two runners-up.

    python tools/round_winner_image.py --photo abada.webp --game d20ab1f2d47d039e --player ca-24 --round 12 --votes 52 --pct 61.2 \
        --second usm-1:16:18.8 --third ess-10:10:11.8 [--site https://tunisiabasket.com] [--out FILE]

The game line (points, rebounds, assists, PIR, shooting, +/-) is read from the live site (the box score of --game); the votes and shares are typed from the admin's round vote.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand  # noqa: E402
from leader_images import ACCENT, BG_BOT, BG_TOP, H, M, MUTED, TEXT, W, avatar, fit, font, logo_of  # noqa: E402
from starting_five_image import glow  # noqa: E402

RED = (214, 36, 52)
GOLD = (245, 197, 66)


def fetch(site, path):
    req = urllib.request.Request(site.rstrip("/") + path, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def row_of(site, game_id, pid):
    g = fetch(site, f"/api/games/{game_id}")
    for t in g["teams"]:
        opp = next(x for x in g["teams"] if x is not t)
        for p in t["players"]:
            if p.get("pid") == pid and not p.get("dnp"):
                return g, t, opp, p
    raise SystemExit(f"{pid} did not play in game {game_id}")


def runner(site, spec):
    pid, votes, *rest = spec.split(":")
    pct = rest[0] if rest else ""
    p = fetch(site, f"/api/players/{pid}")["player"]
    return {"id": pid, "name": p["name"], "team": p["team"]}, votes, pct


def render(photo_path, g, team, opp, p, rnd, votes, pct, seconds, date="11 NOVEMBER 2026", third_stat="ast", cut=None):
    ring = RED
    img = Image.new("RGB", (W, H), BG_TOP)
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line((0, y, W, y), fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img = img.convert("RGBA")

    src = Image.open(photo_path).convert("RGB")
    bg = ImageOps.fit(src, (W, H), Image.LANCZOS, centering=(0.5, 0.2)).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.38).convert("RGBA")
    bg.alpha_composite(Image.new("RGBA", (W, H), (*ring, 70)))
    img.alpha_composite(bg)
    glow(img, W // 2, 520, 420, ring, 60)

    if cut is not None:                                                   # only the winner, cut out of the photo, in front of the blurred photo
        s2 = 780 / cut.height
        sub = cut.resize((round(cut.width * s2), 780), Image.LANCZOS)
        fade = Image.new("L", sub.size, 255)
        fd = ImageDraw.Draw(fade)
        for y in range(300):
            fd.line((0, sub.height - 300 + y, sub.width, sub.height - 300 + y), fill=int(255 * (1 - y / 300) ** 1.3))
        sub.putalpha(ImageChops.multiply(sub.getchannel("A"), fade))
        img.alpha_composite(sub, ((W - sub.width) // 2, 210))
    ph_w = 700
    crop = src.crop((0, 0, src.width, int(src.width * 1.32)))
    ph_h = int(ph_w * crop.height / crop.width)
    ph = ImageEnhance.Contrast(crop.resize((ph_w, ph_h), Image.LANCZOS)).enhance(1.06).filter(ImageFilter.UnsharpMask(2, 70, 2)).convert("RGBA")
    side = Image.new("L", (ph_w, ph_h), 255)
    sd = ImageDraw.Draw(side)
    for x in range(120):
        a = int(255 * x / 120)
        sd.line((x, 0, x, ph_h), fill=a)
        sd.line((ph_w - 1 - x, 0, ph_w - 1 - x, ph_h), fill=a)
    bot = Image.new("L", (ph_w, ph_h), 255)
    bd = ImageDraw.Draw(bot)
    fade = 430
    for y in range(fade):
        bd.line((0, ph_h - fade + y, ph_w, ph_h - fade + y), fill=int(255 * (1 - y / fade) ** 1.4))
    for y in range(90):
        bd.line((0, y, ph_w, y), fill=int(255 * (y / 90)))
    ph.putalpha(ImageChops.multiply(ImageChops.multiply(side, bot), ph.getchannel("A")))
    if cut is None:
        img.alpha_composite(ph, ((W - ph_w) // 2, 150))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = ImageDraw.Draw(shade)
    for y in range(760, H):
        sh.line((0, y, W, y), fill=(12, 14, 26, min(215, int(215 * (y - 760) / 200))))
    img.alpha_composite(shade)

    dr = ImageDraw.Draw(img)
    brand.header(img, "PRO A  ·  2026-2027".upper(), M, 30, 70)
    dr.text((W - M, 44), f"DAY {rnd}", font=font("black", 30), fill=TEXT, anchor="ra")
    dr.text((W - M, 82), date, font=font("med", 24), fill=MUTED, anchor="ra")

    tag = f"ELECTED BY THE FANS  ·  {votes} VOTES" + (f"  ·  {pct}%" if pct else "")
    tf = font("black", 26)
    tw = dr.textlength(tag, font=tf)
    dr.rounded_rectangle((W / 2 - tw / 2 - 32, 138, W / 2 + tw / 2 + 32, 190), radius=26, fill=ACCENT)
    dr.text((W / 2, 164), tag, font=tf, fill=(14, 20, 40), anchor="mm")

    dr.text((W // 2, 868), f"PLAYER OF THE ROUND  ·  DAY {rnd}", font=font("black", 38), fill=GOLD, anchor="mm")
    name = p["name"].upper()
    dr.text((W // 2, 958), name, font=fit(dr, name, "black", 128, W - 2 * M), fill=TEXT, anchor="mm")
    lg = logo_of(team["code"], 54)
    sub = "CLUB AFRICAIN" if team["code"] == "CA" else team["name"].upper()
    dr.text((W // 2 + 30, 1034), sub, font=font("bold", 28), fill=MUTED, anchor="mm")
    if lg:
        img.alpha_composite(lg, (int(W // 2 + 30 - dr.textlength(sub, font=font("bold", 28)) / 2 - 66), 1008))

    tiles = [("PTS", p["pts"]), ("REB", p["reb"]), (third_stat.upper(), p[third_stat]), ("PIR", p["pir"])]
    tw_, gap = 214, 16
    x0 = (W - (4 * tw_ + 3 * gap)) // 2
    for i, (lab, v) in enumerate(tiles):
        x = x0 + i * (tw_ + gap)
        dr.rounded_rectangle((x, 1070, x + tw_, 1146), radius=18, fill=(26, 34, 62, 235), outline=(*ring, 255) if lab == "PIR" else None, width=2)
        dr.text((x + tw_ / 2, 1100), f"{v}", font=font("black", 40), fill=TEXT, anchor="mm")
        dr.text((x + tw_ / 2, 1131), lab, font=font("med", 18), fill=MUTED, anchor="mm")

    line = f"{team['code']} {team['points']} – {opp['points']} {opp['code']}  ·  {p['fgm']}/{p['fga']} FG  ·  {p['p3m']}/{p['p3a']} 3PT  ·  {p['ftm']}/{p['fta']} FT  ·  {p['pm']:+d}"
    dr.text((W // 2, 1186), line, font=fit(dr, line, "med", 27, W - 2 * M), fill=(214, 220, 236), anchor="mm")

    for k, (pl, v, pc) in enumerate(seconds):
        cx0 = M + k * ((W - 2 * M) // 2)
        col = {0: (201, 209, 219), 1: (208, 138, 78)}[k]
        img.alpha_composite(avatar(pl, 58, col), (cx0 + 6, 1214))
        dr = ImageDraw.Draw(img)
        dr.text((cx0 + 78, 1232), f"{k + 2}  ·  {' '.join(w.capitalize() for w in pl['name'].split())}", font=fit(dr, pl["name"], "bold", 25, 380), fill=TEXT, anchor="lm")
        dr.text((cx0 + 78, 1262), f"{pl['team']}  ·  {v} votes" + (f"  ·  {pc}%" if pc else ""), font=font("med", 20), fill=MUTED, anchor="lm")

    brand.footer(img)
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--photo", required=True)
    ap.add_argument("--site", default="https://tunisiabasket.com")
    ap.add_argument("--game", required=True, help="id of the box score of the winner's game")
    ap.add_argument("--player", required=True, help="winner's player id, e.g. ca-24")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--votes", required=True)
    ap.add_argument("--pct", default="", help="share of the votes (left out of the poster when empty); votes may be written 700+")
    ap.add_argument("--date", default="11 NOVEMBER 2026", help="date printed top right, e.g. \"14 NOVEMBER 2026\"")
    ap.add_argument("--second", required=True, help="player id:votes:share, e.g. usm-1:16:18.8")
    ap.add_argument("--third", required=True)
    ap.add_argument("--third-stat", default="ast", choices=["ast", "stl", "blk"], help="the third tile (assists by default; a rebounder with no assists shows blocks)")
    ap.add_argument("--cutout-at", help="x,y (fractions of the photo): cut the person standing there out of the photo and show only him, e.g. 0.62,0.5")
    ap.add_argument("--out", default=str(ROOT / "exports" / "round-winner.png"))
    a = ap.parse_args()
    g, team, opp, p = row_of(a.site, a.game, a.player)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cut = None
    if a.cutout_at:
        from game_images import cutout
        cut = cutout(a.photo, tuple(float(v) for v in a.cutout_at.split(",")))
    render(a.photo, g, team, opp, p, a.round, a.votes, a.pct, [runner(a.site, a.second), runner(a.site, a.third)], a.date, a.third_stat, cut).save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
