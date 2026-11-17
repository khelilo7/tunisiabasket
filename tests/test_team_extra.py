"""Team lines of a box score (points in the paint, second chance, fast break, off turnovers, bench), the team page averages built from them, a player's home / away split,
and the game link of the form chips."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import stats  # noqa: E402
import team_extra  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None

# 1. reading the lines of a sheet
text = """Points from Turnovers 18 15 Biggest Lead 2 (17-15) 18 (32-50)
Points in the Paint 24 (12/25) 48,0 34 (17/35) 48,6 Biggest Scoring Run 7 (17-15) 8 (0-8)
Second Chance Points 6 14 Points per Possession 0,96 1,08
Fast Break Points 5 4 Lead Changes 2
Fast Break Points from Turnovers 3 4 Times Tied 1
Bench Points 25 4 Time with Lead 00:19 38:58"""
got = team_extra.parse(text, ["SN", "DSG"])
check(got == {"SN": {"paint": 24, "second": 6, "fast": 5, "tov_pts": 18, "bench": 25}, "DSG": {"paint": 34, "second": 14, "fast": 4, "tov_pts": 15, "bench": 4}}, f"the five lines are read for both teams: {got}")
check(team_extra.parse("Points in the Paint 40 38\nBench Points 10 12") == {"first": {"paint": 40, "bench": 10}, "second": {"paint": 38, "bench": 12}}, "a sheet with only some of the lines gives only those")
check(team_extra.parse("nothing here") == {}, "a sheet without them gives nothing")
check(team_extra.clean({"paint": 12, "second": -1, "fast": "x", "bench": True, "other": 3}) == {"paint": 12}, "only whole numbers 0-250 of the five known keys are kept")

# 2. a game with the lines: stored, shown, averaged, ranked
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
games = sorted(Path(os.environ["DATA_DIR"], "games").glob("*.json"))
g = json.loads(games[0].read_text())
for i, t in enumerate(g["teams"]):
    t["extra"] = {"paint": 40 + i, "second": 8, "fast": 6 - i, "tov_pts": 12, "bench": 20}
check(c.post("/admin/api/game", json={"game": g}, headers=H).status_code == 200, "a game with team lines is saved")
api = c.get("/api/games/" + g["id"]).get_json()
check(all(t.get("extra", {}).get("paint") in (40, 41) for t in api["teams"]), "the game page gets the lines")
a, b = (t["code"] for t in g["teams"])
sp = c.get(f"/api/teams/{a}").get_json()["splits"]["all"]
check(sp["paint"] == 40 and sp["opp_paint"] == 41 and sp["extra_games"] == 1, f"team average of the lines, and what the opponent scored: {sp['paint']} {sp['opp_paint']} {sp['extra_games']}")
check(sp["rank"].get("paint") in range(1, 13) and sp["rank"].get("opp_paint") in range(1, 13), "the new lines are ranked among the teams")
other = next(t for t in c.get("/api/overview").get_json()["standings"] if t["code"] not in (a, b))["code"]
check(c.get(f"/api/teams/{other}").get_json()["splits"]["all"]["paint"] is None, "a team with no sheet carrying the lines has none (never 0)")

# 3. a player at home and away
d = stats.build()
pl = max(d["players"], key=lambda p: p["gp"])
sp = c.get(f"/api/players/{pl['id']}").get_json()["player"]["splits"]
check(sp["all"]["gp"] == pl["gp"], "overall = the whole log")
check(sp["home"]["gp"] + sp["away"]["gp"] <= sp["all"]["gp"] and sp["home"]["gp"] + sp["away"]["gp"] > 0, f"home + away games add up: {sp['home']['gp']} + {sp['away']['gp']} <= {sp['all']['gp']}")
home = [r for r in pl["log"] if r.get("home") is True]
check(not home or abs(sp["home"]["pts"] - sum(r["pts"] for r in home) / len(home)) < 0.06, "home points per game = the average of his home games")
check(all(r.get("home") in (True, False, None) for r in pl["log"]), "each log row says home, away or unknown")

# 4. the form chips know the game to open
m = c.get(f"/api/matchup?home={a}&away={b}").get_json()
check(all("game_id" in x for x in m["form"][a]) and any(x["game_id"] for x in m["form"][a]), "a form chip carries the game id when the site has its box score")
print("team lines and splits:", "FAILED" if fails else "ok")
for m_ in fails:
    print(" -", m_)
sys.exit(1 if fails else 0)
