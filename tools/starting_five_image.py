"""Shareable "starting five" poster of two teams for Facebook / Instagram (portrait 1080x1350): the two clubs, their standing, coaches and venue, then the five players of each
team facing each other, position by position.

    python tools/starting_five_image.py JSK USM --after 11 --matchday 12 --date 2026-11-11 \\
        --venue "Salle Mohamed Mzali" "Monastir" --coaches "Marouen Keshrid" "Vanja Miljković" --tag "BIG GAME OF THE ROUND" \\
        --exclude jsk-9 jsk-5 usm-2 --pos jsk-2=SF jsk-23=PF usm-1=SG usm-5=PG --zoom jsk-23=2.3

The five of a team are those the site shows as the expected starting five (lineups.py: starts this season + 2 x starts in the team's last 5 games); players the admin marked as
absent are left out, and so are those in --exclude (profile ids), and the next ones move up. --pos sets the position shown when the site's inferred one is wrong, --zoom zooms on the face of a wide photo. --after N computes the standing
from the results of matchdays 1..N only. It is a prediction from the box scores the site has, nothing more.
"""
import argparse
import copy
import datetime
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import leader_images  # noqa: E402
import stats  # noqa: E402
from lineups import expected_five  # noqa: E402
from leader_images import ACCENT, BG_BOT, BG_TOP, H, M, MUTED, PANEL, TEXT, W, avatar, fit, font, logo_of  # noqa: E402

RING = {"JSK": (31, 166, 84), "USM": (56, 132, 224)}
FOOTER_LOGO = ROOT / "exports" / "logo" / "tunisiabasket-footer-light-text.png"
ORD = {1: "1st", 2: "2nd", 3: "3rd"}


def standing(code, after):
    o = copy.deepcopy(stats.load_official())
    if after:
        o["results"] = [r for r in o["results"] if r["matchday"] <= after]
    row = next(r for r in stats.official_standings(o) if r["code"] == code)
    return row["rank"], row["w"], row["l"]


def glow(img, cx, cy, r, color, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r * 0.45)))


def row_card(w, h, left, right):
    """A row background: dark panel tinted with the left team's colour on the left and the right team's on the right."""
    card = Image.new("RGBA", (w, h), (*PANEL, 255))
    tint = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(tint)
    for x in range(w):
        t = abs(x / (w - 1) - 0.5) * 2                  # 0 in the middle, 1 at the sides
        a = int(70 * max(0.0, t - 0.25) / 0.75)
        td.line((x, 0, x, h), fill=(*(left if x < w / 2 else right), a))
    card.alpha_composite(tint)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=24, fill=255)
    card.putalpha(mask)
    return card


