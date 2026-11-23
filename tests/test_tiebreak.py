"""The league table follows the FTBB's law (ranking.py: Règlements Généraux 10/08/2024, art. 182-184, 194)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ranking  # noqa: E402
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
game = lambda h, a, hs, as_, **k: {"matchday": 1, "home": h, "away": a, "home_score": hs, "away_score": as_, **k}
row = lambda code, pts, diff, pf=1000: {"code": code, "pts": pts, "pf": pf, "pa": pf - diff}
order = lambda rows, results: [r["code"] for r in ranking.rank(rows, results)]

# art. 182-183: the points come first, whatever happened between the teams
check(order([row("A", 20, 10), row("B", 21, -50)], [game("A", "B", 90, 60)]) == ["B", "A"], "points before everything else")
# art. 184-1: two teams level on points: the goal difference of the games between them, even when the other has the better difference over the season
check(order([row("B", 20, 50), row("A", 20, 10)], [game("A", "B", 70, 60)]) == ["A", "B"], "two teams: the games between them first")
# the two games together count (A won by 10, then lost by 20: B is ahead, although each won once and A has the far better season)
check(order([row("A", 20, 90), row("B", 20, 5)], [game("A", "B", 70, 60), game("B", "A", 80, 60)]) == ["B", "A"], "two teams: the goal difference of their games, not who won more of them")
# art. 184-2: level between them (each won by 10): the goal difference of all the games, then the points scored
level = [game("A", "B", 70, 60), game("B", "A", 70, 60)]
check(order([row("B", 20, 5), row("A", 20, 9)], level) == ["A", "B"], "two teams level between them: the goal difference of all the games")
check(order([row("B", 20, 5, 900), row("A", 20, 5, 950)], level) == ["A", "B"], "then the points scored")
# art. 184-3: three teams or more: only their games, only the goal difference (A +25, C -5, B -20)
tri = [game("A", "B", 90, 60), game("B", "C", 70, 60), game("C", "A", 80, 75)]
check(order([row("B", 20, 99), row("C", 20, 50), row("A", 20, -99)], tri) == ["A", "C", "B"], "three teams: the goal difference of the games among them")
# it is the difference that counts, not the points those games gave: A won both of its games by 1 (+2), B and C won one big game each (0): A leads
dif = [game("A", "B", 61, 60), game("A", "C", 61, 60), game("B", "C", 100, 50), game("C", "B", 100, 50)]
check(order([row("C", 20, 0), row("B", 20, 0), row("A", 20, 0)], dif)[0] == "A", "three teams: A +2 is ahead of B -1 and C -1")
# art. 184-6: a pair left over after the second table starts again at steps 1 and 2 (A +20, B -10, C -10; B and C: level between them, then the goal difference of all the games)
pair = [game("A", "B", 80, 70), game("A", "C", 80, 70), game("B", "C", 70, 60), game("C", "B", 70, 60)]
check(order([row("A", 20, 0), row("B", 20, 5), row("C", 20, 9)], pair) == ["A", "C", "B"], "a pair left over: their own games (level), then the goal difference of all games")
# art. 184-5: nothing separates a circle of games: the goal difference of all the games
circle = [game("A", "B", 70, 60), game("B", "C", 70, 60), game("C", "A", 70, 60)]
check(order([row("B", 20, 5), row("A", 20, 9), row("C", 20, 7)], circle) == ["A", "C", "B"], "level in their own games: the goal difference of all the games")
# art. 194: the team that lost by penalty has the worst average of the teams level (the games between them are level: A -20 then +20)
pen = [game("A", "B", 0, 20, forfeit="A"), game("B", "A", 50, 70)]
check(order([row("A", 20, 0), row("B", 20, 0)], pen) == ["B", "A"], "a loss by penalty ranks last among the teams that are level")

# art. 182: 2 points for a win, 1 for a loss, 0 for a loss by forfeit; ranks are 1..n
o = {"teams": {"A": "A", "B": "B", "C": "C"}, "results": [game("A", "B", 70, 68), game("B", "C", 100, 50), game("C", "A", 0, 20, forfeit="C")]}
table = stats.official_standings(o)
t = {r["code"]: r for r in table}
check((t["A"]["pts"], t["B"]["pts"], t["C"]["pts"]) == (4, 3, 1), f"points with a forfeit: {[(c, t[c]['pts']) for c in t]}")
check([r["rank"] for r in table] == [1, 2, 3] and [r["code"] for r in table] == ["A", "B", "C"], "ranks 1..n in order")

# WHEN the law applies: only once the phase is over. Four clubs, home and away = 12 games. A and B finish level on points: A beat B by 40 at home and lost by 10 away (+30 between them, so the law puts
# A first), but B beat C and D by far more (B has scored many more points over the season). Until the last game B leads (points, then points scored); with the 12th game played, the law gives A the lead.
import nat1  # noqa: E402
import finals  # noqa: E402

def season(n_games):
    spec = [("A", "B", 100, 60), ("B", "A", 80, 70), ("A", "C", 70, 60), ("C", "A", 60, 70), ("A", "D", 70, 60), ("D", "A", 60, 70),
            ("B", "C", 120, 50), ("C", "B", 50, 120), ("B", "D", 120, 50), ("D", "B", 50, 120), ("C", "D", 70, 60), ("D", "C", 60, 70)]
    return [game(h, a, hs, as_, matchday=i + 1) for i, (h, a, hs, as_) in enumerate(spec[:n_games])]

teams = {"A": "A", "B": "B", "C": "C", "D": "D"}
codes = lambda rows: [r["code"] for r in rows]
mid, end = stats.official_standings({"teams": teams, "results": season(11)}), stats.official_standings({"teams": teams, "results": season(12)})
a, b = (next(r for r in end if r["code"] == c) for c in "AB")
check(a["pts"] == b["pts"] and a["diff"] < b["diff"], "the test season: A and B level on points, B with the better point difference")
check(codes(mid)[:2] == ["B", "A"] and not any(r["final"] for r in mid), f"Pro A, one game still to play: points, then points scored (B), no law: {codes(mid)}")
check(codes(end)[:2] == ["A", "B"] and all(r["final"] for r in end), f"Pro A, every game played: the law (the games between them) puts A first: {codes(end)}")
check(not ranking.complete(4, season(11)) and ranking.complete(4, season(12)) and not ranking.complete(4, []), "the phase is over when all n(n-1) games have a result")
check(codes(ranking.rank([row("A", 20, 10, 900), row("B", 20, 99, 1000)], [game("A", "B", 90, 60)], final=False)) == ["B", "A"], "provisional: the points scored, the game between them does not count")
check(codes(ranking.rank([row("B", 20, 5, 900), row("A", 20, 5, 900)], [], fallback=lambda c: {"A": 2, "B": 1}[c], final=False)) == ["B", "A"], "provisional and level on everything: the fallback decides")

# the movement and the race chart read the same order, round by round
check(finals._table(season(11), teams)["B"] == 1 and finals._table(season(12), teams)["A"] == 1, "the history of ranks follows the same rule (provisional, then the law at the end)")

# National One: the same, without the official FTBB table
n1 = lambda results: nat1.standings({"teams": teams, "results": results, "official": None})
check(codes(n1(season(11)))[:2] == ["B", "A"] and not n1(season(11))[0]["final"], "National One, season on: points, then points scored")
check(codes(n1(season(12)))[:2] == ["A", "B"] and n1(season(12))[0]["final"], "National One, last game played: the law")

# Play-off / play-out mini-championship: four clubs, 12 games (home and away); the same
def league(n_games):
    games = [{"round": i + 1, "home": g["home"], "away": g["away"], "home_score": g["home_score"], "away_score": g["away_score"]} for i, g in enumerate(season(n_games))]
    d = {"carry": "none", "qualify": 2, "relegation": 0, "groups": {"playoff": {"games": games}}}
    return finals._league(d, "playoff", [{"code": c, "name": c, "start_rank": i, "start_pts": 0, "start_diff": 0} for i, c in enumerate("ABCD", 1)])
check(codes(league(11)["table"])[:2] == ["B", "A"] and not league(11)["done"], "play-off table in progress: points, then points scored")
check(codes(league(12)["table"])[:2] == ["A", "B"] and league(12)["done"], "play-off table, every game played: the law")

print("FAILED:\n  " + "\n  ".join(fails) if fails else "tiebreak checks passed")
sys.exit(1 if fails else 0)
