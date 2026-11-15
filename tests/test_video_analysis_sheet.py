"""A "Round N ... Final: video analysis" sheet (tools/video_analysis_sheet.py): read column by column, kept as a video game, and once it is on the site analysts can no longer count that game."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = tempfile.mkdtemp()
os.environ["DATA_DIR"] = DATA
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
os.environ["ANALYTICS_TOKEN"] = "TEST-ANALYST-2222-3333"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
official = json.loads((ROOT / "seed" / "official.json").read_text())
official["results"].append({"matchday": 13, "home": "JSK", "away": "ESR", "home_score": 69, "away_score": 60})   # the real J13 result, 14 Nov 2026
Path(DATA, "official.json").write_text(json.dumps(official))
import analytics  # noqa: E402
import app  # noqa: E402
import auth  # noqa: E402
import stats  # noqa: E402
import video_analysis_sheet as vas  # noqa: E402

auth.time.sleep = lambda s: None
analytics.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
PDF = ROOT / "tests" / "fixtures" / "video_analysis_jsk_esr_j13.pdf"

# 1. columns are read by position (blank cells are 0), and the sheet's own totals line adds up
g = vas.parse(PDF)
jsk, esr = g["teams"]
check((jsk["code"], jsk["points"], esr["code"], esr["points"], g["matchday_no"]) == ("JSK", 69, "ESR", 60, 13), "teams, score and round")
check(len(jsk["players"]) == 10 and len(esr["players"]) == 8, "ten JSK and eight ESR players")
for t, tot in ((jsk, dict(oreb=1, dreb=14, ast=6, tov=6, stl=4, blk=4, pf=6, fd=10, fga=37)), (esr, dict(oreb=2, dreb=5, ast=4, tov=5, stl=1, blk=1, pf=3, fd=10, fga=25))):
    for k, v in tot.items():
        check(sum(p[k] for p in t["players"]) == v, f"{t['code']}: {k} adds up to the sheet's totals line ({v})")
mn = next(p for p in jsk["players"] if p["number"] == 7)
check((mn["pts"], mn["p3m"], mn["p3a"], mn["stl"], mn["min"]) == (18, 5, 9, 3, 38), "Marnaoui: 18 pts, 5/9 from three, 3 steals, ~38 min")
check(next(p for p in jsk["players"] if p["number"] == 23)["fd"] == 4, "Chihi: 4 fouls drawn (a column far right of the shooting cells)")
check(next(p for p in jsk["players"] if p["number"] == 3)["fd"] == 2 and next(p for p in jsk["players"] if p["number"] == 3)["pf"] == 0, "Turner: FD 2, PF blank = 0")
check(mn["captain"] and next(p for p in esr["players"] if p["number"] == 8)["captain"], "captains")

# 2. the command line refuses a sheet whose arithmetic fails, accepts this one
out = Path(DATA) / "j13.json"
r = subprocess.run([sys.executable, str(ROOT / "tools" / "video_analysis_sheet.py"), str(PDF), "--date", "2026-11-14", "--out", str(out)], capture_output=True, text=True)
check(r.returncode == 0 and out.exists(), f"tool writes the game: {r.stdout} {r.stderr}")
game = json.loads(out.read_text())
check(game["id"] == "video-j13-jsk-esr" and game["date"] == "2026-11-14" and game["source"] == "video" and game["date_approx"] is False, "id, real date, source video")

# 3. the analysts could count it from the video until the sheet arrives; after the import they cannot (video list, video game or live game)
analyst = app.app.test_client()
analyst.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333", "name": "Tester One"}, environ_overrides={"REMOTE_ADDR": "198.51.100.9"})
todo = lambda: any(v["matchday"] == 13 and {v["home"], v["away"]} == {"JSK", "ESR"} for v in analytics.video_todo())
check(todo(), "before the import the game is on the analysts' video list")
c = app.app.test_client()
r = c.post("/admin/api/game", json={"game": game}, headers={"X-Admin-Token": "TEST-TOKEN-0000-1111"})
check(r.status_code == 200, f"the admin accepts it: {r.status_code} {r.get_json()}")
v = c.get("/api/games/video-j13-jsk-esr").get_json()
check(v["matchday"] == "J13" and v["date"] == "2026-11-14" and {t["code"]: t["points"] for t in v["teams"]} == {"JSK": 69, "ESR": 60}, "on the site, linked to the official result")
check(not todo(), "after the import it leaves the video list")
for body in ({"home": "JSK", "away": "ESR", "matchday": 13, "video": True}, {"home": "JSK", "away": "ESR", "matchday": 13}, {"home": "ESR", "away": "JSK", "matchday": 13}):
    r = analyst.post("/analytics/api/games", json=body, environ_overrides={"REMOTE_ADDR": "198.51.100.9"})
    check(r.status_code == 422, f"an analyst cannot start {body}: {r.status_code}")
r = analyst.post("/analytics/api/games", json={"home": "JSK", "away": "ESR", "matchday": 14}, environ_overrides={"REMOTE_ADDR": "198.51.100.9"})
check(r.status_code == 200, "another matchday of the same two teams is still open")

shutil.rmtree(DATA, ignore_errors=True)
if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("video analysis sheet checks passed")
