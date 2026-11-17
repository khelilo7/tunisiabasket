"""The Cup (single-game knockout of Pro A and Nationale 1 clubs) and the play-off / play-out (league or series), with the rank history of the season."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import cup  # noqa: E402
import finals  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
apost = lambda path, body: c.post("/admin/api/" + path, json=body, headers=H)

# ------------------------------------------------------------------ the Cup
check(c.get("/api/cup").get_json()["rounds"] == [] and c.get("/coupe").status_code == 200 and c.get("/en/cup").status_code == 200, "an empty cup answers (draw soon)")
check(c.post("/admin/api/cup", json={"op": "reset"}).status_code in (401, 403), "only the admin edits the cup")
pro = list(stats.load_official()["teams"])[:4]
check(apost("nat1", {"op": "team", "code": "EZS", "name": "Ezzahra Sport"}).status_code == 200 and apost("nat1", {"op": "team", "code": "CAB", "name": "CA Bizertin"}).status_code == 200, "two National One clubs")
a, b, d_, e = pro
r = apost("cup", {"op": "draw", "text": f"{a}, EZS, 2026-12-19\n{b}, CAB\n{d_}, BYE\n{e}, XXX"})
check(r.status_code == 422 and "XXX" in r.get_json()["error"], "an unknown club is refused, nothing saved")
check(apost("cup", {"op": "draw", "text": f"{a}, EZS\n{b}, CAB\n{d_}, BYE"}).status_code == 422, "three ties are not a bracket")
check(apost("cup", {"op": "draw", "text": f"{a}, EZS\n{b}, {a}"}).status_code == 422, "a club cannot be drawn twice")
extra = next(code for code in stats.load_official()["teams"] if code not in (a, b, d_, e))
r = apost("cup", {"op": "draw", "text": f"{a}, EZS, 2026-12-19\n{b}, CAB, 2026-12-19\n{d_}, BYE\n{e}, {extra}"})
tid = lambda v, r_, n: v["rounds"][r_]["ties"][n]["id"]
v = r.get_json()
check(r.status_code == 200 and [x["name"] for x in v["rounds"]] == ["Quarts de finale", "Demi-finales", "Finale"], f"4 ties build quarter-finals, semi-finals and a final: {[x['name'] for x in v['rounds']]}")
check(v["rounds"][0]["ties"][2]["bye"] and v["rounds"][0]["ties"][2]["winner"] == d_, "a BYE passes the club on at once")
check(v["rounds"][1]["ties"][0]["home"].get("label") and not v["rounds"][1]["ties"][0]["home"].get("code"), "a later tie waits for its winners")
t1, t2, t4 = tid(v, 0, 0), tid(v, 0, 1), tid(v, 0, 3)
check(apost("cup", {"op": "result", "tie": t1, "home_score": 70, "away_score": 70}).status_code == 422, "equal scores are refused")
check(apost("cup", {"op": "result", "tie": tid(v, 1, 0), "home_score": 70, "away_score": 60}).status_code == 422, "a tie whose clubs are not known cannot take a result")
v = apost("cup", {"op": "result", "tie": t1, "home_score": 70, "away_score": 80}).get_json()           # a Pro A club loses to a Nationale 1 club
check(v["rounds"][0]["ties"][0]["winner"] == "EZS" and v["rounds"][0]["ties"][0]["upset"] and v["upsets"] == 1, "the lower-league winner is an upset")
v = apost("cup", {"op": "result", "tie": t2, "home_score": 90, "away_score": 60}).get_json()
check(v["rounds"][1]["ties"][0]["home"].get("code") == "EZS" and v["rounds"][1]["ties"][0]["away"].get("code") == b, "the winners appear in the next round")
check(apost("cup", {"op": "result", "tie": t1, "home_score": "", "away_score": ""}).get_json()["rounds"][0]["ties"][0]["winner"] is None, "an empty result clears it")
check(v["champion"] is None and v["clubs"]["nat1"] == 2 and v["clubs"]["proa"] == 5, f"clubs by league: {v['clubs']}")
check(apost("cup", {"op": "team", "code": "ZZ", "name": "A club of the Nationale 2"}).status_code == 200 and cup.known_teams()["ZZ"]["league"] == "other", "a club of neither league can be added")
check(c.get("/api/competitions").get_json()["cup"] is True, "the page's switch knows the cup exists")
check(apost("cup", {"op": "reset"}).get_json()["rounds"] == [], "the bracket can be emptied")

# ------------------------------------------------------------------ the regular season's history
h = c.get("/api/rank-history").get_json()
check(len(h["matchdays"]) >= 11 and all(len(t["ranks"]) == len(h["matchdays"]) for t in h["teams"].values()), "a rank after every matchday for every club")
check(sorted(t["ranks"][-1] for t in h["teams"].values()) == list(range(1, len(h["teams"]) + 1)), "the last ranks are 1..N")

# ------------------------------------------------------------------ play-off / play-out
check(c.get("/api/finals").get_json()["active"] is False and c.get("/playoff-playout").status_code == 200, "nothing set up: inactive, the page still answers")
rows = stats.official_standings(stats.load_official())
top, low = [r["code"] for r in rows[:6]], [r["code"] for r in rows[6:]]
check(apost("finals", {"op": "auto_teams"}).status_code == 200, "the groups follow the table")
f = c.get("/api/finals").get_json()
check([t["code"] for t in f["groups"]["playoff"]["teams"]] == top and [t["code"] for t in f["groups"]["playout"]["teams"]] == low and f["active"], "six best / six last")
comp = c.get("/api/competitions").get_json()
check(comp["finals"] is False and comp["started"] is False and c.get("/api/finals").get_json()["played_any"] is False, "set up but NOT announced: the public site does not change (no tab, the championship standings stay)")
check(apost("finals", {"op": "config", "carry": "half", "formats": {"playoff": "series", "playout": "league"}}).status_code == 200, "formats and carry-over")
x, y = low[0], low[1]
check(apost("finals", {"op": "league_games", "group": "playout", "text": f"1, {x}, {y}, 80, 70, 2027-04-24\n1, {low[2]}, {low[3]}"}).status_code == 200, "league games, one without score")
check(apost("finals", {"op": "league_games", "group": "playout", "text": f"1, {x}, {top[0]}, 80, 70"}).status_code == 422, "a club of the other group is refused")
g = c.get("/api/finals").get_json()["groups"]["playout"]
tx = next(t for t in g["table"] if t["code"] == x)
start = next(r for r in rows if r["code"] == x)
check(tx["pts"] == round(start["pts"] * 0.5) + 2 and tx["j"] == 1 and tx["w"] == 1 and tx["carry"] == round(start["pts"] * 0.5), f"table = half the regular-season points + 2 for the win: {tx}")
check(sum(1 for r in g["rounds"][0]["games"] if r["played"]) == 1, "the game without a score is listed as to come")
s1, s2, s3, s4 = top[:4]
r = apost("finals", {"op": "series", "group": "playoff", "text": f"SERIES, qf, Quarter-finals, {s3}, {s4}, 3\nSERIES, sf, Semi-finals, {s1}, W:qf, 5\nGAME, qf, {s3}, 80, 70\nGAME, qf, {s4}, 75, 70\nGAME, qf, {s3}, 90, 85"})
check(r.status_code == 200, f"series saved: {r.get_json()}")
po = c.get("/api/finals").get_json()["groups"]["playoff"]
qf, sf = po["rounds"][0]["series"][0], po["rounds"][1]["series"][0]
check(qf["a"]["wins"] == 2 and qf["b"]["wins"] == 1 and qf["winner"] == s3 and qf["done"], f"best of 3: {s3} wins 2-1: {qf['a']['wins']}-{qf['b']['wins']}")
check(sf["b"].get("code") == s3 and sf["a"].get("code") == s1 and not sf["done"], "the winner of a series takes his place in the next one")
apost("finals", {"op": "series", "group": "playoff", "text": f"GAME, qf, {s3}, 80, 70"})
check(len(c.get("/api/finals").get_json()["groups"]["playoff"]["rounds"][0]["series"][0]["games"]) == 1, "the games written for a series replace its games")
check(apost("finals", {"op": "series", "group": "playoff", "text": "GAME, nope, CA, 80, 70"}).status_code == 422, "a game of an unknown series is refused")
check(apost("finals", {"op": "clear", "group": "playout"}).status_code == 200, "a group can be emptied")
# the announced format: the play-off is a league, its first four go to the super play-off (1v4, 2v3, final), the last two of the play-out go down
check(apost("finals", {"op": "clear", "group": "playoff"}).status_code == 200 and apost("finals", {"op": "config", "carry": "full", "formats": {"playoff": "league", "playout": "league"}}).status_code == 200, "back to the default formats")
apost("finals", {"op": "auto_teams"})
check(apost("finals", {"op": "teams", "group": "super", "text": "CA"}).status_code == 422, "the super play-off takes its clubs from the play-off")
f = c.get("/api/finals").get_json()
check(f["qualify"] == 4 and f["relegation"] == 2 and sorted(f["groups"]) == ["playoff", "playout", "super"], "three groups, 4 qualify, 2 go down")
check(apost("finals", {"op": "super_scaffold"}).status_code == 200, "the super play-off can be set up in one click")
F = c.get("/api/finals").get_json()["groups"]
sp, seed = F["super"], [t["code"] for t in F["playoff"]["table"]]
check(all(x["a"].get("provisional") for x in sp["rounds"][0]["series"]), "seeds are provisional until the play-off is over")
check([r["name"] for r in sp["rounds"]] == ["Semi-finals", "Championship final"] and sp["rounds"][0]["series"][0]["a"].get("code") == seed[0] and sp["rounds"][0]["series"][0]["b"].get("code") == seed[3], f"1 v 4 and 2 v 3 then the final: {[r['name'] for r in sp['rounds']]}")
check(sp["rounds"][0]["series"][1]["a"].get("code") == seed[1] and sp["rounds"][0]["series"][1]["b"].get("code") == seed[2], "2 v 3")
check(all(s["best_of"] == 5 and s["need"] == 3 for r in sp["rounds"] for s in r["series"]), "every series of the super play-off is a best of five, first to three")
check(apost("finals", {"op": "league_games", "group": "playoff", "text": f"1, {top[0]}, {top[1]}, 80, 70"}).status_code == 200, "a play-off game")
po = c.get("/api/finals").get_json()["groups"]["playoff"]
check([t["zone"] for t in po["table"][:4]] == ["up"] * 4 and not po["done"], "the first four of the play-off are in the super zone (not final until the league is played)")
check(apost("finals", {"op": "config", "qualify": 2, "relegation": 3}).status_code == 200, "the numbers can change")
f = c.get("/api/finals").get_json()
check(f["qualify"] == 2 and len(f["groups"]["super"]["teams"]) == 2 and [t.get("zone") for t in f["groups"]["playout"]["table"]].count("down") == 3, "qualify and relegation follow the settings")
apost("finals", {"op": "config", "qualify": 4, "relegation": 2})
n1 = c.get("/api/nat1").get_json()
check(n1["format"]["playoff"] == 8 and n1["format"]["promoted"] == 2 and n1["format"]["confirmed"] is False and n1["format"]["source"].startswith("https://www.ftbb.org.tn"), "Nationale 1: the promotion formula and its source")
j = c.get("/api/finals").get_json()["journey"]
check([s["key"] for s in j] == ["phase1", "phase2", "finals", "cup"] and j[0]["state"] in ("done", "current"), "the season journey: phase 1, return leg, finals, cup")
comp = c.get("/api/competitions").get_json()
check(comp["started"] is False and c.get("/api/finals").get_json()["played_any"] is True, "games typed but not announced: still nothing public")
check(c.post("/admin/api/finals", json={"op": "announce", "on": True}).status_code in (401, 403), "only the admin announces")
check(apost("finals", {"op": "announce", "on": True}).status_code == 200 and c.get("/api/competitions").get_json()["started"] is True and c.get("/api/competitions").get_json()["finals"] is True, "announced: the site shows the play-off instead of the championship")
check(apost("finals", {"op": "announce", "on": False}).status_code == 200 and c.get("/api/competitions").get_json()["finals"] is False, "the announcement can be withdrawn")
for u in ("/coupe", "/en/cup", "/playoff-playout", "/en/playoff-playout"):
    check(c.get(u).status_code == 200, f"{u} answers")
check("/coupe" in c.get("/sitemap.xml").get_data(as_text=True), "the cup is in the sitemap")
# rises and falls after a round: only the day after its last game
import datetime
mv = finals.movement(force=True)
check(mv and mv["matchday"] >= 2 and sum(mv["moves"].values()) == 0 and len(mv["moves"]) == len(stats.load_official()["teams"]), f"a rise for every fall, for every club: {mv and mv['matchday']}")
day = datetime.date.fromisoformat(mv["date"])
check(finals.movement(today=day) and finals.movement(today=day + datetime.timedelta(days=1)), "visible on the day of the last game and the day after")
check(finals.movement(today=day + datetime.timedelta(days=2)) is None, "gone two days after the last game")
check(c.get("/api/overview?move=1").get_json()["movement"]["matchday"] == mv["matchday"], "?move=1 shows it whatever the date")
print("cup, finals, history:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
