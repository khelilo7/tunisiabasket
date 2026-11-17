"""tools/fix_from_csv.py: the board CSV wins for the columns it has, everything else the site has (minutes, +/-, drawn fouls, DNP rows) stays."""
import copy
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import fix_from_csv as f  # noqa: E402
from validate import validate  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
rows = f.read_rows(ROOT / "tests" / "fixtures" / "board_ess_ca_j13.csv")
check(len(rows) == 19 and rows[("ESS", 41)]["p2m"] == 4 and rows[("ESS", 41)]["p2a"] == 8, "19 rows; 2P is FG minus 3P")

# a game as the site had it: one wrong row per team, minutes / +/- / drawn fouls the CSV does not carry, a DNP row
def player(team, n):
    r = rows[(team, n)]
    return {"number": n, "name": f"{team} {n}", "starter": False, "captain": False, "dnp": False, "min": 10.0, "fd": 2, "pm": -3, **r}
game = {"teams": [{"code": c, "name": c, "points": sum(r["pts"] for (t, _), r in rows.items() if t == c),
                   "players": [player(c, n) for (t, n) in rows if t == c] + [{"number": 21, "name": "Bench", "dnp": True}]} for c in ("ESS", "CA")]}
for t in game["teams"]:
    t["players"][0]["min"] = 195 / 9  # minutes in range
    for p in t["players"][:-1]:
        p["min"] = round(200 / len(t["players"][:-1]), 2)
check(validate(game) == [], f"the starting point is valid: {validate(game)}")
old = copy.deepcopy(game)
slim = next(p for p in game["teams"][0]["players"] if p["number"] == 45)
slim["blk"], slim["ast"] = 4, 9                       # wrong on the site
kissi = next(p for p in game["teams"][0]["players"] if p["number"] == 0)
kissi["p3a"], kissi["p2a"] = 1, 3                     # wrong on the site (fga unchanged)
log = f.apply(game, rows, ["ESS:45:blk=1"])
check(slim["blk"] == 1 and slim["ast"] == 1, f"Slimane block set by --set (1), assists from the CSV (1): {slim}")
check(kissi["p3a"] == 2 and kissi["p2a"] == 2, "Kissi 3PA 2 and 2PA 2 from the CSV")
check(all(p.get("min") == o.get("min") and p.get("pm") == o.get("pm") and p.get("fd") == o.get("fd") for t, u in zip(game["teams"], old["teams"]) for p, o in zip(t["players"], u["players"])), "minutes, +/-, drawn fouls untouched")
check(game["teams"][0]["players"][-1] == {"number": 21, "name": "Bench", "dnp": True}, "the DNP row stays")
check(any("Kissi" in x or "ESS #0" in x for x in log) and validate(game) == [], f"valid after: {validate(game)}")
# 2. a player the CSV has but the game does not: refused, nothing guessed
short = copy.deepcopy(old)
short["teams"][0]["players"] = [p for p in short["teams"][0]["players"] if p["number"] != 45]
try:
    f.apply(short, rows)
    check(False, "a CSV player missing from the game is refused")
except SystemExit as e:
    check("ESS #45" in str(e), f"names the missing player: {e}")

# 3. --made-only: makes and points from the CSV, the site's misses kept, other counts only go up, a missing player is added
mrows = f.read_rows(ROOT / "tests" / "fixtures" / "board_usm_css_j13.csv")
mnames = f.read_names(ROOT / "tests" / "fixtures" / "board_usm_css_j13.csv")
def usm(n, **kw):
    z = {"number": n, "name": f"P{n}", "starter": False, "captain": False, "dnp": False, "min": 20.0, "fd": 0, "pm": 0, "fgm": 0, "fga": 0, "p2m": 0, "p2a": 0, "p3m": 0, "p3a": 0, "ftm": 0, "fta": 0,
         "oreb": 0, "dreb": 0, "reb": 0, "ast": 0, "tov": 0, "stl": 0, "blk": 0, "pf": 0, "pts": 0}
    z.update(kw)
    return z
mgame = {"teams": [{"code": "USM", "name": "USM", "points": 79, "players": [
    usm(32, p2m=2, p2a=5, p3m=1, p3a=4, fgm=3, fga=9, pts=7, oreb=1, dreb=1, reb=2, ast=1, stl=1, tov=2, pf=1),   # Addami: 3 missed twos, 3 missed threes on the site
    usm(23, p2m=5, p2a=7, p3m=2, p3a=6, fgm=7, fga=13, ftm=3, fta=4, pts=19, oreb=2, dreb=6, reb=8, ast=5, stl=4),  # Lahyani: the CSV has fewer rebounds, assists, steals: nothing goes down
    usm(5, p2m=1, p2a=2, p3m=0, p3a=4, fgm=1, fga=6, pts=2, ast=3),                                               # Ilehi: CSV has 4 assists
    {"number": 12, "name": "Gadour", "dnp": True}, usm(1, fgm=0), usm(6), usm(11), usm(13), usm(33)]},
    {"code": "CSS", "name": "CSS", "points": 0, "players": [usm(3)]}]}
mlog = f.apply_made_only(mgame, mrows, mnames)
ad = next(p for p in mgame["teams"][0]["players"] if p["number"] == 32)
check((ad["p2m"], ad["p2a"], ad["p3m"], ad["p3a"], ad["pts"], ad["fgm"], ad["fga"]) == (4, 7, 1, 4, 11, 5, 11), f"Addami: 4 twos (3 misses kept), same threes, 11 points: {ad}")
la = next(p for p in mgame["teams"][0]["players"] if p["number"] == 23)
check((la["oreb"], la["dreb"], la["ast"], la["stl"], la["reb"]) == (2, 6, 5, 4, 8), "numbers the CSV has lower are not lowered")
il = next(p for p in mgame["teams"][0]["players"] if p["number"] == 5)
check(il["ast"] == 4 and il["fga"] == 6 and il["fgm"] == 1, "Ilehi: 4th assist added, his 5 misses stay")
aj = next((p for p in mgame["teams"][0]["players"] if p["number"] == 9), None)
check(aj and aj["name"] == "Islem Ajmi" and aj["min"] == 0 and aj["pts"] == 2 and aj["fgm"] == 1, f"Islem Ajmi added with 0 minutes and 2 points: {aj}")
check(mgame["teams"][0]["players"][-1] is aj and {"number": 12, "name": "Gadour", "dnp": True} in mgame["teams"][0]["players"], "the DNP row stays, the new player is last")
check(all(p["number"] == 3 for p in mgame["teams"][1]["players"]) and mgame["teams"][1]["players"][0]["pts"] == 0, "the other team is untouched")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("fix from csv checks passed")
