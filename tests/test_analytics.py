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
codes = [visitor.post("/analytics/api/login", json={"token": "bad%d" % i}, environ_overrides=ip("198.51.100.2")).status_code for i in range(6)]
check(codes == [401] * 5 + [429], f"lockout after 5 wrong tokens: {codes}")
check(visitor.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333"}, environ_overrides=ip("198.51.100.2")).status_code == 429, "locked out even with the right token")
check(analyst.post("/analytics/api/login", json={"token": "TEST-TOKEN-0000-1111"}, environ_overrides=ip("198.51.100.3")).status_code == 401, "the ADMIN token is not an analytics token")
r = analyst.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333"}, environ_overrides=ip("198.51.100.3"))
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

# 3. counting
g = analyst.post("/analytics/api/games", json={"home": "CA", "away": "ESG", "matchday": 12, "date": "2026-11-11"}).get_json()
gid = g["id"]
check(gid == "j12-ca-esg" and g["status"] == "open" and [p["id"] for p in g["players"]["CA"]] == [p["id"] for p in ca], "game created with the site's players")
check(analyst.post("/analytics/api/games", json={"home": "CA", "away": "CA"}).status_code == 422 and analyst.post("/analytics/api/games", json={"home": "CA", "away": "ZZZ"}).status_code == 422, "bad teams refused")
ev = lambda pid, stat: analyst.post(f"/analytics/api/games/{gid}/event", json={"pid": pid, "stat": stat})
a, b, c_ = ca[0]["id"], ca[1]["id"], esg[0]["id"]
for pid, stat in [(a, "p3_m"), (a, "p2_m"), (a, "ft_m"), (a, "p2_x"), (a, "oreb"), (a, "ast"), (b, "p2_m"), (b, "dreb"), (b, "tov"), (b, "pf"), (c_, "p3_m"), (c_, "p3_x"), (c_, "stl"), (c_, "blk")]:
    check(ev(pid, stat).status_code == 200, f"event {pid} {stat}")
check(ev("nobody-1", "ast").status_code == 422 and ev(a, "dunk").status_code == 422, "unknown player or action refused")
g = analyst.get(f"/analytics/api/games/{gid}").get_json()
s = analytics.scores(g)
check(s == {"CA": 8, "ESG": 3}, f"score from the events: {s}")
check(analytics.line(analytics.tally(g)[a]) == {"pts": 6, "fgm": 2, "fga": 3, "p3m": 1, "p3a": 1, "ftm": 1, "fta": 1, "oreb": 1, "dreb": 0, "ast": 1, "stl": 0, "blk": 0, "tov": 0, "pf": 0}, "one player's line")
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
check(ids == ["live-j12-ca-esg-ca", "live-j12-ca-esg-esg"], f"two one-team sheets published: {ids}")
sheet = next(x for x in doc["games"] if x["recorded"] == "CA")
check(sheet["matchday"] == 12 and sheet["date"] == "2026-11-11" and sheet["players"][0]["pts"] == 6 and sheet["players"][0]["oreb"] == 1, "the sheet carries the counted stats")

# 6. it shows only when the official result exists, and never counts as a box score
check(public_partials() == [], "approved, but ignored while the official result of J12 does not exist")
o = stats.load_official()
o["results"].append({"matchday": 12, "home": "CA", "away": "ESG", "home_score": 8, "away_score": 3})
(config.DATA_DIR / "official.json").write_text(json.dumps(o))
check(sorted(public_partials()) == ["live-j12-ca-esg-ca", "live-j12-ca-esg-esg"], "with the official result, both sheets are on the site")
b2 = stats.build()
ca_row = next(p for p in b2["players"] if p["id"] == a)
last = ca_row["log"][-1]
check(last.get("min") is None and last.get("fd") is None and last.get("pm") is None and last["pts"] == 6 and last["tov"] == 0, "minutes, fouls drawn and +/- stay unknown (never 0); points, turnovers and fouls are the counted ones")
check(len(b2["games"]) == games_before, "it never becomes a box score")
check(json.dumps(stats.official_standings(), sort_keys=True) != standings_before, "standings changed only because the admin entered the official result")
lst = admin.get("/admin/api/analytics", environ_overrides=ip("198.51.100.5")).get_json()["games"]
check(lst[0]["official"]["home_score"] == 8 and lst[0]["same_score"] is True and lst[0]["status"] == "published", "the review shows that the score matches the official one")
check(analyst.delete(f"/analytics/api/games/{gid}").status_code == 409, "a published game cannot be deleted by an analyst")
check(admin.post(f"/admin/api/analytics/{gid}/unpublish", json={}, environ_overrides=ip("198.51.100.5")).status_code == 200 and public_partials() == []
      and json.loads((config.DATA_DIR / "partial_games.json").read_text())["games"] == [], "unpublished: gone from the site")
check(analyst.delete(f"/analytics/api/games/{gid}").status_code == 200 and analyst.get(f"/analytics/api/games/{gid}").status_code == 404, "an unpublished game can be deleted")

print("FAILED:\n  " + "\n  ".join(fails) if fails else "analytics checks passed")
sys.exit(1 if fails else 0)
