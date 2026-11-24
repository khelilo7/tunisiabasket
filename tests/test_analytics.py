"""Analytics: an analyst counts a game by hand (/analytics); nothing is public until the admin approves it; the analyst's token never opens /admin."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
os.environ["ANALYTICS_TOKEN"] = "TEST-ANALYST-2222-3333"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analytics  # noqa: E402
import app  # noqa: E402
import auth  # noqa: E402
import config  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
analytics.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
ip = lambda a: {"REMOTE_ADDR": a}
visitor, analyst, admin = app.app.test_client(), app.app.test_client(), app.app.test_client()

# 1. who can do what
check(visitor.get("/analytics").status_code == 200 and 'content="noindex' in visitor.get("/analytics").get_data(as_text=True), "the page shell loads and is noindex")
for method, path in [("get", "/analytics/api/data"), ("post", "/analytics/api/games"), ("get", "/analytics/api/games/j12-ca-esg"), ("get", "/admin/api/analytics"),
                     ("post", "/admin/api/analytics/j12-ca-esg/approve")]:
    check(getattr(visitor, method)(path, environ_overrides=ip("198.51.100.1")).status_code == 401, f"anonymous {method.upper()} {path} must be 401")
check(visitor.get("/analytics/api/me").get_json()["analyst"] is False, "anonymous is not an analyst")
codes = [visitor.post("/analytics/api/login", json={"token": "bad%d" % i, "name": "Guesser"}, environ_overrides=ip("198.51.100.2")).status_code for i in range(6)]
check(codes == [401] * 5 + [429], f"lockout after 5 wrong tokens: {codes}")
check(visitor.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333", "name": "Locked Out"}, environ_overrides=ip("198.51.100.2")).status_code == 429, "locked out even with the right token")
check(analyst.post("/analytics/api/login", json={"token": "TEST-TOKEN-0000-1111", "name": "Tester One"}, environ_overrides=ip("198.51.100.3")).status_code == 401, "the ADMIN token is not an analytics token")
r = analyst.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333", "name": "Tester One"}, environ_overrides=ip("198.51.100.3"))
check(r.status_code == 200 and "HttpOnly" in r.headers["Set-Cookie"] and "SameSite=Strict" in r.headers["Set-Cookie"], "analyst login, HttpOnly + SameSite=Strict cookie")
check(analyst.get("/analytics/api/me").get_json()["analyst"] is True, "signed in")
for method, path in [("get", "/admin/api/official"), ("get", "/admin/api/analytics"), ("post", "/admin/api/analytics/j12-ca-esg/approve"), ("get", "/admin/api/roster")]:
    check(getattr(analyst, method)(path, environ_overrides=ip("198.51.100.3")).status_code == 401, f"an analyst must not reach {path}")
check(analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG"}, headers={"Origin": "http://evil.example"}, environ_overrides=ip("198.51.100.3")).status_code == 403, "cross-site POST refused")
ah = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
check(app.app.test_client().get("/analytics/api/data", headers=ah, environ_overrides=ip("198.51.100.4")).status_code == 200, "the admin may use /analytics too")
check("Disallow: /analytics" in visitor.get("/robots.txt").get_data(as_text=True), "robots.txt keeps /analytics out of search engines")
check(analyst.get("/analytics/api/data").headers.get("X-Robots-Tag", "").startswith("noindex"), "API answers are noindex")

# 2. the data the page needs: the site's own players, and the matches
d = analyst.get("/analytics/api/data").get_json()
check({"CA", "ESG"} <= set(d["roster"]) and d["roster"]["CA"][0]["id"].startswith("ca-") and d["matches"] and "CA" in d["teams"], "teams, players and matches come from the site")
ca, esg = d["roster"]["CA"], d["roster"]["ESG"]
# the video list is gone; any game of any round (first phase included) can be opened
built = stats.build()
full = {(stats.matchday_hint(g), frozenset(t["code"] for t in g["teams"])) for g in built["games"]}
check("video" not in d, "the list of games to count from the video is gone")
mds = {m["matchday"] for m in d["matches"]}
check(1 in mds and any(m["played"] for m in d["matches"] if m["matchday"] == 1), "the matches cover every round, the first phase too")

# 3. counting
g = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 12, "date": "2026-11-11"}).get_json()
gid = g["id"]
check(gid == "j12-ca-esg--tester-one" and g["analyst"] == "Tester One" and g["status"] == "open" and [p["id"] for p in g["players"]["CA"]] == [p["id"] for p in ca], "game created with the site's players")
check(analyst.post("/analytics/api/games", json={"home": "CA", "away": "CA"}).status_code == 422 and analyst.post("/analytics/api/games", json={"home": "CA", "away": "ZZZ"}).status_code == 422, "bad teams refused")
ev = lambda pid, stat: analyst.post(f"/analytics/api/games/{gid}/event", json={"pid": pid, "stat": stat})
a, b, c_ = ca[0]["id"], ca[1]["id"], esg[0]["id"]
for pid, stat in [(a, "p3_m"), (a, "p2_m"), (a, "ft_m"), (a, "p2_x"), (a, "oreb"), (a, "ast"), (b, "p2_m"), (b, "dreb"), (b, "tov"), (b, "pf"), (c_, "p3_m"), (c_, "p3_x"), (c_, "stl"), (c_, "blk")]:
    check(ev(pid, stat).status_code == 200, f"event {pid} {stat}")
r = analyst.post(f"/analytics/api/games/{gid}/event", json={"pid": a, "stat": "stl", "q": 2, "t": 392}).get_json()["events"][-1]
check(r["q"] == 2 and r["t"] == 392, "an action may carry the game clock (quarter, seconds left)")
r = analyst.post(f"/analytics/api/games/{gid}/event", json={"pid": a, "stat": "stl", "q": 99, "t": -5}).get_json()["events"][-1]
check("q" not in r and "t" not in r, "a bad clock stamp is ignored, the action is still counted")
for _ in range(2):
    analyst.post(f"/analytics/api/games/{gid}/undo", json={})
check(ev("nobody-1", "ast").status_code == 422 and ev(a, "dunk").status_code == 422, "unknown player or action refused")
g = analyst.get(f"/analytics/api/games/{gid}").get_json()
s = analytics.scores(g)
check(s == {"CA": 8, "ESG": 3}, f"score from the events: {s}")
check(analytics.line(analytics.tally(g)[a]) == {"pts": 6, "fgm": 2, "fga": 3, "p3m": 1, "p3a": 1, "ftm": 1, "fta": 1, "oreb": 1, "dreb": 0, "ast": 1, "stl": 0, "blk": 0, "tov": 0, "pf": 0, "fd": 0}, "one player's line")
n = g["events"][-1]["n"]
analyst.post(f"/analytics/api/games/{gid}/undo", json={})
check(len(analyst.get(f"/analytics/api/games/{gid}").get_json()["events"]) == 13, "undo removes the last action")
analyst.post(f"/analytics/api/games/{gid}/remove", json={"n": g["events"][0]["n"]})
check(analytics.scores(analyst.get(f"/analytics/api/games/{gid}").get_json())["CA"] == 5, "removing one action (the 3-pointer) takes its points off")
ev(a, "p3_m")
csv = analyst.get(f"/analytics/api/games/{gid}/export.csv")
check(csv.status_code == 200 and "text/csv" in csv.content_type and csv.get_data(as_text=True).startswith("team,number,player,PTS"), "CSV export")
check(analyst.post(f"/analytics/api/games/{gid}/submit", json={"matchday": 99, "date": "2026-11-11"}).status_code == 422 and analyst.post(f"/analytics/api/games/{gid}/submit", json={"matchday": 12, "date": "tomorrow"}).status_code == 422, "submit needs a real matchday and date")

# 4. nothing is public before the approval
def public_partials():
    return [x["id"] for x in stats.build()["partials"] if x["id"].startswith("live-")]
games_before, standings_before = len(stats.build()["games"]), json.dumps(stats.official_standings(), sort_keys=True)
check(analyst.post(f"/analytics/api/games/{gid}/submit", json={"matchday": 12, "date": "2026-11-11"}).status_code == 200, "submitted")
check(public_partials() == [] and not (config.DATA_DIR / "partial_games.json").exists(), "a submitted game is not public")
check(ev(a, "ast").status_code == 409, "a submitted game cannot be changed")
check(analyst.post(f"/analytics/api/games/{gid}/reopen", json={}).get_json()["status"] == "open" and ev(a, "ast").status_code == 200, "the analyst can take it back and carry on")
analyst.post(f"/analytics/api/games/{gid}/undo", json={})
analyst.post(f"/analytics/api/games/{gid}/submit", json={"matchday": 12, "date": "2026-11-11"})

# 5. the admin reviews: a rejection sends it back, an approval publishes it
admin.post("/admin/api/login", json={"token": "TEST-TOKEN-0000-1111"}, environ_overrides=ip("198.51.100.5"))
lst = admin.get("/admin/api/analytics", environ_overrides=ip("198.51.100.5")).get_json()["games"]
check(len(lst) == 1 and lst[0]["id"] == gid and lst[0]["official"] is None and lst[0]["same_score"] is False and lst[0]["box"]["CA"][0]["pts"] == 6, "the admin sees the box score and that there is no official result yet")
check(admin.post(f"/admin/api/analytics/{gid}/reject", json={"note": "Check the 3-pointers"}, environ_overrides=ip("198.51.100.5")).status_code == 200, "rejected")
g = analyst.get(f"/analytics/api/games/{gid}").get_json()
check(g["status"] == "rejected" and g["note"] == "Check the 3-pointers" and ev(a, "ast").status_code == 200, "sent back with the reason, and editable again")
analyst.post(f"/analytics/api/games/{gid}/undo", json={})
analyst.post(f"/analytics/api/games/{gid}/submit", json={"matchday": 12, "date": "2026-11-11"})
check(admin.post(f"/admin/api/analytics/{gid}/approve", json={}, environ_overrides=ip("198.51.100.5")).status_code == 200, "approved")
doc = json.loads((config.DATA_DIR / "partial_games.json").read_text())
ids = sorted(x["id"] for x in doc["games"])
check(ids == ["live-j12-ca-esg--tester-one-ca", "live-j12-ca-esg--tester-one-esg"], f"two one-team sheets published: {ids}")
sheet = next(x for x in doc["games"] if x["recorded"] == "CA")
check(sheet["matchday"] == 12 and sheet["date"] == "2026-11-11" and sheet["players"][0]["pts"] == 6 and sheet["players"][0]["oreb"] == 1, "the sheet carries the counted stats")

# 6. it shows only when the official result exists, and never counts as a box score
check(public_partials() == [], "approved, but ignored while the official result of J12 does not exist")
o = stats.load_official()
o["results"].append({"matchday": 12, "home": "CA", "away": "ESG", "home_score": 8, "away_score": 3})
(config.DATA_DIR / "official.json").write_text(json.dumps(o))
check(public_partials() == ["live-j12-ca-esg--tester-one"], f"with the official result, the two sheets of the game show as ONE game: {public_partials()}")
mg = next(x for x in stats.build()["partials"] if x["id"] == "live-j12-ca-esg--tester-one")
check(mg["recorded_all"] == ["CA", "ESG"] and all(t["players"] for t in mg["teams"]) and all(t["recorded"] for t in mg["teams"]), "both teams' players are on the game (not only one team)")
check(stats.partial_game("live-j12-ca-esg--tester-one-esg") is not None and stats.partial_game("live-j12-ca-esg--tester-one-ca")["id"] == mg["id"], "the old address of a sheet still opens the game")
api_ = app.app.test_client().get(f"/api/games/{mg['id']}").get_json()
check(all(t["players"] for t in api_["teams"]) and api_["recorded_all"] == ["CA", "ESG"], "the game page API carries both teams")
check(stats.box_counts([], [mg]).get("CA", 0) + stats.box_counts([], [mg]).get("ESG", 0) == sum(1 for t in mg["teams"] if t["complete"]), "box scores are counted per complete team")
b2 = stats.build()
ca_row = next(p for p in b2["players"] if p["id"] == a)
last = ca_row["log"][-1]
check(last.get("min") is None and last.get("pm") is None and last["pts"] == 6 and last["tov"] == 0 and last["fd"] == 0, "minutes and +/- stay unknown (never 0); points, turnovers, fouls and fouls drawn are the counted ones")
check(len(b2["games"]) == games_before, "it never becomes a box score")
check(json.dumps(stats.official_standings(), sort_keys=True) != standings_before, "standings changed only because the admin entered the official result")
lst = admin.get("/admin/api/analytics", environ_overrides=ip("198.51.100.5")).get_json()["games"]
check(lst[0]["official"]["home_score"] == 8 and lst[0]["same_score"] is True and lst[0]["status"] == "published", "the review shows that the score matches the official one")
check(analyst.delete(f"/analytics/api/games/{gid}").status_code == 409, "a published game cannot be deleted by an analyst")
check(admin.post(f"/admin/api/analytics/{gid}/unpublish", json={}, environ_overrides=ip("198.51.100.5")).status_code == 200 and public_partials() == []
      and json.loads((config.DATA_DIR / "partial_games.json").read_text())["games"] == [], "unpublished: gone from the site")
check(analyst.delete(f"/analytics/api/games/{gid}").status_code == 200 and analyst.get(f"/analytics/api/games/{gid}").status_code == 404, "an unpublished game can be deleted")

# 8. who is on the court: the five of each team, how long they play (game clock) and their plus/minus
lg = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 13, "date": "2026-11-14"}).get_json()
lid = lg["id"]
base_url = f"/analytics/api/games/{lid}"
lu = lambda team, on, q=None, t=None: analyst.post(f"{base_url}/lineup", json={"team": team, "on": on, **({"q": q, "t": t} if q else {})})
ev2 = lambda pid, stat, q, t: analyst.post(f"{base_url}/event", json={"pid": pid, "stat": stat, "q": q, "t": t})
five, bench, opp = [p["id"] for p in ca[:5]], ca[5]["id"], [p["id"] for p in esg[:5]]
check(lu("CA", [p["id"] for p in ca[:6]]).status_code == 422, "six players on the court are refused")
check(lu("CA", five[:2] + five[:1]).status_code == 422 and lu("CA", [opp[0]]).status_code == 422 and lu("ZZZ", five).status_code == 422 and lu("CA", "x").status_code == 422, "duplicates, a player of the other team, an unknown team, a bad list are refused")
check(visitor.post(f"/analytics/api/games/{lid}/lineup", json={"team": "CA", "on": five}).status_code in (401, 429), "the court is for the analyst only")
check(lu("CA", five, 1, 600).status_code == 200 and lu("ESG", opp, 1, 600).status_code == 200, "the two fives are set at the start of the game")
ev2(five[0], "p2_m", 1, 500)                                  # CA +2 while the first five is on
lu("CA", five[:4] + [bench], 1, 300)                           # five[4] comes off after 5:00
ev2(bench, "p3_m", 1, 200)                                    # CA +3
ev2(opp[0], "p2_m", 1, 100)                                   # ESG +2
pre = analyst.get(base_url).get_json()
check(pre["court"]["on"]["CA"] == five[:4] + [bench] and pre["court"]["on"]["ESG"] == opp and pre["court"]["used"], "the court knows who is on")
check(analytics.scores(pre) == {"CA": 5, "ESG": 2}, "a change of five is not a statistic: the score is only the shots")
lu("CA", five, 1, 50)
check(analyst.post(f"{base_url}/undo", json={}).get_json()["court"]["on"]["CA"] == five[:4] + [bench], "undo of a change of five gives the previous five back")
r = analyst.post(f"{base_url}/submit", json={"matchday": 13, "date": "2026-11-14", "q": 1, "t": 0}).get_json()
mins, pm = analytics.minutes(r), r["court"]["pm"]
check(all(mins[i] == 600 for i in five[:4]) and mins[five[4]] == 300 and mins[bench] == 300 and all(mins[i] == 600 for i in opp), f"minutes follow the game clock up to where it stood when sent: {mins}")
check(pm[five[0]] == 3 and pm[five[4]] == 2 and pm[bench] == 1 and pm[opp[0]] == -3 and pm[opp[1]] == -3, f"plus/minus: points of both teams while on the court: {pm}")
csv_ = analyst.get(f"{base_url}/export.csv").get_data(as_text=True)
check(csv_.splitlines()[0].split(",")[3:5] == ["MIN", "+/-"] and "10:00" in csv_ and "5:00" in csv_, "the CSV has minutes and +/-")
sheet = next(x for x in analytics._sheets(r) if x["recorded"] == "CA")
row = next(x for x in sheet["players"] if x["name"] == ca[0]["name"])
check(row["min"] == 10.0 and row["pm"] == 3 and "come from the five" in sheet["note"], "the one-team sheet carries minutes and +/-")
check(analyst.delete(base_url).status_code == 200, "game deleted")

# 9. live: public only when the ADMIN switches a game on, only while it is being counted, and only what is meant to be public
lv = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 15, "date": "2099-01-15"}).get_json()["id"]
pub = app.app.test_client()
analyst.post(f"/analytics/api/games/{lv}/event", json={"pid": ca[0]["id"], "stat": "p3_m", "q": 1, "t": 540})
check(pub.get("/api/live").get_json()["games"] == [], "a game being counted is not public by default")
check(analyst.post(f"/admin/api/analytics/{lv}/live", json={"on": True}).status_code in (401, 403) and pub.post(f"/admin/api/analytics/{lv}/live", json={"on": True}).status_code in (401, 403), "only the admin can make a game live")
check(admin.post(f"/admin/api/analytics/{lv}/live", json={"on": True}, environ_overrides=ip("198.51.100.5")).status_code == 200, "the admin makes it live")
lg_ = pub.get("/api/live").get_json()["games"]
check(len(lg_) == 1 and lg_[0]["id"] == lv and lg_[0]["teams"]["CA"]["score"] == 3 and lg_[0]["clock"] == {"q": 1, "t": 540}, f"the public sees the score and the clock: {lg_ and lg_[0]['teams']['CA']['score']}")
check(lg_[0]["plays"][0]["text"] == "3-pointer made" and lg_[0]["plays"][0]["pts"] == 3 and any(p["id"] == ca[0]["id"] and p["pts"] == 3 for p in lg_[0]["teams"]["CA"]["players"]), "box score and last plays are there")
check(not ({"events", "players", "created", "note"} & set(lg_[0])) and pub.get("/api/live").headers["Cache-Control"] == "no-store", "nothing else of the analyst's file is public, and it is never cached")
check(any(x["id"] == lv and x["live"] for x in admin.get("/admin/api/analytics", environ_overrides=ip("198.51.100.5")).get_json()["counting"]), "the admin sees it as live")
analyst.post(f"/analytics/api/games/{lv}/submit", json={"matchday": 15, "date": "2099-01-15"})
check(pub.get("/api/live").get_json()["games"] == [], "sent for approval: no longer live")
check(admin.post(f"/admin/api/analytics/{lv}/live", json={"on": True}, environ_overrides=ip("198.51.100.5")).status_code == 409, "a game that is not being counted cannot be live")
analyst.delete(f"/analytics/api/games/{lv}")

# 10. names, one version per analyst, editing any action, the change log
anon = app.app.test_client()
for bad in ({"token": "TEST-ANALYST-2222-3333"}, {"token": "TEST-ANALYST-2222-3333", "name": "x"}, {"token": "TEST-ANALYST-2222-3333", "name": "<b>Eve</b>"}, {"token": "TEST-ANALYST-2222-3333", "name": "  "}):
    check(anon.post("/analytics/api/login", json=bad, environ_overrides=ip("198.51.100.60")).status_code == 422, f"a name is compulsory: {bad.get('name')!r}")
check(analytics.name_slug("Tester One") == analytics.name_slug("tester  one") == "tester-one" and analytics.name_slug("أحمد") != analytics.name_slug("محمد"), "one key per name, an Arabic name still gets its own")
two = app.app.test_client()
check(two.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333", "name": "Tester Two"}, environ_overrides=ip("198.51.100.61")).status_code == 200, "a second analyst signs in with the same token and another name")
check(analyst.get("/analytics/api/me").get_json()["name"] == "Tester One" and two.get("/analytics/api/me").get_json()["name"] == "Tester Two", "the page knows who is who")
mk = lambda cl: cl.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 16, "date": "2099-01-16"}).get_json()
ga, gb = mk(analyst), mk(two)
check(ga["id"] == "j16-ca-esg--tester-one" and gb["id"] == "j16-ca-esg--tester-two" and ga["id"] != gb["id"], f"two names, two versions of the same game: {ga['id']} {gb['id']}")
check(mk(analyst)["id"] == ga["id"] and len(ga["events"]) == 0, "the same name opening the game again continues its own version")
check([g["id"] for g in two.get("/analytics/api/data").get_json()["games"] if g["base"] == "j16-ca-esg"] == [gb["id"]], "an analyst sees only his own versions")
check(two.get(f"/analytics/api/games/{ga['id']}").status_code == 404 and two.post(f"/analytics/api/games/{ga['id']}/event", json={"pid": ca[0]["id"], "stat": "p2_m"}).status_code == 404 and two.delete(f"/analytics/api/games/{ga['id']}").status_code == 404, "another analyst's version does not exist for him")
adm = app.app.test_client()
adm.post("/admin/api/login", json={"token": "TEST-TOKEN-0000-1111"}, environ_overrides=ip("198.51.100.62"))
seen = {g["id"]: g["analyst"] for g in adm.get("/analytics/api/data", environ_overrides=ip("198.51.100.62")).get_json()["games"] if g["base"] == "j16-ca-esg"}
check(seen == {ga["id"]: "Tester One", gb["id"]: "Tester Two"}, f"the admin sees every version with its analyst: {seen}")

A = f"/analytics/api/games/{ga['id']}"
evA = lambda pid, stat, q=None, t=None: analyst.post(f"{A}/event", json={"pid": pid, "stat": stat, **({"q": q, "t": t} if q else {})})
five = [p["id"] for p in ca[:5]]
bench = ca[5]["id"]
for pid, stat in [(five[0], "p3_m"), (five[1], "p2_m"), (five[2], "ast")]:
    evA(pid, stat)
g1 = analyst.get(A).get_json()
check(all(e["by"] == "Tester One" for e in g1["events"]) and [x["op"] for x in g1["log"]][:2] == ["start", "add"], "every action is stamped with its analyst and logged")
first, second = g1["events"][0]["n"], g1["events"][1]["n"]
r = analyst.post(f"{A}/remove", json={"n": first}).get_json()
check(len(r["events"]) == 2 and all(e["n"] != first for e in r["events"]) and r["log"][-1]["op"] == "remove" and "removed" in r["log"][-1]["detail"], "any action can be removed, not only the last ones")
r = analyst.post(f"{A}/edit", json={"n": second, "pid": five[3], "stat": "p3_m", "clock": {"q": 2, "t": 311}})
e2 = next(e for e in r.get_json()["events"] if e["n"] == second)
check(r.status_code == 200 and e2["pid"] == five[3] and e2["stat"] == "p3_m" and (e2["q"], e2["t"]) == (2, 311) and e2["edited_by"] == "Tester One" and e2["by"] == "Tester One", "an action can be changed: player, action, time")
check("changed" in r.get_json()["log"][-1]["detail"] and "→" in r.get_json()["log"][-1]["detail"], "the change log says what was changed")
check(analyst.post(f"{A}/edit", json={"n": second, "pid": "nobody-1"}).status_code == 422 and analyst.post(f"{A}/edit", json={"n": second, "stat": "dunk"}).status_code == 422
      and analyst.post(f"{A}/edit", json={"n": 9999, "stat": "ast"}).status_code == 422 and analyst.post(f"{A}/edit", json={"n": second, "clock": {"q": 99, "t": 1}}).status_code == 422, "bad edits are refused")
check("q" not in next(e for e in analyst.post(f"{A}/edit", json={"n": second, "clock": None}).get_json()["events"] if e["n"] == second), "the clock of an action can be taken off")
# an action entered late but timed earlier falls in its place: the five that leaves at 5:00 still gets the points scored before
analyst.post(f"{A}/lineup", json={"team": "CA", "on": five, "q": 1, "t": 600})
analyst.post(f"{A}/lineup", json={"team": "CA", "on": five[:4] + [bench], "q": 1, "t": 300})
analyst.post(f"{A}/event", json={"pid": five[0], "stat": "p2_m", "q": 1, "t": 400})                     # entered after the substitution, played before it
pmA = analyst.get(A).get_json()["court"]["pm"]
check(pmA.get(five[4]) == 2 and pmA.get(bench, 0) == 0, f"actions are placed by the game clock: {pmA}")
# the admin edits every version; an analyst cannot touch a version that was sent for approval
sub = two.post(f"/analytics/api/games/{gb['id']}/event", json={"pid": ca[0]["id"], "stat": "p2_m"}).get_json()
check(two.post(f"/analytics/api/games/{gb['id']}/submit", json={"matchday": 16, "date": "2099-01-16"}).status_code == 200, "version B sent for approval")
check(two.post(f"/analytics/api/games/{gb['id']}/event", json={"pid": ca[0]["id"], "stat": "p2_m"}).status_code == 409, "an analyst cannot change a version waiting for approval")
r = adm.post(f"/analytics/api/games/{gb['id']}/event", json={"pid": ca[1]["id"], "stat": "p3_m"}, environ_overrides=ip("198.51.100.62"))
check(r.status_code == 200 and r.get_json()["events"][-1]["by"] == "Admin" and r.get_json()["status"] == "submitted", "the admin can add to a version waiting for approval, stamped Admin")
r = adm.post(f"/analytics/api/games/{gb['id']}/edit", json={"n": r.get_json()["events"][-1]["n"], "stat": "ast"}, environ_overrides=ip("198.51.100.62"))
check(r.status_code == 200 and r.get_json()["log"][-1]["by"] == "Admin", "and edit it, logged as Admin")
# the admin tab: every version with its analyst and log; approving one takes the other off the site
analyst.post(f"{A}/submit", json={"matchday": 16, "date": "2099-01-16", "q": 1, "t": 0})
lst = {x["id"]: x for x in adm.get("/admin/api/analytics", environ_overrides=ip("198.51.100.62")).get_json()["games"]}
check(lst[ga["id"]]["analyst"] == "Tester One" and lst[gb["id"]]["analyst"] == "Tester Two" and lst[gb["id"]]["log"] and lst[ga["id"]]["editable"], "the admin list shows each version, its analyst and its log")
ap = lambda gid_: adm.post(f"/admin/api/analytics/{gid_}/approve", json={}, environ_overrides=ip("198.51.100.62"))
check(ap(ga["id"]).status_code == 200 and ap(gb["id"]).status_code == 200, "both versions approved one after the other")
stored = lambda: sorted(x["id"] for x in json.loads((config.DATA_DIR / "partial_games.json").read_text())["games"] if x["id"].startswith("live-j16-"))
pub = stored()
check(pub and all("tester-two" in x for x in pub) and any("tester-two" in x for x in pub), f"only one version is on the site: {pub}")
st = {x["id"]: x["status"] for x in adm.get("/admin/api/analytics", environ_overrides=ip("198.51.100.62")).get_json()["games"]}
check(st[gb["id"]] == "published" and st[ga["id"]] == "submitted", f"the first version stepped down: {st}")
check(adm.post(f"/admin/api/analytics/{gb['id']}/unpublish", json={}, environ_overrides=ip("198.51.100.62")).status_code == 200 and stored() == [], "unpublishing removes exactly that version's sheets")
# live: one version of a game at a time
for who_, cl in ((ga, analyst), (gb, two)):
    cl.post(f"/analytics/api/games/{who_['id']}/reopen", json={})
live_ = lambda gid_, on: adm.post(f"/admin/api/analytics/{gid_}/live", json={"on": on}, environ_overrides=ip("198.51.100.62"))
live_(ga["id"], True)
live_(gb["id"], True)
cnt = {x["id"]: x["live"] for x in adm.get("/admin/api/analytics", environ_overrides=ip("198.51.100.62")).get_json()["counting"]}
check(cnt.get(gb["id"]) and not cnt.get(ga["id"]) and [g["id"] for g in anon.get("/api/live").get_json()["games"] if g["id"].startswith("j16-")] == [gb["id"]], f"only one version of a game is live: {cnt}")

# 11. no more counting from the video; any played game can be opened to edit it, and is never live
check(analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 12, "video": True}).status_code == 422, "counting from the video is refused")
full_game = next(g for g in stats.build()["games"] if g.get("matchday_no"))
fa, fb = [t["code"] for t in full_game["teams"]]
r = analyst.post("/analytics/api/games", json={"home": fa, "away": fb, "matchday": full_game["matchday_no"]})
old = r.get_json()
check(r.status_code == 200 and old["kind"] == "live", f"a game that already has a full box score can be opened to edit it: {r.status_code} {old.get('error')}")
check(next(x for x in analyst.get("/analytics/api/data").get_json()["games"] if x["id"] == old["id"])["old"] is True, "it is flagged old")
check(adm.post(f"/admin/api/analytics/{old['id']}/live", json={"on": True}, environ_overrides=ip("198.51.100.62")).status_code == 409, "an old game can never be live")
check(analyst.post(f"/analytics/api/games/{old['id']}/event", json={"pid": old["players"][old["home"]][0]["id"], "stat": "p2_m"}).status_code == 200, "and it is counted like any other game")
check(not any(g["id"] == old["id"] for g in anon.get("/api/live").get_json()["games"]), "it is not in the Live section")
# 12. the admin list: an old game (even one a past version left flagged live) is in its own group, never shown as live, and the admin can delete it; the newest game comes first
g_old = json.loads((config.DATA_DIR / "analytics" / f"{old['id']}.json").read_text())
g_old["live"] = True                              # the stale flag an earlier version left
(config.DATA_DIR / "analytics" / f"{old['id']}.json").write_text(json.dumps(g_old))
newest = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 40, "date": "2099-01-01"}).get_json()
cl = adm.get("/admin/api/analytics", environ_overrides=ip("198.51.100.62")).get_json()["counting"]
by = {x["id"]: x for x in cl}
check(by[old["id"]]["old"] is True and by[old["id"]]["live"] is False, f"an old game is flagged old and never shown as live: {by.get(old['id'])}")
check(by[newest["id"]]["old"] is False and cl[0]["id"] == newest["id"], f"the game worked on last comes first: {[x['id'] for x in cl][:3]}")
check(adm.post(f"/admin/api/analytics/{old['id']}/delete", json={}, environ_overrides=ip("198.51.100.62")).status_code == 200 and not (config.DATA_DIR / "analytics" / f"{old['id']}.json").exists(), "the admin can delete an old game")
check(analyst.post(f"/admin/api/analytics/{newest['id']}/delete", json={}, environ_overrides=ip("198.51.100.3")).status_code == 401, "an analyst cannot use the admin delete")
check(adm.post(f"/admin/api/analytics/{gb['id']}/delete", json={}, environ_overrides=ip("198.51.100.62")).status_code == 200, "a game still being counted can be deleted by the admin")
analyst.delete(f"/analytics/api/games/{newest['id']}")

# 13. the public live data carries each team's line so far (the sum of its players) and the tagged scoring lines
lg = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 41, "date": "2099-02-02"}).get_json()
LA = f"/analytics/api/games/{lg['id']}"
pl = lambda code, i: lg["players"][code][i]["id"]
for code, i, st, tags in [("CA", 0, "p2_m", ["paint"]), ("CA", 0, "p3_x", None), ("CA", 1, "p3_m", None), ("CA", 1, "oreb", None), ("CA", 2, "ast", None), ("ESG", 0, "ft_m", None), ("ESG", 0, "ft_x", None), ("ESG", 1, "tov", None)]:
    body = {"pid": pl(code, i), "stat": st, **({"tags": tags} if tags else {})}
    r = analyst.post(f"{LA}/event", json=body)
    if tags and r.status_code == 200 and r.get_json()["events"][-1].get("tags") != tags:
        analyst.post(f"{LA}/edit", json={"n": r.get_json()["events"][-1]["n"], "tags": tags})
adm.post(f"/admin/api/analytics/{lg['id']}/live", json={"on": True}, environ_overrides=ip("198.51.100.62"))
lv = next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == lg["id"])
ca_t, esg_t = lv["teams"]["CA"]["totals"], lv["teams"]["ESG"]["totals"]
check((ca_t["pts"], ca_t["fgm"], ca_t["fga"], ca_t["p3m"], ca_t["p3a"], ca_t["oreb"], ca_t["reb"], ca_t["ast"]) == (5, 2, 3, 1, 2, 1, 1, 1), f"the live team line is the sum of its players: {ca_t}")
check((esg_t["pts"], esg_t["ftm"], esg_t["fta"], esg_t["tov"]) == (1, 1, 2, 1), f"and the other team's: {esg_t}")
check(lv["teams"]["CA"]["extra"].get("paint") == 2 and lv["teams"]["ESG"]["extra"].get("paint") == 0, f"the points in the paint of the tagged baskets are public too: {lv['teams']['CA']['extra']}")
analyst.delete(f"/analytics/api/games/{lg['id']}")

# 14. which team has the ball: deduced from the last action, or set by the analyst until the next action
bg = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 42, "date": "2099-03-03"}).get_json()
BA = f"/analytics/api/games/{bg['id']}"
ev = lambda code, i, st: analyst.post(f"{BA}/event", json={"pid": bg["players"][code][i]["id"], "stat": st}).get_json()["ball"]
check(analyst.get(BA).get_json()["ball"]["team"] is None, "nobody has the ball before the first action")
steps = [("CA", "p2_m", "ESG"), ("ESG", "p2_x", None), ("CA", "dreb", "CA"), ("CA", "tov", "ESG"), ("CA", "stl", "CA"), ("CA", "pf", "ESG"), ("ESG", "fd", "ESG"),
         ("ESG", "p3_m", "CA"), ("ESG", "ast", "CA"),                    # an assist entered after its basket does not give the ball back
         ("ESG", "ft_m", "ESG"), ("ESG", "ft_m", "CA"),                  # a first free throw: still his; the second one made: the other team
         ("CA", "p2_x", None), ("ESG", "oreb", "ESG")]
for code, st, want in steps:
    got = ev(code, 0, st)["team"]
    check(got == want, f"ball after {code} {st}: wanted {want}, got {got}")
r = analyst.post(f"{BA}/ball", json={"team": "CA"})
check(r.status_code == 200 and r.get_json()["ball"] == {"team": "CA", "how": "manual", "manual": True}, f"the analyst can set the ball: {r.get_json().get('ball')}")
check(analyst.post(f"{BA}/ball", json={"team": "XXX"}).status_code == 422, "only one of the two teams can have the ball")
check(ev("ESG", 0, "p2_m")["manual"] is False, "the next action takes over again")
analyst.post(f"{BA}/ball", json={"team": "ESG"})
check(analyst.post(f"{BA}/ball", json={"team": None}).get_json()["ball"]["manual"] is False, "and tapping again clears the manual ball")
adm.post(f"/admin/api/analytics/{bg['id']}/live", json={"on": True}, environ_overrides=ip("198.51.100.62"))
lvb = next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == bg["id"])
check(lvb["ball"]["team"] == "CA" and lvb["ball"]["how"] == "basket", f"the public live data carries the ball: {lvb['ball']}")
analyst.delete(f"/analytics/api/games/{bg['id']}")

# 15. how the game went: biggest lead, longest run, lead changes and ties, from the points in game order
fgm = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 43, "date": "2099-04-04"}).get_json()
FA = f"/analytics/api/games/{fgm['id']}"
for code, st in [("CA", "p3_m"), ("CA", "p2_m"), ("ESG", "p2_m"), ("ESG", "p3_m"), ("ESG", "p2_m"), ("CA", "ft_m"), ("CA", "p2_m"), ("CA", "p2_m"), ("ESG", "ft_m")]:
    analyst.post(f"{FA}/event", json={"pid": fgm["players"][code][0]["id"], "stat": st})
adm.post(f"/admin/api/analytics/{fgm['id']}/live", json={"on": True}, environ_overrides=ip("198.51.100.62"))
fl = next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == fgm["id"])["flow"]
# CA 3, 5 | ESG 2, 5(tie), 7 | CA 8, 10, 12 | ESG 13?? -> scores: CA3-0, CA5-0, 5-2, 5-5 (tie), 5-7 (ESG ahead), CA 6-7, 8-7 (CA ahead), 10-7, 10-8
check(fl["lead"] == {"CA": 5, "ESG": 2} and fl["run"] == {"CA": 5, "ESG": 7}, f"biggest lead and longest run: {fl}")
check(fl["changes"] == 2 and fl["ties"] == 1, f"lead changes and ties: {fl}")
check(next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == fgm["id"])["quarters"] is None, "without the game clock there is no score by quarter")
analyst.post(f"{FA}/event", json={"pid": fgm["players"]["CA"][0]["id"], "stat": "p3_m", "q": 2, "t": 300})      # CA +3 in the 2nd quarter
analyst.post(f"{FA}/event", json={"pid": fgm["players"]["ESG"][0]["id"], "stat": "p2_m", "q": 4, "t": 10})      # ESG +2 in the 4th
qs = next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == fgm["id"])["quarters"]
check(qs and qs["periods"] == 4 and qs["pts"]["CA"][1] == 3 and qs["pts"]["ESG"][3] == 2 and sum(qs["pts"]["CA"]) == 13 and sum(qs["pts"]["ESG"]) == 10, f"the score by quarter follows the game clock: {qs}")
analyst.post(f"{FA}/event", json={"pid": fgm["players"]["CA"][1]["id"], "stat": "p2_m", "q": 5, "t": 120})       # overtime: a fifth column appears by itself
qs = next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == fgm["id"])["quarters"]
check(qs and qs["periods"] == 5 and qs["pts"]["CA"][4] == 2 and sum(qs["pts"]["CA"]) == 15, f"an overtime adds its own period to the score by quarter: {qs}")
analyst.delete(f"/analytics/api/games/{fgm['id']}")

# 16. technical fouls, injury, ejection, timeouts, team rebounds / turnovers
tg = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 44, "date": "2099-05-05"}).get_json()
TA = f"/analytics/api/games/{tg['id']}"
pid_ = lambda code, i: tg["players"][code][i]["id"]
for code, i, st in [("CA", 0, "pf"), ("CA", 0, "tf"), ("CA", 1, "inj"), ("ESG", 0, "ej"), ("ESG", 1, "tov")]:
    check(analyst.post(f"{TA}/event", json={"pid": pid_(code, i), "stat": st}).status_code == 200, f"player action {st} is accepted")
for code, st in [("CA", "timeout"), ("CA", "timeout"), ("ESG", "t_tov"), ("CA", "t_dreb"), ("CA", "tf_c"), ("ESG", "tf_b")]:
    r = analyst.post(f"{TA}/team", json={"team": code, "stat": st})
    check(r.status_code == 200, f"team action {st} is accepted: {r.status_code} {r.get_json()}")
check(analyst.post(f"{TA}/team", json={"team": "XXX", "stat": "timeout"}).status_code == 422 and analyst.post(f"{TA}/team", json={"team": "CA", "stat": "p2_m"}).status_code == 422, "an unknown team or a player action is refused on the team route")
v = analyst.get(TA).get_json()
ca_, esg_ = v["totals"]["CA"], v["totals"]["ESG"]
check(ca_["timeouts"] == 2 and ca_["pf"] == 2 and ca_["team_reb"] == 1 and ca_["dreb"] == 1 and ca_["reb"] == 1 and ca_["techs"] == 2, f"CA totals: {ca_}")
check(esg_["tov"] == 2 and esg_["team_tov"] == 1 and esg_["techs"] == 1, f"ESG totals (a team turnover adds to the turnovers): {esg_}")
check(next(e for e in v["events"] if e["stat"] == "timeout")["pid"] is None and v["team_events"]["CA"]["timeout"] == 2, "team events belong to no player")
check(sum(ptsv for ptsv in analyst.get(TA).get_json()["court"]["pm"].values()) == 0, "team events never touch the court")
adm.post(f"/admin/api/analytics/{tg['id']}/live", json={"on": True}, environ_overrides=ip("198.51.100.62"))
lv_ = next(x for x in anon.get("/api/live").get_json()["games"] if x["id"] == tg["id"])
texts = [p["text"] for p in lv_["plays"]]
check("timeout" in texts and "team turnover" in texts and "technical foul" in texts and "injured" in texts and "ejected" in texts, f"the live plays name them: {texts}")
row_ = next(p for p in lv_["teams"]["ESG"]["players"] if p["id"] == pid_("ESG", 0))
check(row_["ej"] is True and next(p for p in lv_["teams"]["CA"]["players"] if p["id"] == pid_("CA", 1))["inj"] is True, "the live rows flag the ejected and the injured players")
check(lv_["teams"]["CA"]["totals"]["timeouts"] == 2, "the public totals carry the timeouts")
tev = next(e for e in v["events"] if e["stat"] == "timeout")
check(analyst.post(f"{TA}/edit", json={"n": tev["n"], "stat": "t_oreb", "team": "ESG"}).status_code == 200 and analyst.get(TA).get_json()["team_events"]["ESG"].get("t_oreb") == 1, "a team event can be changed")
check(analyst.post(f"{TA}/ball", json={"team": "CA"}).status_code == 200, "the ball still works with team events")
analyst.delete(f"/analytics/api/games/{tg['id']}")

print("FAILED:\n  " + "\n  ".join(fails) if fails else "analytics checks passed")
sys.exit(1 if fails else 0)
