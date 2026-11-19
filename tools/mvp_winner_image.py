"""Poster (portrait 1080x1350, Facebook / Instagram) announcing the MVP chosen by the fans, with the winner's photo, his phase numbers and the two runners-up.

    python tools/mvp_winner_image.py --photo abada.webp --votes "3,500+" [--phase 1] [--winner ca-24 --second jsk-7 --third usm-23] [--tagline "..."] [--out FILE]

The numbers (points, rebounds, assists, PIR) are the phase averages of the site's MVP race (mvp.py); the vote count is typed by you (the site never shows it to the public as a total).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mvp  # noqa: E402
import brand  # noqa: E402
import stats  # noqa: E402
from leader_images import ACCENT, BG_BOT, BG_TOP, H, M, MUTED, TEXT, W, avatar, fit, font, logo_of  # noqa: E402
from starting_five_image import RING, glow  # noqa: E402

RED = (214, 36, 52)
GOLD = (245, 197, 66)


def render(photo_path, votes, phase, ids, tagline):
    race = mvp.race(phase)
    rows = {r["id"]: r for r in race["candidates"]}
    win, p2, p3 = (rows[i] for i in ids)
    ring = RING.get(win["team"], RED if win["team"] == "CA" else ACCENT)
    if win["team"] == "CA":
        ring = RED

    img = Image.new("RGB", (W, H), BG_TOP)
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line((0, y, W, y), fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img = img.convert("RGBA")

    src = Image.open(photo_path).convert("RGB")
    # background: the same photo, enlarged, blurred, darkened and tinted with the club colour
    bg = ImageOps.fit(src, (W, H), Image.LANCZOS, centering=(0.5, 0.2)).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.38).convert("RGBA")
    tint = Image.new("RGBA", (W, H), (*ring, 70))
    bg.alpha_composite(tint)
    img.alpha_composite(bg)
    glow(img, W // 2, 520, 420, ring, 60)

    # the photo itself: kept at a size where it stays sharp, edges and bottom faded into the background
    ph_w = 700
    crop = src.crop((0, 0, src.width, int(src.width * 1.32)))                      # head to below the waist
    ph_h = int(ph_w * crop.height / crop.width)
    ph = ImageEnhance.Contrast(crop.resize((ph_w, ph_h), Image.LANCZOS)).enhance(1.06).filter(ImageFilter.UnsharpMask(2, 70, 2)).convert("RGBA")
    side = Image.new("L", (ph_w, ph_h), 255)                                       # soft left / right edges
    sd = ImageDraw.Draw(side)
    for x in range(120):
        a = int(255 * x / 120)
        sd.line((x, 0, x, ph_h), fill=a)
        sd.line((ph_w - 1 - x, 0, ph_w - 1 - x, ph_h), fill=a)
    bot = Image.new("L", (ph_w, ph_h), 255)                                        # fade out at the bottom, early enough to leave room for the name
    bd = ImageDraw.Draw(bot)
    fade = 430
    for y in range(fade):
        bd.line((0, ph_h - fade + y, ph_w, ph_h - fade + y), fill=int(255 * (1 - y / fade) ** 1.4))
    for y in range(90):                                                            # and at the top
        bd.line((0, y, ph_w, y), fill=int(255 * (y / 90)))
    mask = ImageChops.multiply(side, bot)
    ph.putalpha(ImageChops.multiply(mask, ph.getchannel("A")))
    img.alpha_composite(ph, ((W - ph_w) // 2, 150))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))                                 # darker behind the name and the numbers
    sh = ImageDraw.Draw(shade)
    for y in range(760, H):
        sh.line((0, y, W, y), fill=(12, 14, 26, min(215, int(215 * (y - 760) / 200))))
    img.alpha_composite(shade)

    dr = ImageDraw.Draw(img)
    # top bar
    brand.header(img, f"PRO A  ·  {stats.load_official().get('season') or ''}".upper(), M, 32, 88)
    dr.text((W - M, 44), f"PHASE {phase}", font=font("black", 30), fill=TEXT, anchor="ra")
    dr.text((W - M, 82), f"J1 – J{phase * 11}", font=font("med", 24), fill=MUTED, anchor="ra")

    # ribbon
    tag = f"ELECTED BY THE FANS  ·  {votes} VOTES"
    tf = font("black", 26)
    tw = dr.textlength(tag, font=tf)
    dr.rounded_rectangle((W / 2 - tw / 2 - 32, 138, W / 2 + tw / 2 + 32, 190), radius=26, fill=ACCENT)
    dr.text((W / 2, 164), tag, font=tf, fill=(14, 20, 40), anchor="mm")

    # title + name
    dr.text((W // 2, 868), f"PHASE {phase} MVP", font=font("black", 40), fill=GOLD, anchor="mm")
    name = win["name"].upper()
    dr.text((W // 2, 958), name, font=fit(dr, name, "black", 128, W - 2 * M), fill=TEXT, anchor="mm")
    lg = logo_of(win["team"], 54)
    sub = "CLUB AFRICAIN" if win["team"] == "CA" else win["team"]
    dr.text((W // 2 + 30, 1034), sub, font=font("bold", 28), fill=MUTED, anchor="mm")
    if lg:
        img.alpha_composite(lg, (int(W // 2 + 30 - dr.textlength(sub, font=font("bold", 28)) / 2 - 66), 1008))

    # numbers
    tiles = [("PTS", win["pts"]), ("REB", win["reb"]), ("AST", win["ast"]), ("PIR", win["pir"])]
    tw_, gap = 214, 16
    x0 = (W - (4 * tw_ + 3 * gap)) // 2
    for i, (lab, v) in enumerate(tiles):
        x = x0 + i * (tw_ + gap)
        dr.rounded_rectangle((x, 1070, x + tw_, 1146), radius=18, fill=(26, 34, 62, 235), outline=(*ring, 255) if lab == "PIR" else None, width=2)
        dr.text((x + tw_ / 2, 1100), f"{v:.1f}", font=font("black", 40), fill=TEXT, anchor="mm")
        dr.text((x + tw_ / 2, 1131), lab, font=font("med", 18), fill=MUTED, anchor="mm")

    dr.text((W // 2, 1186), tagline, font=fit(dr, tagline, "med", 27, W - 2 * M), fill=(214, 220, 236), anchor="mm")

    # the runners-up
    for k, (pl, rank) in enumerate(((p2, 2), (p3, 3))):
        cx0 = M + k * ((W - 2 * M) // 2)
        col = {2: (201, 209, 219), 3: (208, 138, 78)}[rank]
        img.alpha_composite(avatar(pl, 58, col), (cx0 + 6, 1214))
        dr = ImageDraw.Draw(img)
        dr.text((cx0 + 78, 1232), f"{rank}  ·  {' '.join(w.capitalize() for w in pl['name'].split())}", font=fit(dr, pl["name"], "bold", 25, 380), fill=TEXT, anchor="lm")
        dr.text((cx0 + 78, 1262), f"{pl['team']}  ·  {pl['pir']:.1f} PIR", font=font("med", 20), fill=MUTED, anchor="lm")

    brand.footer(img)
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--photo", required=True)
    ap.add_argument("--votes", required=True, help='as written on the poster, e.g. "3,500+"')
    ap.add_argument("--phase", type=int, default=1)
    ap.add_argument("--winner", default="ca-24")
    ap.add_argument("--second", default="jsk-7")
    ap.add_argument("--third", default="usm-23")
    ap.add_argument("--tagline", default="The Tunisian legend. He always shows up when it matters most.")
    ap.add_argument("--out", default=str(ROOT / "exports" / "mvp-phase1-winner.png"))
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    render(a.photo, a.votes, a.phase, (a.winner, a.second, a.third), a.tagline).save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
