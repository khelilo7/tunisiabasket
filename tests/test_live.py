"""Live board and news feed: admin-only updates, rules (scores, periods, finish/reopen), what visitors see, news items."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import live  # noqa: E402

auth.time.sleep = lambda s: None
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda body: c.post("/admin/api/live", json=body, headers=H)

check(c.get("/api/live").get_json()["live"] == [], "nothing live at first")
check(c.post("/admin/api/live", json={"op": "create", "home": "CA", "away": "JSK"}).status_code == 401, "only the admin can start a match")
check(c.get("/admin/api/live").status_code == 401, "the admin list is private")
check(post({"op": "create", "home": "CA", "away": "CA"}).status_code == 422, "two different teams")
check(post({"op": "create", "home": "ZZZ", "away": "CA"}).status_code == 422, "unknown team")

m = post({"op": "create", "home": "CA", "away": "JSK", "matchday": "J12", "start": True}).get_json()["match"]
check(m["status"] == "live" and m["home_score"] == 0, "created and started")
check(post({"op": "create", "home": "JSK", "away": "CA", "start": True}).status_code == 422, "the same match cannot be live twice")
check(post({"op": "update", "id": m["id"], "home_score": 21, "away_score": 18, "clock": "02:10"}).status_code == 200, "score update")
check(post({"op": "update", "id": m["id"], "home_score": -3}).status_code == 422 and post({"op": "update", "id": m["id"], "home_score": 999}).status_code == 422, "scores stay in range")
check(post({"op": "update", "id": m["id"], "period": "7"}).status_code == 422, "bad period refused")
check(post({"op": "update", "id": m["id"], "period": "2", "note": "10-0 run for CA"}).status_code == 200, "period + note")
b = c.get("/api/live").get_json()
mm = b["live"][0]
check(len(b["live"]) == 1 and mm["home_name"] == "Club Africain" and mm["period"] == "2" and (mm["home_score"], mm["away_score"]) == (21, 18), "visitors see the live score")
ep = next((u for u in mm["updates"] if u["kind"] == "end_period"), None)
check(ep and ep["period"] == "1" and (ep["home_score"], ep["away_score"]) == (21, 18), "end-of-period line keeps the score as it stood")
check(mm["updates"][0]["text"] == "10-0 run for CA" and mm["updates"][-1]["kind"] == "tipoff", "automatic and manual updates logged, newest first")
check(c.get("/api/live").headers["Cache-Control"] == "no-store", "live data is never cached")

post({"op": "update", "id": m["id"], "home_score": 79, "away_score": 71, "period": "4"})
check(post({"op": "finish", "id": m["id"]}).status_code == 200, "finish")
b = c.get("/api/live").get_json()
check(b["live"] == [] and len(b["final"]) == 1 and b["final"][0]["home_score"] == 79, "finished match stays visible as final")
check(post({"op": "update", "id": m["id"], "home_score": 80}).status_code == 422, "a finished match is locked")
check(post({"op": "reopen", "id": m["id"]}).status_code == 200 and len(c.get("/api/live").get_json()["live"]) == 1, "reopen")
post({"op": "finish", "id": m["id"]})

# news: results by matchday with the player of the matchday, the finished live match, and the vote while it is open
n = c.get("/api/news").get_json()["items"]
kinds = [x["kind"] for x in n]
check("matchday" in kinds and "live_final" in kinds and "vote" in kinds, f"news kinds: {kinds}")
day = next(x for x in n if x["kind"] == "matchday")
check(day["results"] and day["best"] and day["results"][0]["home_name"], "matchday news has results and a player of the matchday")
lf = next(x for x in n if x["kind"] == "live_final")
check((lf["match"]["home_score"], lf["match"]["away_score"]) == (79, 71), "the finished live match is news")

# old finals leave the board after 36 h, deletion works, the file never holds personal data
d = live._load(); d["matches"][0]["finished"] = int(time.time()) - 40 * 3600; live._save(d)
check(c.get("/api/live").get_json()["final"] == [], "a final older than 36 hours leaves the board")
check(post({"op": "delete", "id": m["id"]}).status_code == 200 and c.get("/admin/api/live", headers=H).get_json()["matches"] == [], "delete")
check(c.get("/").status_code == 200 and c.get("/admin-live.js").status_code == 200, "pages and scripts served")

print("live:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
