"""A game counted on the analyst board (CSV export) -> the game JSON for the site + a FIBA box score PDF laid out like the federation's.

    python tools/count_sheet.py COUNT.csv --id video-j13-jsk-esr --matchday 13 --date 2026-11-14 --venue "Kairouan (salle Aziz Miled)" \
        --names-from VIDEO_SHEET.pdf --timeline-pdf VIDEO_SHEET.pdf --set ESR:8:fgm=6 --set ESR:1:fgm=4 \
        --bench 22:11 [--paint a:b --second a:b --fast a:b --turnover-pts a:b] --out-dir exports

The CSV columns are those of the board's "CSV" button: team, number, player, MIN, +/-, PTS, FGM, FGA, 3PM, 3PA, FTM, FTA, OREB, DREB, REB, AST, STL, BLK, TOV, PF.
2-pointers are FGM - 3PM. --set TEAM:NUMBER:field=value corrects one typed cell (then every check runs again: PTS = 2 x 2P + 3 x 3P + FT, REB = OR + DR, team totals = the official score).
--timeline-pdf is a sheet with a "Scoring timeline" page ("# Q Clock Video Team Pts Player Event Score J-E"): the score sequence gives the 5-minute scores, largest lead, longest run,
lead changes, ties and time in the lead. Team lines nobody counted (points in the paint, 2nd chance, fast break, from turnovers) are printed as "-" until given.
Needs reportlab for the PDF only (pip install reportlab); the site itself does not.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from validate import validate  # noqa: E402

TEAMS = {"JSK": ("JEUNESSE SPORTIVE KAIROUANAISE", "Jeunesse Sportive Kairouanaise"), "ESR": ("ETOILE SPORTIVE RADESIENNE", "ES Rades")}
MONTHS = ["janv.", "fevr.", "mars", "avr.", "mai", "juin", "juil.", "aout", "sept.", "oct.", "nov.", "dec."]
DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


# ------------------------------------------------------------------ CSV -> game
def read_csv(path, sets):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    fix = {}
    for s in sets or []:
        team, num, kv = s.split(":", 2)
        k, v = kv.split("=")
        fix[(team, int(num), k)] = int(v)
    teams = {}
    for r in rows:
        t = teams.setdefault(r["team"], [])
        mm, ss = r["MIN"].split(":")
        g = lambda k: int(r[k])
        d = {"number": g("number"), "name": r["player"], "starter": False, "captain": False, "dnp": False, "min": round(int(mm) + int(ss) / 60, 2),
             "fgm": g("FGM"), "fga": g("FGA"), "p3m": g("3PM"), "p3a": g("3PA"), "ftm": g("FTM"), "fta": g("FTA"), "oreb": g("OREB"), "dreb": g("DREB"), "reb": g("REB"),
             "ast": g("AST"), "stl": g("STL"), "blk": g("BLK"), "tov": g("TOV"), "pf": g("PF"), "fd": g("FD") if r.get("FD") not in (None, "") else 0, "pm": g("+/-"), "pts": g("PTS")}
        for (tm, num, k), v in fix.items():
            if tm == r["team"] and num == d["number"]:
                d[k] = v
        d["p2m"], d["p2a"] = d["fgm"] - d["p3m"], d["fga"] - d["p3a"]
        t.append(d)
    return teams


def name_map(pdf):
    """{(team, number): 'SURNAME FIRST'} as printed on a federation-style sheet (for the PDF only)."""
    out, cur = {}, None
    with pdfplumber.open(pdf) as p:
        text = p.pages[0].extract_text() or ""
    for ln in text.splitlines():
        m = re.search(r"\(([A-Z]{2,5})\)\s+Coach:", ln)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"^\*?(\d+)\s+(.+?)\s+~\d+\s+", ln)
        if m and cur:
            out[(cur, int(m.group(1)))] = re.sub(r"\s*\(C\)", "", m.group(2)).strip()
    return out


# ------------------------------------------------------------------ timeline -> game flow
def flow(pdf):
    ev = []
    with pdfplumber.open(pdf) as p:
        for pg in p.pages:
            for ln in (pg.extract_text() or "").splitlines():
                m = re.match(r"^\d+\s+Q(\d)\s+(\d\d):(\d\d)\s+\S+\s+(JSK|ESR)\s+\+(\d)\s+.*\s(\d+)-(\d+)$", ln)
                if m:
                    q, mi, se, team, pts, a, b = m.groups()
                    ev.append({"t": (int(q) - 1) * 600 + 600 - (int(mi) * 60 + int(se)), "q": int(q), "rem": int(mi) * 60 + int(se), "team": team, "pts": int(pts), "j": int(a), "e": int(b)})
    return ev


def derive(ev, final):
    j = e = 0
    lead = {"JSK": (0, None), "ESR": (0, None)}
    led = {"JSK": 0, "ESR": 0}
    last_t, last_lead, changes, ties, run, best_run = 0, None, 0, 0, None, {"JSK": (0, None), "ESR": (0, None)}
    for x in ev:
        cur = "JSK" if j > e else "ESR" if e > j else None
        if cur:
            led[cur] += x["t"] - last_t
        last_t = x["t"]
        j, e = x["j"], x["e"]
        d = j - e
        if d > lead["JSK"][0]:
            lead["JSK"] = (d, (j, e))
        if -d > lead["ESR"][0]:
            lead["ESR"] = (-d, (j, e))
        now = "JSK" if d > 0 else "ESR" if d < 0 else None
        if d == 0:
            ties += 1
        if now and last_lead and now != last_lead:
            changes += 1
        if now:
            last_lead = now
        if run and run[0] == x["team"]:
            run = (x["team"], run[1] + x["pts"], (j, e))
        else:
            run = (x["team"], x["pts"], (j, e))
        if run[1] > best_run[run[0]][0]:
            best_run[run[0]] = (run[1], run[2])
    cur = "JSK" if j > e else "ESR" if e > j else None
    if cur:
        led[cur] += 2400 - last_t
    assert (j, e) == final, f"timeline ends {j}-{e}, expected {final}"
    q = []
    for n in range(1, 5):
        up = [x for x in ev if x["q"] <= n]
        prev = [x for x in ev if x["q"] <= n - 1]
        q.append(((up[-1]["j"] - (prev[-1]["j"] if prev else 0)), (up[-1]["e"] - (prev[-1]["e"] if prev else 0))))
    five = []
    for n in range(1, 5):                                      # score when 5:00 are left in the quarter, and at its end
        for rem in (300, 0):
            up = [x for x in ev if x["q"] < n or (x["q"] == n and x["rem"] >= rem)]
            five.append((up[-1]["j"], up[-1]["e"]) if up else (0, 0))
    return {"lead": lead, "run": best_run, "changes": changes, "ties": ties, "led": led, "quarters": q, "five": five}


# ------------------------------------------------------------------ PDF
def pct(m, a):
    return f"{100 * m / a:.1f}".replace(".", ",") if a else "0,0"


def mmss(sec):
    return f"{int(sec // 60):02d}:{int(round(sec % 60)):02d}"


def ev_of(p):
    return p["pts"] + p["reb"] + p["ast"] + p["stl"] + p["blk"] - (p["fga"] - p["fgm"]) - (p["fta"] - p["ftm"]) - p["tov"]


def pdf(path, game, names, fl, a):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"FIBA Box Score {game['teams'][0]['code']} vs {game['teams'][1]['code']} (final)")
    c.setAuthor("Tunisia Basket")
    L, R = 38, W - 38
    B, N = "Helvetica-Bold", "Helvetica"
    jsk, esr = game["teams"]
    logo = ROOT / "static" / "img" / "logo.png"
    if logo.is_file():
        c.drawImage(str(logo), L, H - 112, width=66, height=66, mask="auto", preserveAspectRatio=True)
    c.setFont(B, 15)
    c.drawCentredString(W / 2, H - 52, "CHAMPIONNAT TUNISIE PRO A")
    c.setFont(B, 13)
    c.drawRightString(R, H - 52, "FIBA Box Score")
    c.setFont(N, 6.5)
    import datetime
    d = datetime.date.fromisoformat(game["date"])
    c.drawCentredString(W / 2, H - 65, f"{a.venue.upper()}, {DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}")
    c.drawRightString(R, H - 64, f"Journée {game['matchday_no']}")
    c.drawRightString(R, H - 72, "Statistiques finales (comptage manuel)")
    c.setFont(B, 6.5)
    c.drawRightString(R, H - 80, "Tunisia Basket")
    c.setFont(N, 9.5)
    c.drawCentredString(W / 2 + 34, H - 90, f"{TEAMS['JSK'][0]}  {jsk['points']} – {esr['points']}  {TEAMS['ESR'][0]}")
    c.setFont(N, 6.5)
    q = fl["quarters"]
    c.drawCentredString(W / 2 + 34, H - 101, "(" + ", ".join(f"{x}-{y}" for x, y in q) + ")")
    # 5-minute scores
    y0 = H - 133
    c.setFont(B, 6.5)
    c.drawString(L + 8, y0 - 9, "Score par intervalles de 5 minutes")
    for k in range(4):
        x = 190 + k * 100
        c.setFont(B, 6.5)
        c.drawString(x + 24, y0 + 6, f"P{k + 1}")
        for i, (code, idx) in enumerate((("JSK", 0), ("ESR", 1))):
            c.setFont(N, 6.5)
            c.drawString(x - 8, y0 - 6 - i * 12, code)
            for m in range(2):
                bx = x + 12 + m * 28
                c.rect(bx, y0 - 9 - i * 12, 24, 10)
                c.drawCentredString(bx + 12, y0 - 6.5 - i * 12, str(fl["five"][k * 2 + m][idx]))

    def table(top, team, coach_lines):
        w = [17, 90, 30] + [28, 22] * 4 + [14, 14, 16] + [13, 13, 13, 13] + [13, 13] + [21, 18, 19]
        xs = [L]
        for v in w:
            xs.append(xs[-1] + v)
        c.setFont(B, 8)
        c.drawString(L, top + 20, f"{TEAMS[team['code']][0]} ({team['code']})")
        c.setFont(B, 6)
        for i, ln in enumerate(coach_lines):
            c.drawRightString(R, top + 20 - 7 * i, ln)
        hh = 10
        c.setFont(B, 6)
        heads1 = [(3, 5, "Tirs Tot."), (5, 7, "2 Points"), (7, 9, "3 pts"), (9, 11, "LF"), (11, 14, "Rebonds"), (18, 20, "Fautes")]
        c.rect(L, top - 2 * hh, xs[-1] - L, 2 * hh)
        for a_, b_, t_ in heads1:
            c.drawCentredString((xs[a_] + xs[b_]) / 2, top - hh + 3, t_)
            c.line(xs[a_], top - hh, xs[b_], top - hh)
        sub = {3: "R/T", 4: "%", 5: "R/T", 6: "%", 7: "R/T", 8: "%", 9: "R/T", 10: "%", 11: "RO", 12: "RD", 13: "TOT", 18: "F", 19: "FP"}
        for i, t_ in sub.items():
            c.drawCentredString((xs[i] + xs[i + 1]) / 2, top - 2 * hh + 3, t_)
        for i, t_ in ((0, "No"), (1, "Nom"), (2, "Min"), (14, "PD"), (15, "BP"), (16, "IN"), (17, "Ctr"), (20, "+/-"), (21, "Ev"), (22, "PTS")):
            c.drawCentredString((xs[i] + xs[i + 1]) / 2, top - hh - 2, t_)
        rh = 11.2
        y = top - 2 * hh
        c.setFont(N, 6.3)
        cols = []
        tot = dict.fromkeys(("min", "fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "pm", "ev", "pts"), 0)
        for p in sorted(team["players"], key=lambda p: p["number"]):
            y -= rh
            printed = names.get((team["code"], p["number"]), "")
            same = bool({w.lower() for w in printed.split()} & {w.lower() for w in p["name"].split()})   # a printed name is used only if it shares a word with the board's name (same person, other spelling)
            nm = printed if same else " ".join(reversed(p["name"].upper().split())) if len(p["name"].split()) == 2 else p["name"].upper()
            ev = ev_of(p)
            vals = [str(p["number"]), nm, f"{int(p['min']):02d}:{round((p['min'] % 1) * 60):02d}",
                    f"{p['fgm']}/{p['fga']}", pct(p["fgm"], p["fga"]), f"{p['p2m']}/{p['p2a']}", pct(p["p2m"], p["p2a"]), f"{p['p3m']}/{p['p3a']}", pct(p["p3m"], p["p3a"]),
                    f"{p['ftm']}/{p['fta']}", pct(p["ftm"], p["fta"]), p["oreb"], p["dreb"], p["reb"], p["ast"], p["tov"], p["stl"], p["blk"], p["pf"], "–", p["pm"], ev, p["pts"]]
            for i, v in enumerate(vals):
                c.setFont(B if i == 22 else N, 6.3)
                if i == 1:
                    c.drawString(xs[i] + 2, y + 3, str(v))
                else:
                    c.drawCentredString((xs[i] + xs[i + 1]) / 2, y + 3, str(v))
            c.line(L, y, xs[-1], y)
            for k in tot:
                tot[k] += ev if k == "ev" else p["min"] * 60 if k == "min" else p[k]
        y -= rh
        c.line(L, y, xs[-1], y)                                         # Equipe/Coach row (team rebounds are not counted on the board)
        c.setFont(N, 6.3)
        c.drawString(xs[1] + 2, y + 3, "Equipe/Coach")
        y -= rh
        c.setFont(B, 6.3)
        vals = {1: "Totaux", 2: "200:00", 3: f"{tot['fgm']}/{tot['fga']}", 4: pct(tot["fgm"], tot["fga"]), 5: f"{tot['p2m']}/{tot['p2a']}", 6: pct(tot["p2m"], tot["p2a"]),
                7: f"{tot['p3m']}/{tot['p3a']}", 8: pct(tot["p3m"], tot["p3a"]), 9: f"{tot['ftm']}/{tot['fta']}", 10: pct(tot["ftm"], tot["fta"]), 11: tot["oreb"], 12: tot["dreb"],
                13: tot["reb"], 14: tot["ast"], 15: tot["tov"], 16: tot["stl"], 17: tot["blk"], 18: tot["pf"], 19: "–", 20: tot["pm"], 21: tot["ev"], 22: tot["pts"]}
        for i, v in vals.items():
            if i == 1:
                c.drawString(xs[i] + 2, y + 3, v)
            else:
                c.drawCentredString((xs[i] + xs[i + 1]) / 2, y + 3, str(v))
        c.line(L, y, xs[-1], y)
        cols = xs
        for xx in cols:                                                 # vertical rules
            c.line(xx, top - 2 * hh, xx, y)
        c.line(L, top - 2 * hh, xs[-1], top - 2 * hh)
        c.rect(L, y, xs[-1] - L, top - 2 * hh - y)
        return y, tot

    coach = {"JSK": ["Entraineur: JEDH EL-HAQ JAOUADI (TUN) (par intérim)"], "ESR": ["Entraineur: AHMED TEBORSKI (TUN)", "Entraineur(s) Adjoints(s): KARIM BEN SALAH (TUN)"]}
    y, t1 = table(H - 196, jsk, coach["JSK"])
    y, t2 = table(y - 52, esr, coach["ESR"])
    # bottom tables
    ty = y - 22
    dash = lambda v: "–" if v is None else v
    left = [("Points de Balles Perdues", a.turnover_pts), ("Points dans la raquette", a.paint), ("Points sur 2eme chance", a.second), ("Pts en contre-attaque", a.fast), ("Points Banc", a.bench)]
    poss = a.poss
    ppp = [f"{jsk['points'] / poss[0]:.2f}".replace(".", ","), f"{esr['points'] / poss[1]:.2f}".replace(".", ",")] if poss else ["–", "–"]
    lead, run, led = fl["lead"], fl["run"], fl["led"]
    sc = lambda s: f"({s[0]}-{s[1]})" if s else ""
    right = [("Avantage Maximum", f"{lead['JSK'][0]} {sc(lead['JSK'][1])}", f"{lead['ESR'][0]} {sc(lead['ESR'][1])}"),
             ("Serie Maximum", f"{run['JSK'][0]} {sc(run['JSK'][1])}", f"{run['ESR'][0]} {sc(run['ESR'][1])}"),
             ("Points per Possession", ppp[0], ppp[1]), ("Changements de Leader", str(fl["changes"]), ""), ("Egalites", str(fl["ties"]), ""),
             ("Amene au score durant", mmss(led["JSK"]), mmss(led["ESR"]))]

    def box(x0, rows, head):
        w = 250
        c.setFont(B, 6.5)
        c.rect(x0, ty - 12, w, 12)
        c.drawCentredString(x0 + w * 0.65, ty - 9, head[0])
        c.drawCentredString(x0 + w * 0.88, ty - 9, head[1])
        yy = ty - 12
        for lab, v1, v2 in rows:
            yy -= 11.5
            c.rect(x0, yy, w, 11.5)
            c.setFont(N, 6.5)
            c.drawCentredString(x0 + w * 0.28, yy + 3.5, lab)
            c.drawCentredString(x0 + w * 0.65, yy + 3.5, str(v1))
            c.drawCentredString(x0 + w * 0.88, yy + 3.5, str(v2))
            c.line(x0 + w * 0.52, yy, x0 + w * 0.52, yy + 11.5)
            c.line(x0 + w * 0.77, yy, x0 + w * 0.77, yy + 11.5)
        return yy

    pair = lambda t: (dash(t[0]), dash(t[1])) if t else ("–", "–")
    box(L, [(lab, *pair(v)) for lab, v in left], ("JSK", "ESR"))
    yy = box(R - 250, right, ("JSK", "ESR"))
    # legend
    ly = yy - 18
    c.setFont(B, 7)
    c.drawString(L, ly, "Legende")
    leg = [("No", "Numero Maillot"), ("Min", "Minutes Jouees"), ("R/T", "Reussis / Tentes"), ("%", "Pourcentage aux Tirs"), ("RO", "Rebonds Offensifs"), ("RD", "Rebonds Defensifs"),
           ("TOT", "Total Rebonds"), ("PD", "Passes Decisives"), ("BP", "Balles Perdues"), ("IN", "Interceptions"), ("Ctr", "Contres"), ("F", "Fautes Personnelles"),
           ("FP", "Fautes Provoquees"), ("+/-", "Plus / Moins"), ("Ev", "Evaluation"), ("PTS", "Points")]
    c.setFont(N, 6)
    for i, (k, v) in enumerate(leg):
        r_, col = i // 4, i % 4
        c.setFont(B, 6)
        c.drawString(L + col * 125, ly - 10 - r_ * 9, k)
        c.setFont(N, 6)
        c.drawString(L + col * 125 + 22, ly - 10 - r_ * 9, v)
    ny = ly - 52
    notes = [f"NOTES — Feuille finale établie par Tunisia Basket à partir du comptage manuel du match (Journée {game['matchday_no']}), remplaçant la version provisoire établie à partir de la vidéo.",
             "• Score, points par joueur, minutes, +/-, rebonds, passes, interceptions, contres, balles perdues et fautes : comptage manuel. Fautes provoquées : non relevées (–).",
             "• Points banc : feuille de comptage manuscrite. Les cases laissées à « – » n'ont pas été relevées.",
             "• Avantage maximum, série maximum, changements de leader, égalités et temps mené : calculés à partir de la chronologie des paniers, vérifiée sur vidéo.",
             "• Possessions (pour les points par possession) : suivi sur vidéo, 66 pour JSK et 65 pour ESR." if poss else ""]
    notes = [n for n in notes if n]
    c.setFillColorRGB(1, 0.97, 0.9)
    c.setStrokeColorRGB(0.85, 0.6, 0.2)
    c.rect(L, ny - 9 * len(notes) - 4, R - L, 9 * len(notes) + 10, fill=1)
    c.setFillColorRGB(0, 0, 0)
    for i, n in enumerate(notes):
        c.setFont(B if i == 0 else N, 6)
        c.drawString(L + 6, ny - 5 - i * 9, n)
    c.showPage()
    c.save()


def pair_arg(s):
    return tuple(int(x) for x in s.split(":")) if s else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--id", required=True)
    ap.add_argument("--matchday", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--venue", required=True)
    ap.add_argument("--names-from", help="a federation-style sheet whose printed names are used on the PDF")
    ap.add_argument("--timeline-pdf", required=True)
    ap.add_argument("--set", action="append", help="TEAM:NUMBER:field=value")
    ap.add_argument("--bench", type=pair_arg)
    ap.add_argument("--paint", type=pair_arg)
    ap.add_argument("--second", type=pair_arg)
    ap.add_argument("--fast", type=pair_arg)
    ap.add_argument("--turnover-pts", type=pair_arg)
    ap.add_argument("--poss", type=pair_arg, help="tracked possessions JSK:ESR")
    ap.add_argument("--out-dir", default=str(ROOT / "exports"))
    a = ap.parse_args()
    teams = read_csv(a.csv, a.set)
    game = {"competition": "CHAMPIONNAT DE TUNISIE PRO A SENIORS", "date": a.date, "date_approx": False, "id": a.id, "matchday": f"J{a.matchday}", "matchday_no": a.matchday,
            "source": "claude", "source_file": "FIBA Box Score JSK vs ESR (final) - manual count", "uploaded": True, "teams": []}
    for code in ("JSK", "ESR"):
        pl = teams[code]
        game["teams"].append({"code": code, "name": TEAMS[code][1], "coach": "", "points": sum(p["pts"] for p in pl), "players": pl})
    problems = validate(game)
    for t in game["teams"]:
        print(t["code"], t["points"], "pts,", len(t["players"]), "players")
    if problems:
        sys.exit("REFUSED:\n  " + "\n  ".join(problems))
    fl = derive(flow(a.timeline_pdf), (game["teams"][0]["points"], game["teams"][1]["points"]))
    names = name_map(a.names_from) if a.names_from else {}
    out = Path(a.out_dir)
    (out / "games_inbox").mkdir(parents=True, exist_ok=True)
    (out / "games_inbox" / f"{a.id}.json").write_text(json.dumps(game, indent=1, ensure_ascii=False))
    pdf(out / f"FIBA Box Score {game['teams'][0]['code']} vs {game['teams'][1]['code']} (final).pdf", game, names, fl, a)
    print("flow:", fl["quarters"], "lead", fl["lead"], "run", fl["run"], "changes", fl["changes"], "ties", fl["ties"], "led", {k: mmss(v) for k, v in fl["led"].items()})
    print("written ->", out)


if __name__ == "__main__":
    main()
