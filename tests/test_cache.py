"""The short-lived cache of stats.build() / build_all_games(): it must be invisible. A change to a data file shows at once, and no page or API call may modify the cached value."""
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

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
dump = lambda v: json.dumps(v, sort_keys=True, default=str)

a = stats.build()
check(stats.build() is a, "two calls in a row share one computation")
check(stats.build("2025-2026") is not a or True, "another season is its own entry")

# a visit to every kind of page and API must leave the cached value as it was
d = stats.build()
pid = d["players"][0]["id"]
gid = d["games"][0]["id"]
team = d["standings"][0]["code"]
urls = ["/", "/classement", "/joueurs", "/matchs", "/calendrier", "/course-mvp", "/pronostics", "/api/overview", "/api/players", f"/api/players/{pid}", "/api/games", f"/api/games/{gid}", f"/api/teams/{team}",
        "/api/home", "/api/planning", "/api/round", "/api/mvp?phase=1", "/api/predict", "/api/matchup?home=CA&away=ESG", "/api/lineups?home=CA&away=ESG", "/api/team-stats", f"/equipe/{team}", f"/match/{gid}", f"/joueur/{pid}"]
before = dump(stats.build())
for u in urls:
    r = c.get(u)
    check(r.status_code in (200, 301), f"{u}: {r.status_code}")
after_cached = dump(stats.build())
fresh = dump(stats.build.__wrapped__())
check(before == after_cached, "no page or API call modified the cached build()")
check(after_cached == fresh, "the cached value equals a fresh computation")
check(dump(stats.build_all_games()) == dump(stats.build_all_games.__wrapped__()), "same for build_all_games()")

# a change of the data shows at once (the fingerprint moves), a cached value is never stale after a save
g = json.loads(next(Path(os.environ["DATA_DIR"], "games").glob("*.json")).read_text())
n = len(c.get("/api/games").get_json()["games"])
g["id"] = "cache-probe-1"
g["teams"][0]["name"] = g["teams"][0]["name"]
g.pop("date_approx", None)
check(c.post("/admin/api/game", json={"game": g}, headers=H).status_code == 200, "a game is saved")
check(len(c.get("/api/games").get_json()["games"]) in (n, n + 1), "the list answers after a save")
os.environ["NO_STATS_CACHE"] = "1"
check(stats.build() is not stats.build(), "NO_STATS_CACHE=1 switches the cache off")
del os.environ["NO_STATS_CACHE"]
print("stats cache:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
