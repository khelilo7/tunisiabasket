"""Rules of the competition and of the MVP, checked on the seed data."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import stats  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


off = json.loads((root / "seed" / "official.json").read_text())
check(len(off["results"]) == 66, "official results: expected 66 (11 matchdays x 6)")
per = {}
for r in off["results"]:
    per.setdefault(r["matchday"], []).append(r)
check(all(len(v) == 6 for v in per.values()), "every matchday must have 6 games")
for md, games in per.items():
    teams = [t for g in games for t in (g["home"], g["away"])]
    check(len(set(teams)) == 12, f"matchday {md}: every team must play exactly once")

table = stats.official_standings()
exp = {"CA": (10, 21), "JSK": (10, 21), "USM": (9, 20), "ESS": (8, 19), "DSG": (6, 17), "CSS": (6, 17),
       "ESG": (6, 17), "SN": (4, 15), "JSM": (3, 14), "ESR": (2, 13), "USA": (1, 12), "CSHS": (1, 12)}
check([r["code"] for r in table][:4] == ["CA", "JSK", "USM", "ESS"], "top 4 must be CA, JSK, USM, ESS")
for r in table:
    check((r["w"], r["pts"]) == exp[r["code"]], f"standing of {r['code']}: {(r['w'], r['pts'])} != {exp[r['code']]}")
check(sum(r["diff"] for r in table) == 0, "goal differences must add up to 0")

d = stats.build()
check(d["top_teams"] == ["CA", "JSK", "USM", "ESS"], "MVP pool teams")
pool = [p for p in d["players"] if p["mvp_eligible"]]
check(bool(pool) and all(p["team"] in d["top_teams"] for p in pool), "MVP pool must only contain top-4 players")
check(all(g["mvp"]["team"] in [t["code"] for t in g["teams"] if t["won"]] for g in d["games"] if g["mvp"]),
      "a game MVP must come from the winning team")
check(len(d["games"]) == 48, f"expected 48 box scores in the seed, got {len(d['games'])}")

plan = stats.planning()
check(plan["projected"] and [m["matchday"] for m in plan["matchdays"]] == list(range(12, 23)), "planning must cover J12-J22")
for code in off["teams"]:
    up = stats.team_view(code)["upcoming"]
    check(len(up) == 11 and len({u["opp"] for u in up}) == 11, f"{code}: 11 upcoming games vs 11 different opponents")

print("stats:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
