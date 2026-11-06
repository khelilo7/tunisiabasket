"""Quick 'does this build start and serve data' check. Used by CI and by the server before switching to a new release.
Run with a throwaway data folder:  DATA_DIR=$(mktemp -d) python tests/smoke.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

c = app.app.test_client()
checks = {"/": 200, "/admin": 200, "/api/overview": 200, "/api/players": 200, "/api/games": 200,
          "/api/planning": 200, "/fr/": 200, "/standings": 200, "/fr/classement": 200, "/sitemap.xml": 200, "/robots.txt": 200, "/favicon.ico": 200, "/img/teams/CA.png": 200, "/api/teams/CA": 200, "/api/teams/ZZZ": 404, "/admin/api/official": 401}
bad = 0
for path, want in checks.items():
    got = c.get(path).status_code
    if got != want:
        bad += 1
        print(f"FAIL {path}: {got} (expected {want})")
if c.post("/api/sync").status_code != 401:
    bad += 1
    print("FAIL anonymous POST /api/sync must be 401")
gid = c.get("/api/games").get_json()["games"][0]["id"]
if "lineups" not in c.get("/api/games/" + gid).get_json():
    bad += 1
    print("FAIL game page data has no lineups")
d = c.get("/api/overview").get_json()
if not d["games"] or not d["mvp"] or len(d["standings"]) != 12:
    bad += 1
    print("FAIL overview has no data:", d["games"], d["mvp"] and d["mvp"]["name"], len(d["standings"]))
print("smoke:", "FAILED" if bad else f"ok ({d['games']} games, MVP {d['mvp']['name']})")
sys.exit(1 if bad else 0)
