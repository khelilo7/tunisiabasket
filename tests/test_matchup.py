"""Calendar dates and the head-to-head preview behind the next-games banner."""
import datetime
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import stats  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
cal = stats.load_calendar()
WANT = {11: ("2026-11-04", 2), 12: ("2026-11-11", 2), 13: ("2026-11-14", 5), 14: ("2026-11-18", 2), 15: ("2026-11-21", 5), 16: ("2026-11-25", 2), 17: ("2026-11-28", 5),
        18: ("2026-12-11", 4), 19: ("2026-12-15", 1), 20: ("2026-12-23", 2), 21: ("2026-12-26", 5), 22: ("2026-12-30", 2)}   # weekday: Mon=0
for md, (day, wd) in WANT.items():
    check(cal.get(md) == day, f"J{md} should be {day}, got {cal.get(md)}")
    check(datetime.date.fromisoformat(day).weekday() == wd, f"J{md} {day} has the weekday the federation gave")

plan = c.get("/api/planning").get_json()
mds = {m["matchday"]: m for m in plan["matchdays"]}
check(mds[12]["date"] == "2026-11-11" and mds[22]["date"] == "2026-12-30" and len(mds[12]["games"]) == 6, "planning carries the dates and six games per matchday")
check(("CA", "ESG") in {(g["home"], g["away"]) for g in mds[12]["games"]}, "J12 has Club Africain - ES Goulette (matches the published fixture)")

m = c.get("/api/matchup?home=CA&away=ESG").get_json()
check(m["home"]["code"] == "CA" and m["away"]["code"] == "ESG" and m["home"]["ppg"] > 0, "team stats for both sides")
check(len(m["meetings"]) == 1 and m["meetings"][0]["matchday"] == 1, "phase 1 meeting listed")
check(m["next"] == {"matchday": 12, "date": "2026-11-11"}, f"next meeting: {m['next']}")
check(len(m["form"]["CA"]) == 5 and len(m["players"]["ESG"]) == 3, "form and key players")
check(c.get("/api/matchup?home=CA&away=CA").status_code == 404 and c.get("/api/matchup?home=ZZZ&away=CA").status_code == 404, "bad teams refused")
check(c.get("/api/team-stats").status_code == 200, "public team stats")
check(c.get("/").status_code == 200, "home renders")

print("matchup:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
