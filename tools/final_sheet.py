"""Read a corrected full box score made by Tunisia Basket ("FIBA Box Score ... (final).pdf", French labels: Tirs Tot., 2 Points, 3 pts, LF, Rebonds, Fautes, +/-, Ev, PTS)
and write it as a game JSON that REPLACES the version already on the site (same game id).

    python tools/final_sheet.py "FIBA Box Score CA vs ESG 11 novembre (final).pdf" --like exports/games_inbox/hand-j12-ca-esg.json [--out FILE]

--like is the JSON of the version being replaced: its game id, date, team names and player names are kept (the site matches players by team + jersey number and name, so
the same names keep the same profiles); the numbers come from the PDF. Every sheet check runs (points, rebounds, FG = 2P + 3P, the printed EF, team totals line); the game is refused if one fails.
Stored as source "claude" (a transcribed box score, no video banner). The "Equipe/Coach" row (team rebounds, team turnovers) is kept in not_attributed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from validate import validate  # noqa: E402

TEAM = re.compile(r"^([A-ZÉ' ]+?)\s*\(([A-Z]{2,5})\)\s+Entraineur:\s*(.*)$")
ROW = re.compile(r"^(\*)?(\d+)\s+(.+?)\s+(\d\d):(\d\d)\s+((?:\d+/\d+\s+[\d,]+\s+){4})((?:-?\d+\s*){12})$")
KEYS = ("oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "ef", "pts")   # RO RD TOT PD BP IN Ctr F FP +/- Ev PTS


def parse(path):
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    teams, cur = [], None
    for ln in (l.strip() for l in text.splitlines()):
        h = TEAM.match(ln)
        if h:
            cur = {"code": h.group(2), "name": None, "coach": "", "players": [], "points": None, "totals": None, "team_row": None}
            teams.append(cur)
            continue
        if cur is None:
            continue
        if ln.startswith("Equipe/Coach"):
            cur["team_row"] = [int(x) for x in ln.split()[1:]]          # RO RD TOT BP
            continue
        if ln.startswith("Totaux"):
            cur["points"] = int(ln.split()[-1])
            cur["totals"] = ln.split()
            cur = None
            continue
        m = ROW.match(ln)
        if not m:
            continue
        star, no, name, mm, ss, shots, tail = m.groups()
        fr = [tuple(int(v) for v in x.split("/")) for x in re.findall(r"\d+/\d+", shots)]
        nums = dict(zip(KEYS, (int(x) for x in tail.split())))
        (fgm, fga), (p2m, p2a), (p3m, p3a), (ftm, fta) = fr
        captain = "(C)" in name
        p = {"number": int(no), "name": re.sub(r"\s*\(C\)\s*", "", name).strip(), "starter": bool(star), "captain": captain, "dnp": False, "min": round(int(mm) + int(ss) / 60, 2),
             "fgm": fgm, "fga": fga, "p2m": p2m, "p2a": p2a, "p3m": p3m, "p3a": p3a, "ftm": ftm, "fta": fta, "stl": nums["stl"], "blk": nums["blk"], **{k: nums[k] for k in KEYS if k not in ("stl", "blk", "ef")},
             "_ef": nums["ef"]}
        cur["players"].append(p)
    if len(teams) != 2 or any(t["points"] is None for t in teams):
        raise SystemExit(f"expected 2 teams with a totals line, found {len(teams)}")
    return text, teams


def build(path, like):
    text, teams = parse(path)
    old = json.loads(Path(like).read_text())
    by = {t["code"]: t for t in old["teams"]}
    d, mon, y = re.search(r"(\d+)\s+([a-zéû]+)\.?\s+(\d{4})", text).groups()
    month = {"janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12, "déc": 12}[mon]
    assert f"{y}-{month:02d}-{int(d):02d}" == old["date"], f"the date on the sheet ({d} {mon} {y}) is not the date of the version being replaced ({old['date']})"
    out = {k: v for k, v in old.items() if k != "teams"}
    out["source"] = "claude"
    out["source_file"] = Path(path).name
    out["teams"] = []
    for t in teams:
        o = by[t["code"]]
        names = {p["number"]: p["name"] for p in o["players"]}
        for p in t["players"]:
            p["name"] = names.get(p["number"], p["name"])
        team_row = t["team_row"] or [0, 0, 0, 0]
        out["teams"].append({"code": t["code"], "name": o["name"], "coach": o.get("coach", ""), "points": t["points"], "players": t["players"],
                             "not_attributed": {"fga": 0, "pts": 0, "tov": team_row[3], "team_reb": team_row[2]}})
        # the sheet's own totals line must equal the sum of its rows (+ the team row for rebounds and turnovers)
        s = lambda k: sum(p[k] for p in t["players"])
        ro, rd, rt, pd_, bp = (int(x) for x in t["totals"][-12:-7])      # after the four shooting pairs: RO RD TOT PD BP IN Ctr F FP +/- Ev PTS
        assert (s("oreb") + team_row[0], s("dreb") + team_row[1], s("reb") + team_row[2], s("ast"), s("tov") + team_row[3]) == (ro, rd, rt, pd_, bp), f"{t['code']}: totals line"
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf")
    ap.add_argument("--like", required=True, help="JSON of the version being replaced")
    ap.add_argument("--out")
    a = ap.parse_args()
    g = build(a.pdf, a.like)
    problems = validate(g)
    for t in g["teams"]:
        print(t["code"], t["points"], "pts,", len(t["players"]), "players")
    if problems:
        sys.exit("REFUSED:\n  " + "\n  ".join(problems))
    for t in g["teams"]:
        for p in t["players"]:
            p.pop("_ef", None)
    out = Path(a.out or a.like)
    out.write_text(json.dumps(g, indent=1, ensure_ascii=False))
    print("all checks passed ->", out)


if __name__ == "__main__":
    main()
