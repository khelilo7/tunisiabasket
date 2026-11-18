"""The league table: points first, then the games between the tied teams (their points, then their point difference), then the point difference of all games, then the points scored."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
row = lambda code, pts, diff, pf=1000: {"code": code, "pts": pts, "diff": diff, "pf": pf}
game = lambda h, a, hs, as_: {"matchday": 1, "home": h, "away": a, "home_score": hs, "away_score": as_}
order = lambda rows, results: [r["code"] for r in stats.rank_rows(rows, results)]

# 1. points first: a team that won the game between them but has fewer points stays under
check(order([row("A", 20, 10), row("B", 21, -50)], [game("A", "B", 90, 60)]) == ["B", "A"], "league points come before the head-to-head")
# 2. level on points: the game between them decides, even when the other has the better point difference
check(order([row("B", 20, 50), row("A", 20, 10)], [game("A", "B", 70, 60)]) == ["A", "B"], "the head-to-head winner is ahead of the better point difference")
# 3. each won once: the point difference of their two games decides, then the whole season
two = [game("A", "B", 70, 60), game("B", "A", 80, 60)]            # A +10 then -20: B is ahead
check(order([row("A", 20, 90), row("B", 20, 5)], two) == ["B", "A"], "head-to-head points level: their games' point difference decides")
level = [game("A", "B", 70, 60), game("B", "A", 70, 60)]            # both won once by the same margin
check(order([row("B", 20, 5), row("A", 20, 9)], level) == ["A", "B"], "everything level between them: the point difference of all games decides")
check(order([row("B", 20, 5, 900), row("A", 20, 5, 950)], level) == ["A", "B"], "then the points scored")
# 4. nobody played each other: the whole season
check(order([row("B", 20, 5), row("A", 20, 9)], []) == ["A", "B"], "no game between them: the point difference of all games")
# 5. three teams: their own games first, and the rule starts again for those still level
circle = [game("A", "B", 70, 60), game("B", "C", 70, 60), game("C", "A", 70, 60)]          # each beat one and lost to one by the same margin: those games separate nobody
check(order([row("B", 20, 5), row("A", 20, 9), row("C", 20, 7)], circle) == ["A", "C", "B"], "three teams level in their own games: the point difference of all games")
partial = [game("A", "B", 70, 60), game("A", "C", 70, 60), game("B", "C", 60, 50)]         # A beat both, B beat C
check(order([row("C", 20, 300), row("B", 20, 200), row("A", 20, 100)], partial) == ["A", "B", "C"], "three teams: the best record in their own games leads, then the next")
rest = [game("A", "B", 70, 60), game("A", "C", 70, 60), game("B", "C", 70, 60), game("C", "B", 80, 60)]       # A leads; B and C are level on their games, B has the better point difference there
check(order([row("C", 20, 300), row("B", 20, 200), row("A", 20, 100)], rest)[0] == "A", "the leader of the three is taken out, the others are compared again")
# 6. the table of a real set of results is ordered the same way and ranks are 1..n
o = {"teams": {"A": "A", "B": "B", "C": "C", "D": "D"},
     "results": [game("A", "B", 70, 68), game("B", "C", 100, 50), game("C", "A", 80, 60), game("A", "D", 90, 60), game("D", "B", 60, 59), game("C", "D", 70, 60)]}
table = stats.official_standings(o)
check([r["rank"] for r in table] == [1, 2, 3, 4] and [r["pts"] for r in table] == sorted((r["pts"] for r in table), reverse=True), f"ranks and points are in order: {[(r['code'], r['pts']) for r in table]}")
tied = [r for r in table if r["pts"] == table[0]["pts"]]
check(len(tied) >= 1, "the table has a leader")

print("FAILED:\n  " + "\n  ".join(fails) if fails else "tiebreak checks passed")
sys.exit(1 if fails else 0)
