"""Games tab (time, date, featured rank), results typed by hand with optional stats, news with labels, leaders on the players API, Facebook link."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda path, body, h=H: c.post(path, json=body, headers=h)
plan = lambda: c.get("/api/planning").get_json()["matchdays"]
g0 = next(g for m in plan() for g in m["games"] if not g["played"])
key, md = g0["key"], int(g0["key"].split(":")[0])

# --- admin only
for method, path in (("get", "/admin/api/schedule"), ("post", "/admin/api/schedule"), ("post", "/admin/api/result"), ("get", "/admin/api/news"), ("post", "/admin/api/news"), ("post", "/admin/api/news/delete")):
    check(getattr(c, method)(path).status_code == 401, f"{method} {path} needs the admin login")

# --- schedule: time, own date, featured rank
check(post("/admin/api/schedule", {"key": key, "time": "18:30", "featured": 2}).status_code == 200, "time and rank saved")
g = next(x for m in plan() for x in m["games"] if x["key"] == key)
check(g["time"] == "18:30" and g["featured"] == 2, f"the calendar carries them: {g}")
check(post("/admin/api/schedule", {"key": key, "time": "25:99"}).status_code == 422, "a bad time is refused")
check(post("/admin/api/schedule", {"key": key, "featured": 500}).status_code == 422, "a rank above 99 is refused")
check(post("/admin/api/schedule", {"key": key, "date": "tomorrow"}).status_code == 422, "a bad date is refused")
check(post("/admin/api/schedule", {"key": "12:XX-YY", "time": "18:00"}).status_code == 422, "a game that is not in the calendar is refused")
check(post("/admin/api/schedule", {"key": key, "date": "2026-11-12", "time": "20:00", "featured": 1}).status_code == 200, "own date saved")
g = next(x for m in plan() for x in m["games"] if x["key"] == key)
check(g["game_date"] == "2026-11-12" and g["featured"] == 1, "rank and own date updated")
check(post("/admin/api/schedule", {"key": key}).status_code == 200, "empty fields clear")
g = next(x for m in plan() for x in m["games"] if x["key"] == key)
check(g["time"] is None and g["featured"] is None and g["game_date"] is None, "cleared")
sc = c.get("/admin/api/schedule", headers=H).get_json()
check(sc["matchdays"] and "key" in sc["matchdays"][0]["games"][0] and "officiel" not in sc and sc["teams"], "the admin sees the calendar")

# --- a result typed by hand, with optional stats
before = {r["code"]: r["j"] for r in c.get("/api/home").get_json()["standings"]}
bad = post("/admin/api/result", {"matchday": md, "home": g0["home"], "away": g0["home"], "home_score": 70, "away_score": 60}).status_code
check(bad == 422, "a team cannot play itself")
check(post("/admin/api/result", {"matchday": md, "home": g0["home"], "away": g0["away"], "home_score": 80}).status_code == 422, "both scores are required")
check(post("/admin/api/result", {"matchday": md, "home": g0["home"], "away": g0["away"], "home_score": 80, "away_score": 70, "players": [{"name": "X", "team": "ZZZ", "pts": 5}]}).status_code == 422, "a stat line belongs to one of the two teams")
check(post("/admin/api/result", {"matchday": md, "home": g0["home"], "away": g0["away"], "home_score": 80, "away_score": 70, "players": [{"name": "X", "team": g0["home"], "pts": 500}]}).status_code == 422, "absurd stats are refused")
r = post("/admin/api/result", {"matchday": md, "home": g0["home"], "away": g0["away"], "home_score": 80, "away_score": 70, "note": "Decisive run", "players": [{"name": "Test Player", "team": g0["home"], "pts": 25, "reb": 9}, {"name": ""}]})
check(r.status_code == 200 and "added" in r.get_json()["message"], f"result saved: {r.get_json()}")
home = c.get("/api/home").get_json()
top = home["recent"][0]
check(top["id"] is None and top["teams"][0]["points"] == 80 and top["note"] == "Decisive run" and top["players"] == [{"name": "Test Player", "team": g0["home"], "pts": 25, "reb": 9}], f"the latest games list it at once, with its note and stats: {top}")
after = {r["code"]: r["j"] for r in home["standings"]}
check(after[g0["home"]] == before[g0["home"]] + 1, "the standings count it")
g = next(x for m in plan() for x in m["games"] if x["key"] == key)
check(g["played"] and g["home_score"] == 80, "the calendar shows it played")
check("updated" in post("/admin/api/result", {"matchday": md, "home": g0["home"], "away": g0["away"], "home_score": 81, "away_score": 70}).get_json()["message"], "sending it again corrects it")
check(c.get("/api/home").get_json()["recent"][0]["players"] == [], "a correction without stats clears the old stats")
check(c.get("/api/home").headers.get("Cache-Control") == "no-cache", "the home data is never cached")

# --- news
check(post("/admin/api/news", {"label": "injury", "title": "", "body": "x"}).status_code == 422, "a title is required")
check(post("/admin/api/news", {"label": "gossip", "title": "x"}).status_code == 422, "unknown label refused")
check(post("/admin/api/news", {"label": "info", "title": "x", "date": "yesterday"}).status_code == 422, "bad date refused")
a = post("/admin/api/news", {"label": "injury", "title": "Player out 6 weeks", "body": "Knee injury", "date": "2026-11-05", "title_en": "Player out for 6 weeks"}).get_json()["item"]
b = post("/admin/api/news", {"label": "official", "title": "Calendar published", "date": "2026-11-08"}).get_json()["item"]
pin = post("/admin/api/news", {"label": "transfer", "title": "Pinned one", "date": "2026-10-01", "pinned": True}).get_json()["item"]
items = c.get("/api/news").get_json()["items"]
check([n["id"] for n in items] == [pin["id"], b["id"], a["id"]], "pinned first, then newest first")
check(a["label"] == "injury" and "injury" in c.get("/api/news").get_json()["labels"], "labels")
check(len(c.get("/api/home").get_json()["news"]) == 3, "the home page gets the latest news")
check(post("/admin/api/news", {"id": a["id"], "label": "injury", "title": "Back in 4 weeks", "date": "2026-11-05"}).status_code == 200 and c.get("/api/news").get_json()["items"][2]["title"] == "Back in 4 weeks", "a news item can be edited")
check(post("/admin/api/news", {"id": "nope", "label": "info", "title": "x"}).status_code == 422, "editing a missing item is refused")
check(post("/admin/api/news/delete", {"id": b["id"]}).get_json()["ok"] and len(c.get("/api/news").get_json()["items"]) == 2, "a news item can be deleted")

# --- the rest
pl = c.get("/api/players").get_json()
check(len(pl["leaders"]) >= 6 and pl["leaders"][0]["top"], "the players page gets the league leaders")
html = c.get("/").get_data(as_text=True)
check("facebook.com/people/Tunisia-Basket/61596371069928" in html and "Facebook" in html, "the footer links to the Facebook page, with the invitation")
check(c.get("/actualites").status_code == 200 and c.get("/en/news").status_code == 200, "the news page exists in both languages")
check("Pinned one" in c.get("/actualites").get_data(as_text=True), "crawlers see the news titles")
print("content:", "FAILED" if fails else "ok")
for m_ in fails:
    print(" -", m_)
sys.exit(1 if fails else 0)
