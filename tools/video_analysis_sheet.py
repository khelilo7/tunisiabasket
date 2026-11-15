"""Read a "FIBA Box Score ... Final: video analysis" PDF (Tunisia Basket, round N) into a game JSON for exports/games_inbox/.

    python tools/video_analysis_sheet.py "FIBA Box Score JSK vs ESR (final).pdf" --date 2026-11-14 [--out exports/games_inbox/video-j13-jsk-esr.json]

This sheet differs from the older "(from video)" ones (video_sheet.py): no "Journée N" but "Round N"; minutes are printed "~31"; attempts carry a "*" (makes + the misses the
commentator named, so they are LOWER than the real ones); blank cells mean 0; +/- and EF are "–" (not computed, stored as 0); no starters. Columns are read by their x position
under the header because blanks make the text line ambiguous. Every sheet check (points, rebounds, FG = 2P + 3P, team totals) is run; the game is refused if one fails.
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

NOTE = ("Compiled by Tunisia Basket from the broadcast video, not from the official table sheet: minutes are estimates, +/- is not available, and shooting attempts, "
        "rebounds, assists, turnovers and fouls are minimum counts (only what the commentary identified).")
TEAM = re.compile(r"^(.+?)\s*\(([A-Z]{2,5})\)\s+Coach:\s*(.*)$")
FRACTION = re.compile(r"^(\d+)/(\d+)\*?$")
COUNT_COLS = ("oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd")


def _columns(words):
    """x centre of every counting column, from the header words of the first team table."""
    top = next(w["top"] for w in words if w["text"] == "OR")
    heads = {w["text"]: (w["x0"] + w["x1"]) / 2 for w in words if abs(w["top"] - top) < 3}
    cols = {k: heads[h] for k, h in (("oreb", "OR"), ("dreb", "DR"), ("reb", "TOT"), ("pf", "PF"), ("fd", "FD"))}
    above = {w["text"]: (w["x0"] + w["x1"]) / 2 for w in words if abs(w["top"] - (top - 5)) < 3}   # AS TO ST BS span two header rows: they sit on the line above
    for k, h in (("ast", "AS"), ("tov", "TO"), ("stl", "ST"), ("blk", "BS")):
        cols[k] = above[h]
    return cols


def _nearest(x, cols):
    k = min(cols, key=lambda c: abs(cols[c] - x))
    return k if abs(cols[k] - x) < 7 else None


def parse(path):
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""
        words = page.extract_words()
    m = re.search(r"Round\s+(\d+)", text)
    if not m or "video analysis" not in text.lower():
        raise SystemExit("not a 'Round N ... video analysis' sheet")
    md = int(m.group(1))
    cols = _columns(words)
    lines = []
    for w in sorted(words, key=lambda w: w["top"]):          # words whose tops are within 3 pt belong to one printed line
        if lines and w["top"] - lines[-1][0]["top"] <= 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    teams, cur = [], None
    for ln in lines:
        ln.sort(key=lambda w: w["x0"])
        flat = " ".join(w["text"] for w in ln)
        h = TEAM.match(flat)
        if h:
            cur = {"code": h.group(2), "name": h.group(1).strip(), "coach": h.group(3).strip(), "players": [], "points": None,
                   "not_attributed": {"fga": 0, "pts": 0, "tov": 0, "team_reb": 0}}
            teams.append(cur)
            continue
        if cur is None:
            continue
        if flat.startswith("Totals"):
            cur["points"] = int(re.sub(r"\D", "", ln[-1]["text"]))
            cur = None
            continue
        if not re.match(r"^\d+$", ln[0]["text"]) or ln[0]["x0"] > 60:
            continue
        fr = [w for w in ln if w["x0"] > 190 and w["x0"] < 375 and FRACTION.match(w["text"].replace(",", "."))]
        shots = [tuple(int(v) for v in FRACTION.match(w["text"]).groups()) for w in fr]
        if len(shots) != 4:
            raise SystemExit(f"unreadable shooting cells: {flat}")
        mins = next((w["text"] for w in ln if w["text"].startswith("~")), None)
        name = " ".join(w["text"] for w in ln if 60 < w["x0"] < 168)
        captain = "(C)" in name
        name = re.sub(r"\s*\(C\)\s*", " ", name).strip()
        counts = dict.fromkeys(COUNT_COLS, 0)
        for w in ln:
            if w["x0"] > 372 and w["x1"] < 497 and re.fullmatch(r"\d+", w["text"]):
                k = _nearest((w["x0"] + w["x1"]) / 2, cols)
                if k:
                    counts[k] = int(w["text"])
        pts = int(re.sub(r"\D", "", ln[-1]["text"]))
        (fgm, fga), (p2m, p2a), (p3m, p3a), (ftm, fta) = shots
        cur["players"].append({
            "number": int(ln[0]["text"]), "name": name, "starter": False, "captain": captain, "dnp": False, "min": round(int(re.sub(r"\D", "", mins or "0")), 2),
            "fgm": fgm, "fga": fga, "p2m": p2m, "p2a": p2a, "p3m": p3m, "p3a": p3a, "ftm": ftm, "fta": fta, **counts, "pm": 0, "pts": pts})
    if len(teams) != 2 or any(t["points"] is None for t in teams):
        raise SystemExit(f"expected 2 teams with a totals line, found {len(teams)}")
    return {"competition": "CHAMPIONNAT DE TUNISIE PRO A SENIORS", "date": None, "teams": teams, "source": "video", "note": NOTE, "matchday_no": md, "matchday": f"J{md}",
            "date_approx": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf")
    ap.add_argument("--date", required=True, help="real day of the game, YYYY-MM-DD (official calendar)")
    ap.add_argument("--out")
    a = ap.parse_args()
    g = parse(a.pdf)
    g["date"] = a.date
    c0, c1 = (t["code"].lower() for t in g["teams"])
    g["id"] = f"video-j{g['matchday_no']}-{c0}-{c1}"
    g["source_file"] = Path(a.pdf).name
    g["uploaded"] = True
    problems = validate(g)
    for t in g["teams"]:
        print(t["code"], t["points"], "pts,", len(t["players"]), "players, minutes", sum(p["min"] for p in t["players"]))
    if problems:
        sys.exit("REFUSED:\n  " + "\n  ".join(problems))
    out = Path(a.out or ROOT / "exports" / "games_inbox" / f"{g['id']}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, indent=1, ensure_ascii=False))
    print("all checks passed ->", out)


if __name__ == "__main__":
    main()
