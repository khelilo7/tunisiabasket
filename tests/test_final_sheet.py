"""tools/final_sheet.py reads a corrected French box score and replaces the version already on the site; tools/fix_player_stat.py changes one stat of one player and nothing else."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import final_sheet  # noqa: E402
import fix_player_stat  # noqa: E402
from validate import validate  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
FX = ROOT / "tests" / "fixtures"

# 1. the corrected CA 93-68 ESG sheet: arithmetic passes (including the printed Ev of every player), and only three ESG free-throw lines differ from the version it replaces
new = final_sheet.build(FX / "final_ca_esg_j12.pdf", FX / "j12_ca_esg_before_correction.json")
check(validate(new) == [], f"checks pass: {validate(new)}")
old = json.loads((FX / "j12_ca_esg_before_correction.json").read_text())
check(new["id"] == old["id"] == "d20ab1f2d47d039e" and new["date"] == "2026-11-11" and new["source"] == "claude", "same game id and date, source claude")
F = ("min", "fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts", "starter", "captain")
changed = sorted((t["code"], p["number"]) for t, to in zip(new["teams"], old["teams"]) for p, po in zip(t["players"], to["players"]) if any(p.get(f) != po.get(f) for f in F if f != "min"))
check(changed == [("ESG", 4), ("ESG", 6), ("ESG", 30)], f"only Ben Makhlouf, Marmouch and Temim change: {changed}")
bm = next(p for t in new["teams"] if t["code"] == "ESG" for p in t["players"] if p["number"] == 4)
check((bm["ftm"], bm["fta"], bm["pts"]) == (2, 2, 5), "Ben Makhlouf 2/2 free throws, 5 points")
check([t["not_attributed"]["tov"] for t in new["teams"]] == [1, 1] and [t["not_attributed"]["team_reb"] for t in new["teams"]] == [6, 2], "team rows kept (turnovers 1 and 1, team rebounds 6 and 2)")

# 2. fix_player_stat: reb follows dreb, nothing else moves, and a bad number is refused by the checks
api = {"id": "x1234567", "date": "2026-11-03", "date_approx": True, "matchday": "J10", "matchday_no": 10, "source": "ocr", "source_file": "f.pdf", "competition": "",
       "teams": [{"code": c, "name": c, "coach": "", "points": 10, "box_points": 10, "won": c == "AAA", "players": [
           {"number": 1, "name": "P One", "starter": True, "captain": False, "dnp": False, "min": 200.0, "fgm": 5, "fga": 9, "p2m": 5, "p2a": 9, "p3m": 0, "p3a": 0, "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0, "reb": 0,
            "ast": 0, "tov": 0, "stl": 0, "blk": 0, "pf": 0, "fd": 0, "pm": 0, "pts": 10, "pir": 3, "rating": 50, "pid": "aaa-1", "impact": 1}]} for c in ("AAA", "BBB")]}
g = fix_player_stat.rebuild(api)
check("pir" not in g["teams"][0]["players"][0] and g["id"] == "x1234567" and g["source"] == "ocr", "derived fields are not stored back, id and source kept")
g["teams"][0]["players"][0]["dreb"] = 3
g["teams"][0]["players"][0]["reb"] = 3
check(validate(g) == [], "after the change the checks pass")
g["teams"][0]["players"][0]["reb"] = 2
check(validate(g) != [], "reb != oreb + dreb is refused")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("final sheet checks passed")
