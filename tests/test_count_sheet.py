"""tools/count_sheet.py: a board CSV becomes a checked game; a typed cell that contradicts the points is refused; the game flow (lead, runs, ties) comes from the scoring timeline."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import count_sheet as cs  # noqa: E402
from validate import validate  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
FX = ROOT / "tests" / "fixtures"


def game(sets):
    teams = cs.read_csv(FX / "count_jsk_esr_j13.csv", sets)
    return {"date": "2026-11-14", "matchday_no": 13, "teams": [{"code": c, "name": c, "coach": "", "points": sum(p["pts"] for p in teams[c]), "players": teams[c]} for c in ("JSK", "ESR")]}


# 1. as typed, two ESR rows contradict their own points (Mabrouk 7 FG with 4 threes = 19, not 17; K. Rouissi 3 FG with 1 three = 7, not 9): refused
bad = validate(game([]))
check(len(bad) == 2 and any("Mabrouk" in b for b in bad) and any("Rouissi" in b for b in bad), f"the two inconsistent rows are refused: {bad}")
# 2. the two swapped FG cells corrected (the team's FG total does not change): every check passes
g = game(["ESR:8:fgm=6", "ESR:8:fga=15", "ESR:1:fgm=4", "ESR:1:fga=11", "ESR:1:p3a=6"])
check(validate(g) == [], f"corrected: {validate(g)}")
check([t["points"] for t in g["teams"]] == [69, 60] and [len(t["players"]) for t in g["teams"]] == [10, 8], "69-60, ten and eight players")
mab = next(p for p in g["teams"][1]["players"] if p["number"] == 8)
check((mab["p2m"], mab["p2a"], mab["p3m"], mab["p3a"], mab["pts"]) == (2, 7, 4, 8, 17), "Mabrouk 2/7 two-pointers, 4/8 threes, 17 points")
kr = next(p for p in g["teams"][1]["players"] if p["number"] == 1)
check((kr["p2m"], kr["p2a"], kr["p3m"], kr["p3a"], kr["pts"]) == (3, 5, 1, 6, 9), "Khalil Rouissi 3/5 two-pointers, 1/6 threes, 9 points")
# 3. the flow of the game from the scoring timeline
fl = cs.derive(cs.flow(FX / "video_analysis_jsk_esr_j13.pdf"), (69, 60))
check(fl["quarters"] == [(21, 12), (21, 28), (16, 12), (11, 8)], f"quarter scores {fl['quarters']}")
check(fl["lead"]["JSK"] == (13, (39, 26)) and fl["lead"]["ESR"][0] == 7 and fl["changes"] == 4 and fl["ties"] == 3, f"lead, changes, ties: {fl}")
check(abs(sum(fl["led"].values()) - 2400) < 400, "time in the lead is below the 40 minutes (the rest is ties)")
check(fl["five"][0] == (4, 6) and fl["five"][-1] == (69, 60), "score with 5:00 left in Q1 is 4-6, final 69-60")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("count sheet checks passed")
