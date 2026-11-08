"""POST /admin/api/game: a hand-transcribed box score is checked, saved, shown on the site, and re-sending it changes nothing."""
import copy
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

def player(num, name, pts):
    return {"number": num, "name": name, "starter": True, "captain": False, "dnp": False, "min": 200.0, "fgm": pts // 2, "fga": pts // 2, "p2m": pts // 2, "p2a": pts // 2, "p3m": 0, "p3a": 0,
            "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0, "reb": 0, "ast": 0, "tov": 0, "stl": 0, "blk": 0, "pf": 0, "fd": 0, "pm": 0, "pts": pts}
game = {"competition": "TEST", "date": "2026-09-30", "source": "claude", "date_approx": False, "matchday_no": 2, "matchday": "J2", "source_file": "hand.pdf", "id": "up-test0001",
        "teams": [{"code": "USM", "name": "UNION SPORTIVE MONASTIRIENNE", "coach": "", "points": 66, "players": [player(2, "TEST ONE", 66)]},
                  {"code": "CSS", "name": "CLUB SPORTIF SFAXIEN", "coach": "", "points": 54, "players": [player(9, "TEST TWO", 54)]}]}
n0 = len(c.get("/api/games").get_json()["games"])
check(c.post("/admin/api/game", json={"game": game}).status_code == 401, "admin only")
r = c.post("/admin/api/game", json={"game": game}, headers=H)
check(r.status_code == 200, f"saved: {r.status_code} {r.get_json()}")
check(len(c.get("/api/games").get_json()["games"]) == n0 + 1, "the game is on the site")
r = c.post("/admin/api/game", json={"game": game}, headers=H)
check(r.status_code == 200 and len(c.get("/api/games").get_json()["games"]) == n0 + 1, "sending it again changes nothing")
bad = copy.deepcopy(game); bad["id"] = "up-test0002"; bad["teams"][0]["players"][0]["pts"] = 60
r = c.post("/admin/api/game", json={"game": bad}, headers=H)
check(r.status_code == 422 and r.get_json().get("problems"), "points that do not add up are refused")
check(c.post("/admin/api/game", json={"game": {"teams": []}}, headers=H).status_code == 422, "malformed body refused")
bad2 = copy.deepcopy(game); bad2["id"] = "../etc"
check(c.post("/admin/api/game", json={"game": bad2}, headers=H).status_code == 422, "path tricks in the id refused")
print("import game:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
