"""A box score compiled from a broadcast video (video_sheet.py): read exactly, kept apart from official sheets, replaced by a real box score of the same game."""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app  # noqa: E402
import auth  # noqa: E402
import extractor  # noqa: E402
import stats  # noqa: E402
from video_sheet import is_video_sheet  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
PDF = ROOT / "tests" / "fixtures" / "video_ess_dsg_j3.pdf"

# 1. the PDF is recognised and read exactly; every arithmetic check of the site passes
check(is_video_sheet(PDF), "recognised as a video-compiled sheet")
game, problems = extractor.extract(str(PDF), filename=PDF.name)
check(problems == [], f"consistency checks pass: {problems}")
check(game["source"] == "video" and game["matchday_no"] == 3 and game["date_approx"] is True, "source video, matchday 3, date approximate (the sheet has none)")
ess, dsg = game["teams"]
check((ess["code"], ess["points"], dsg["code"], dsg["points"]) == ("ESS", 74, "DSG", 69), "teams and score")
check(len(ess["players"]) == 9 and len(dsg["players"]) == 9, "nine players each")
check(next(p for p in ess["players"] if p["number"] == 0)["name"] == "WISSEM KISSI", "jersey 00 reads as number 0")
check(all("_ef" not in p for t in game["teams"] for p in t["players"]), "private EF column removed")

# 2. what could not be given to a player is kept aside, and with it the sheet's own totals line adds up (sheet: ESS 55 FGA, 29 REB, 13 TO; DSG 54, 32, 15)
for t, fga, reb, tov in ((ess, 55, 29, 13), (dsg, 54, 32, 15)):
    s = lambda k: sum(p[k] for p in t["players"])
    na = t["not_attributed"]
    check(s("fga") + na["fga"] == fga, f"{t['code']}: attempts + unattributed misses = sheet total")
    check(s("reb") + na["team_reb"] == reb, f"{t['code']}: rebounds + team rebounds = sheet total")
    check(s("tov") + na["tov"] == tov, f"{t['code']}: turnovers + unattributed = sheet total")

# 3. stored like any game: on the site, linked to the official result, one more box score for each team, profiles built on (team, number)
before = stats.build()
box0 = {r["code"]: r["box"] for r in app.app.test_client().get("/api/overview").get_json()["standings"]}
(stats.GAMES_DIR).mkdir(parents=True, exist_ok=True)
game.update(id="video-j3-ess-dsg", date="2026-10-04", uploaded=True)
c = app.app.test_client()
r = c.post("/admin/api/game", json={"game": game}, headers={"X-Admin-Token": "TEST-TOKEN-0000-1111"})
check(r.status_code == 200, f"the admin accepts it: {r.status_code} {r.get_json()}")
d = stats.build()
check(len(d["games"]) == len(before["games"]) + 1, "one more game on the site")
box1 = {r["code"]: r["box"] for r in c.get("/api/overview").get_json()["standings"]}
check(box1["ESS"] == box0["ESS"] + 1 and box1["DSG"] == box0["DSG"] + 1, "box scores column: +1 for ESS and DSG only")
check(all(box1[k] == box0[k] for k in box1 if k not in ("ESS", "DSG")), "other teams unchanged")
v = c.get("/api/games/video-j3-ess-dsg").get_json()
check(v.get("source") == "video" and v.get("matchday") == "J3", "the match page says where it comes from")
harvey = next(p for p in d["players"] if p["team"] == "ESS" and p["number"] == 2)
check(any(row["game_id"] == "video-j3-ess-dsg" for row in harvey["log"]), "the player's game log has it")
check(sum(1 for t in v["teams"] for p in t["players"]) == 18, "18 player rows, no 'unknown player'")

# 4. a real box score of the same game replaces it, whichever file comes first; the other way round the real one is never replaced
real = copy.deepcopy(game)
real.update(source="text", date_approx=False)
for k in ("id", "uploaded"):
    real.pop(k, None)
for gid, rid in (("a-video", "z-real"), ("z-video", "a-real")):
    for f in stats.GAMES_DIR.glob("*.json"):
        f.unlink()
    vid = {**copy.deepcopy(game), "id": gid}
    rl = {**copy.deepcopy(real), "id": rid}
    (stats.GAMES_DIR / f"{gid}.json").write_text(json.dumps(vid))
    (stats.GAMES_DIR / f"{rid}.json").write_text(json.dumps(rl))
    ids = [g["id"] for g in stats.load_games()]
    check(ids == [rid], f"the real box score wins ({gid} vs {rid}): {ids}")

print("video sheet:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
