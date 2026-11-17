"""Shareable poster (portrait 1080x1350) comparing how two clubs perform in the games that matter for a fixture: the HOME games of one, the AWAY games of the other.

    python tools/venue_form_image.py JSK away USM home --after 11 [--out FILE]

Games are the official results of matchdays 1..N (--after); the per-game numbers come from the box scores the site has for those games (the footer says how many).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stats  # noqa: E402
from leader_images import ACCENT, BG_BOT, BG_TOP, H, M, MUTED, TEXT, W, fit, font, logo_of  # noqa: E402
from starting_five_image import FOOTER_LOGO, RING, glow  # noqa: E402

GOOD, BAD = (46, 190, 108), (226, 83, 83)


def venue_games(code, venue, after):
    """[(matchday, opponent, points for, points against)] of the club's home or away official results up to matchday `after`."""
    out = []
    for r in sorted(stats.load_official()["results"], key=lambda r: r["matchday"]):
        if after and r["matchday"] > after:
            continue
        if venue == "home" and r["home"] == code:
            out.append((r["matchday"], r["away"], r["home_score"], r["away_score"]))
        if venue == "away" and r["away"] == code:
            out.append((r["matchday"], r["home"], r["away_score"], r["home_score"]))
    return out


def form(d, code, venue, after):
    games = venue_games(code, venue, after)
    mds = {md: opp for md, opp, *_ in games}
    tot = dict(fgm=0, fga=0, p3m=0, p3a=0, reb=0, ast=0, tov=0, ofgm=0, ofga=0, n=0)
    scorers = {}
    for g in d["games"]:
        if g.get("matchday_no") not in mds:
            continue
        mine = next((t for t in g["teams"] if t["code"] == code), None)
        opp = next((t for t in g["teams"] if t["code"] != code), None)
        if not mine or not opp or opp["code"] != mds[g["matchday_no"]]:
            continue
        tot["n"] += 1
        for k in ("fgm", "fga", "p3m", "p3a", "reb", "ast", "tov"):
            tot[k] += sum(p[k] for p in mine["players"] if not p.get("dnp"))
        tot["ofgm"] += sum(p["fgm"] for p in opp["players"] if not p.get("dnp"))
        tot["ofga"] += sum(p["fga"] for p in opp["players"] if not p.get("dnp"))
        for p in mine["players"]:
            if not p.get("dnp"):
                s = scorers.setdefault(p["pid"], {"name": p["name"], "pts": 0, "gp": 0})
                s["pts"] += p["pts"]
                s["gp"] += 1
    n, g = tot["n"], len(games)
    top = max(scorers.values(), key=lambda s: s["pts"] / s["gp"]) if scorers else None
    wins = sum(1 for *_, f, a in games if f > a)
    return {"games": games, "w": wins, "l": g - wins, "pf": sum(x[2] for x in games) / g, "pa": sum(x[3] for x in games) / g, "boxes": n,
            "fg": 100 * tot["fgm"] / tot["fga"], "ofg": 100 * tot["ofgm"] / tot["ofga"], "p3": 100 * tot["p3m"] / tot["p3a"], "reb": tot["reb"] / n,
            "ast": tot["ast"] / n, "tov": tot["tov"] / n,
            "top": (top["name"].title() if top else "", top["pts"] / top["gp"] if top else 0)}


def surname(name):
    parts = name.split()
    return " ".join(parts[1:]) if len(parts) > 2 and parts[0].lower() in ("mohamed", "med") else (parts[-1] if len(parts) > 1 else name)


