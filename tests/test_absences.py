"""Players marked as not playing (admin) are left out of the expected starting five (/api/lineups); nothing else about them changes and the note stays private."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import absences  # noqa: E402
import app  # noqa: E402
import auth  # noqa: E402
import lineups  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
get = lambda: c.get("/api/lineups?home=JSK&away=USM").get_json()

# 1. the expected five: five players per team, guards first, with what the banner shows
base = get()
for side in ("home", "away"):
    five = base[side]["five"]
    check(len(five) == 5, f"{side}: five players")
    check([lineups.POS_ORDER.get(p["pos"], 9) for p in five] == sorted(lineups.POS_ORDER.get(p["pos"], 9) for p in five), f"{side}: guards first")
    check(all(p["team"] == base[side]["code"] and {"id", "name", "number", "pos", "pts", "reb", "ast"} <= set(p) for p in five), f"{side}: what the page needs")
check(base["home"]["code"] == "JSK" and base["away"]["code"] == "USM", "home / away as asked")
check(c.get("/api/lineups?home=JSK&away=JSK").status_code == 404 and c.get("/api/lineups?home=../x&away=USM").status_code == 404 and c.get("/api/lineups").status_code == 404, "bad teams refused")

# 2. only the admin can read or change the list
check(c.get("/admin/api/absences").status_code == 401, "list: admin only")
check(c.post("/admin/api/absences", json={"id": base["home"]["five"][0]["id"], "absent": True}).status_code == 401, "change: admin only")
check(c.post("/admin/api/absences", json={"id": "nobody-0", "absent": True}, headers=H).status_code == 422, "unknown player refused")

# 3. marking a starter as absent leaves him out; the next player moves up, the others stay
before_players = json.dumps(stats.build()["players"], sort_keys=True, default=str)
out = base["home"]["five"][0]
r = c.post("/admin/api/absences", json={"id": out["id"], "absent": True, "note": "knee injury"}, headers=H)
check(r.status_code == 200 and out["id"] in r.get_json()["absences"], "marked as absent")
after = get()
ids0, ids1 = [p["id"] for p in base["home"]["five"]], [p["id"] for p in after["home"]["five"]]
check(out["id"] not in ids1 and len(ids1) == 5, "the absent player is not in the expected five, and the five is complete")
check(set(ids0) - {out["id"]} <= set(ids1), "the other four starters stay")
check([p["id"] for p in after["away"]["five"]] == [p["id"] for p in base["away"]["five"]], "the other team is unchanged")
check("knee" not in json.dumps(after) and "note" not in json.dumps(after), "the note is never public")
check(json.dumps(stats.build()["players"], sort_keys=True, default=str) == before_players, "his stats and profile are unchanged")
lst = c.get("/admin/api/absences", headers=H).get_json()["absences"]
check(lst.get(out["id"], {}).get("note") == "knee injury" and lst[out["id"]]["since"], "the admin sees the note and the date")
since = lst[out["id"]]["since"]
c.post("/admin/api/absences", json={"id": out["id"], "absent": True, "note": "still out"}, headers=H)
check(c.get("/admin/api/absences", headers=H).get_json()["absences"][out["id"]]["since"] == since, "marking again keeps the first date")

# 4. two absent players of the same team, then everyone back
second = after["home"]["five"][1]
c.post("/admin/api/absences", json={"id": second["id"], "absent": True}, headers=H)
two = [p["id"] for p in get()["home"]["five"]]
check(out["id"] not in two and second["id"] not in two and len(two) == 5, "two absent players, still five")
check(lineups.expected_five(stats.build(), "JSK", exclude={two[0]})[0]["id"] != two[0], "the poster tool's own exclusions stack on top")
for pid in (out["id"], second["id"]):
    r = c.post("/admin/api/absences", json={"id": pid, "absent": False}, headers=H)
check(r.status_code == 200 and absences.load() == {}, "everyone back")
check([p["id"] for p in get()["home"]["five"]] == ids0, "back to the original five")

print("absences:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