def render(d, a, b, opt):
    names = {}
    for g in d["games"]:
        for t in g["teams"]:
            names.setdefault(t["code"], t["name"])
    full = lambda c: " ".join(w.upper() if len(w) == 2 else w for w in names.get(c, c).title().split())
    ca, cb = RING.get(a, ACCENT), RING.get(b, ACCENT)

    img = Image.new("RGB", (W, H), BG_TOP)
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line((0, y, W, y), fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img = img.convert("RGBA")
    glow(img, 120, 330, 430, ca, 95)
    glow(img, W - 120, 330, 430, cb, 105)
    glow(img, W // 2, 330, 200, ACCENT, 38)
    rings = Image.new("RGBA", img.size, (0, 0, 0, 0))                              # faint centre-court circles behind the VS, blended (never over the text)
    rd = ImageDraw.Draw(rings)
    for r, al in ((120, 34), (185, 22), (250, 12)):
        rd.ellipse((W // 2 - r, 300 - r, W // 2 + r, 300 + r), outline=(255, 255, 255, al), width=2)
    img.alpha_composite(rings)
    dr = ImageDraw.Draw(img)

    # top bar
    mark = Image.open(ROOT / "static" / "img" / "logo.png").convert("RGBA")
    mark = mark.resize((int(mark.width * 88 / mark.height), 88), Image.LANCZOS)
    img.alpha_composite(mark, (M, 32))
    dr.text((M + mark.width + 18, 44), "TUNISIA BASKET", font=font("black", 26), fill=ACCENT)
    dr.text((M + mark.width + 18, 80), f"PRO A  ·  {d['season']}", font=font("med", 22), fill=MUTED)
    if opt["matchday"]:
        dr.text((W - M, 44), f"MATCHDAY {opt['matchday']}", font=font("black", 30), fill=TEXT, anchor="ra")
    if opt["date"]:
        day = datetime.date.fromisoformat(opt["date"]).strftime("%a %d %b").upper()
        dr.text((W - M, 82), day + (f"  ·  {opt['time']}" if opt["time"] else ""), font=font("med", 24), fill=MUTED, anchor="ra")

    # tag
    tag = opt["tag"]
    if tag:
        tf = font("black", 26)
        tw = dr.textlength(tag, font=tf)
        dr.rounded_rectangle((W / 2 - tw / 2 - 30, 146, W / 2 + tw / 2 + 30, 196), radius=25, fill=ACCENT)
        dr.text((W / 2, 171), tag, font=tf, fill=(14, 20, 40), anchor="mm")

    # the two clubs
    for k, code in enumerate((a, b)):
        cx = 215 if k == 0 else W - 215
        ring = (ca, cb)[k]
        r = 100
        glow(img, cx, 330, 135, ring, 90)
        dr = ImageDraw.Draw(img)
        dr.ellipse((cx - r - 8, 330 - r - 8, cx + r + 8, 330 + r + 8), fill=ring)
        dr.ellipse((cx - r - 2, 330 - r - 2, cx + r + 2, 330 + r + 2), fill=(14, 20, 40))
        lg = logo_of(code, 2 * r - 6)
        if lg:
            disc = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
            ImageDraw.Draw(disc).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=(255, 255, 255, 255))
            disc.alpha_composite(lg, (3, 3))
            img.alpha_composite(disc, (cx - r, 330 - r))
        dr = ImageDraw.Draw(img)
        nm = full(code).upper()
        dr.text((cx, 462), nm, font=fit(dr, nm, "black", 34, 400), fill=TEXT, anchor="mm")
        rank, w, l = standing(code, opt["after"])
        dr.text((cx, 502), f"{ORD.get(rank, str(rank) + 'th')}  ·  {w}W – {l}L", font=font("bold", 26), fill=ring, anchor="mm")
        if opt["coaches"]:
            dr.text((cx, 538), f"Coach  {opt['coaches'][k]}", font=fit(dr, f"Coach  {opt['coaches'][k]}", "med", 22, 400), fill=MUTED, anchor="mm")

    # centre: VS, venue
    cx = W // 2
    glow(img, cx, 300, 80, ACCENT, 120)
    dr = ImageDraw.Draw(img)
    dr.ellipse((cx - 62, 238, cx + 62, 362), fill=ACCENT)
    dr.text((cx, 301), "VS", font=font("black", 54), fill=(14, 20, 40), anchor="mm")
    if opt["venue"]:
        dr.text((cx, 410), opt["venue"][0].upper(), font=fit(dr, opt["venue"][0].upper(), "bold", 24, 330), fill=TEXT, anchor="mm")
        if len(opt["venue"]) > 1:
            dr.text((cx, 442), opt["venue"][1].upper(), font=font("med", 22), fill=MUTED, anchor="mm")

    # section title
    dr.text((cx, 596), "STARTING FIVE", font=font("black", 38), fill=TEXT, anchor="mm")
    tw = dr.textlength("STARTING FIVE", font=font("black", 38))
    for x0, x1 in ((M, cx - tw / 2 - 24), (cx + tw / 2 + 24, W - M)):
        dr.line((x0, 596, x1, 596), fill=(58, 68, 98), width=2)

    # the five, facing each other
    fa, fb = expected_five(d, a, opt["exclude"], opt["pos"]), expected_five(d, b, opt["exclude"], opt["pos"])
    rw, rh, y0, pitch, av = W - 2 * M, 104, 628, 114, 88
    card = row_card(rw, rh, ca, cb)
    for i in range(5):
        y = y0 + i * pitch
        img.alpha_composite(card, (M, y))
        dr = ImageDraw.Draw(img)
        for k, p in enumerate((fa[i], fb[i]) if i < len(fa) and i < len(fb) else ()):
            ring = (ca, cb)[k]
            left = k == 0
            ax = M + 14 if left else W - M - 14 - av
            img.alpha_composite(avatar(p, av, ring), (ax, y + (rh - av) // 2))
            tx = ax + av + 16 if left else ax - 16
            anchor = "l" if left else "r"
            name = " ".join(w.capitalize() if w.isupper() else w for w in p["name"].split())
            avail = 314
            dr = ImageDraw.Draw(img)
            dr.text((tx, y + 22), f"#{p['number']}", font=font("bold", 20), fill=ring, anchor=anchor + "m")
            dr.text((tx, y + 49), name, font=fit(dr, name, "bold", 29, avail), fill=TEXT, anchor=anchor + "m")
            line = f"{p['pts']:.1f} PTS  ·  {p['reb']:.1f} REB  ·  {p['ast']:.1f} AST"
            dr.text((tx, y + 82), line, font=fit(dr, line, "med", 20, avail), fill=MUTED, anchor=anchor + "m")
        pos = fa[i]["pos"] if i < len(fa) else ""
        pw = 96
        dr.rounded_rectangle((cx - pw // 2, y + rh // 2 - 22, cx + pw // 2, y + rh // 2 + 22), radius=22, fill=(14, 20, 40), outline=ACCENT, width=2)
        dr.text((cx, y + rh // 2 + 1), pos, font=font("black", 24), fill=ACCENT, anchor="mm")

    # footer
    dr.text((W // 2, H - 124), "Based on starts this season and in recent games", font=font("reg", 22), fill=MUTED, anchor="mm")
    if FOOTER_LOGO.is_file():
        fl = Image.open(FOOTER_LOGO).convert("RGBA")
        fl = fl.resize((int(fl.width * 72 / fl.height), 72), Image.LANCZOS)
        img.alpha_composite(fl, ((W - fl.width) // 2, H - 96))
    else:
        dr.text((W // 2, H - 60), "tunisiabasket.com", font=font("bold", 30), fill=ACCENT, anchor="mm")
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("home", help="club shown on the left (code)")
    ap.add_argument("away", help="club shown on the right (code)")
    ap.add_argument("--exclude", nargs="*", default=[], help="profile ids of players who will not play, e.g. jsk-9 usm-2")
    ap.add_argument("--pos", nargs="*", default=[], help="position to show for a player, e.g. jsk-2=SF jsk-23=PF")
    ap.add_argument("--zoom", nargs="*", default=[], help="zoom factor on the face for a wide photo, e.g. jsk-23=2.3")
    ap.add_argument("--after", type=int, default=0, help="standing after this matchday (default: all results)")
    ap.add_argument("--matchday", type=int, default=0)
    ap.add_argument("--date", default="", help="YYYY-MM-DD")
    ap.add_argument("--time", default="", help="kick-off, e.g. 18:00 (only if confirmed)")
    ap.add_argument("--venue", nargs="*", default=[], help='hall and town, e.g. "Salle Mohamed Mzali" "Monastir"')
    ap.add_argument("--coaches", nargs=2, default=[], metavar=("LEFT", "RIGHT"))
    ap.add_argument("--tag", default="", help='ribbon above the clubs, e.g. "BIG GAME OF THE ROUND"')
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    home, away = a.home.upper(), a.away.upper()
    zoom = {k: float(v) for k, v in (x.split("=") for x in a.zoom)}
    plain = leader_images.photo_of

    def zoomed(pid):
        im = plain(pid)
        if im and zoom.get(pid, 1) > 1:
            w, h = im.size
            side = int(min(w, h) / zoom[pid])
            left = min(max(int(w * 0.52 - side / 2), 0), w - side)       # the face of a wide shot: a little right of centre, in the upper part
            top = min(max(int(h * 0.24 - side / 2), 0), h - side)
            im = im.crop((left, top, left + side, top + side))
        return im
    leader_images.photo_of = zoomed
    out = Path(a.out or ROOT / "exports" / f"starting5-{home.lower()}-{away.lower()}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    opt = {"exclude": set(a.exclude), "pos": dict(x.split("=") for x in a.pos), "after": a.after, "matchday": a.matchday, "date": a.date, "time": a.time,
           "venue": a.venue, "coaches": a.coaches, "tag": a.tag}
    render(stats.build(), home, away, opt).save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