def render(d, left, right, after):
    (ca, va), (cb, vb) = left, right
    fa, fb = form(d, ca, va, after), form(d, cb, vb, after)
    ra, rb = RING.get(ca, ACCENT), RING.get(cb, ACCENT)
    names = {}
    for g in d["games"]:
        for t in g["teams"]:
            names.setdefault(t["code"], t["name"])
    full = lambda c: " ".join(w.upper() if len(w) == 2 else w for w in names.get(c, c).title().split()).upper()

    img = Image.new("RGB", (W, H), BG_TOP)
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        px.line((0, y, W, y), fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img = img.convert("RGBA")
    glow(img, 110, 380, 420, ra, 85)
    glow(img, W - 110, 380, 420, rb, 95)
    dr = ImageDraw.Draw(img)

    mark = Image.open(ROOT / "static" / "img" / "logo.png").convert("RGBA")
    mark = mark.resize((int(mark.width * 88 / mark.height), 88), Image.LANCZOS)
    img.alpha_composite(mark, (M, 32))
    dr.text((M + mark.width + 18, 44), "TUNISIA BASKET", font=font("black", 26), fill=ACCENT)
    dr.text((M + mark.width + 18, 80), f"PRO A  ·  {d['season']}", font=font("med", 22), fill=MUTED)
    dr.text((W - M, 44), f"AFTER J{after}" if after else "", font=font("black", 30), fill=TEXT, anchor="ra")
    dr.text((W // 2, 176), "HOME & AWAY FORM", font=fit(dr, "HOME & AWAY FORM", "black", 70, W - 2 * M), fill=TEXT, anchor="mm")
    sub = f"{ca} {'on the road' if va == 'away' else 'at home'}   ·   {cb} {'on the road' if vb == 'away' else 'at home'}"
    dr.text((W // 2, 238), sub, font=font("med", 28), fill=MUTED, anchor="mm")
    dr.rectangle((W // 2 - 45, 268, W // 2 + 45, 273), fill=ACCENT)

    # club blocks
    for k, (code, v, f, ring) in enumerate(((ca, va, fa, ra), (cb, vb, fb, rb))):
        left_side = k == 0
        r, cy = 62, 372
        cx = M + r + 6 if left_side else W - M - r - 6
        glow(img, cx, cy, 90, ring, 80)
        dr = ImageDraw.Draw(img)
        dr.ellipse((cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), fill=ring)
        lg = logo_of(code, 2 * r - 6)
        disc = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=(255, 255, 255, 255))
        if lg:
            disc.alpha_composite(lg, (3, 3))
        img.alpha_composite(disc, (cx - r, cy - r))
        dr = ImageDraw.Draw(img)
        tx, anchor = (cx + r + 24, "l") if left_side else (cx - r - 24, "r")
        dr.text((tx, 336), full(code), font=fit(dr, full(code), "black", 32, 280), fill=TEXT, anchor=anchor + "m")
        dr.text((tx, 370), ("AWAY GAMES" if v == "away" else "HOME GAMES") + f"  ·  {len(f['games'])}", font=font("bold", 20), fill=ACCENT, anchor=anchor + "m")
        dr.text((tx, 414), f"{f['w']}W – {f['l']}L", font=font("black", 46), fill=ring, anchor=anchor + "m")
        dr.text((tx, 452), f"{f['pf'] - f['pa']:+.1f} avg margin", font=font("med", 22), fill=MUTED, anchor=anchor + "m")

    # results strips
    def header(y, text):
        dr.text((W // 2, y), text, font=font("black", 30), fill=TEXT, anchor="mm")
        tw = dr.textlength(text, font=font("black", 30))
        for x0, x1 in ((M, W // 2 - tw / 2 - 22), (W // 2 + tw / 2 + 22, W - M)):
            dr.line((x0, y, x1, y), fill=(58, 68, 98), width=2)
    header(508, "RESULTS")
    cw, gap = (W - 2 * M - 48) // 2, 8
    cwid = (cw - 4 * gap) // 5
    for k, (f, v, ring) in enumerate(((fa, va, ra), (fb, vb, rb))):
        x0 = M + k * (cw + 48)
        for i, (md, opp, pf, pa) in enumerate(f["games"][-5:]):
            x = x0 + i * (cwid + gap)
            win = pf > pa
            dr.rounded_rectangle((x, 536, x + cwid, 624), radius=14, fill=(26, 34, 62))
            dr.rounded_rectangle((x, 536, x + cwid, 546), radius=5, fill=GOOD if win else BAD)
            dr.text((x + cwid / 2, 572), f"{'@' if v == 'away' else 'vs'} {opp}", font=fit(dr, f"{'@' if v == 'away' else 'vs'} {opp}", "bold", 19, cwid - 8), fill=MUTED, anchor="mm")
            dr.text((x + cwid / 2, 602), f"{pf}–{pa}", font=fit(dr, f"{pf}–{pa}", "black", 24, cwid - 6), fill=TEXT, anchor="mm")

    # per-game comparison
    header(668, "PER GAME")
    rows = [("POINTS SCORED", fa["pf"], fb["pf"], "{:.1f}", True), ("POINTS ALLOWED", fa["pa"], fb["pa"], "{:.1f}", False),
            ("FIELD GOAL %", fa["fg"], fb["fg"], "{:.1f}%", True), ("OPPONENT FIELD GOAL %", fa["ofg"], fb["ofg"], "{:.1f}%", False),
            ("THREE-POINT %", fa["p3"], fb["p3"], "{:.1f}%", True), ("REBOUNDS", fa["reb"], fb["reb"], "{:.1f}", True),
            ("ASSISTS", fa["ast"], fb["ast"], "{:.1f}", True), ("TURNOVERS", fa["tov"], fb["tov"], "{:.1f}", False)]
    y, pitch = 698, 54
    cx, maxlen = W // 2, 300
    for label, a, b, fmt, higher in rows:
        dr.text((cx, y + 9), label, font=font("med", 19), fill=MUTED, anchor="mm")
        best = max(a, b)
        a_wins = (a > b) if higher else (a < b)
        b_wins = (b > a) if higher else (b < a)
        for val, ring, wins, left_side in ((a, ra, a_wins, True), (b, rb, b_wins, False)):
            ln = max(8, int(maxlen * val / best))
            col = ring if wins else tuple(int(c * 0.42 + 14) for c in ring)
            if left_side:
                dr.rounded_rectangle((cx - 10 - ln, y + 22, cx - 10, y + 40), radius=9, fill=col)
                dr.text((M, y + 31), fmt.format(val), font=font("black" if wins else "bold", 30 if wins else 26), fill=TEXT if wins else MUTED, anchor="lm")
            else:
                dr.rounded_rectangle((cx + 10, y + 22, cx + 10 + ln, y + 40), radius=9, fill=col)
                dr.text((W - M, y + 31), fmt.format(val), font=font("black" if wins else "bold", 30 if wins else 26), fill=TEXT if wins else MUTED, anchor="rm")
        y += pitch
    dr.text((cx, y + 9), "TOP SCORER", font=font("med", 19), fill=MUTED, anchor="mm")
    for f, ring, left_side in ((fa, ra, True), (fb, rb, False)):
        nm, ppg = f["top"]
        nm = surname(nm)
        txt = f"{nm}  {ppg:.1f}"
        dr.text((M if left_side else W - M, y + 31), txt, font=fit(dr, txt, "black", 30, 360), fill=ring, anchor="lm" if left_side else "rm")

    note = " · ".join(f"{c}: {f['boxes']} {v} box scores" for c, v, f in ((ca, va, fa), (cb, vb, fb)))
    dr.text((W // 2, H - 124), note, font=font("reg", 22), fill=MUTED, anchor="mm")
    if FOOTER_LOGO.is_file():
        fl = Image.open(FOOTER_LOGO).convert("RGBA")
        fl = fl.resize((int(fl.width * 72 / fl.height), 72), Image.LANCZOS)
        img.alpha_composite(fl, ((W - fl.width) // 2, H - 96))
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("left_team")
    ap.add_argument("left_venue", choices=("home", "away"))
    ap.add_argument("right_team")
    ap.add_argument("right_venue", choices=("home", "away"))
    ap.add_argument("--after", type=int, default=0, help="only results up to this matchday")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lt, rt = a.left_team.upper(), a.right_team.upper()
    out = Path(a.out or ROOT / "exports" / f"form-{lt.lower()}-{a.left_venue}-{rt.lower()}-{a.right_venue}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    render(stats.build(), (lt, a.left_venue), (rt, a.right_venue), a.after).save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
