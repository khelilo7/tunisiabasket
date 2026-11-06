"""Positions, lineups and the admin correction flow (isolated data folder)."""
import os
import sys
from pathlib import Path

os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
ADDR = {"REMOTE_ADDR": "198.51.100.77"}
P = stats.POSITIONS

# --- inferred positions and team lineups
d = stats.build()
check(all(p["pos"] in P and 1.0 <= p["pos_value"] <= 5.0 for p in d["players"]), "every player has a position in PG..C and a value 1-5")
for code in stats.load_official()["teams"]:
    lineup = stats.team_view(code)["lineup"]
    check(len(lineup) == 5, f"{code}: lineup has {len(lineup)} players")
    check([x["spot"] for x in lineup] == P, f"{code}: the five spots must be PG,SG,SF,PF,C once each, got {[x['spot'] for x in lineup]}")
    mins = sorted((p["total_min"] for p in d["players"] if p["team"] == code), reverse=True)
    check(sorted((x["total_min"] for x in lineup), reverse=True) == mins[:5], f"{code}: lineup must be the five most-played players")

# --- game lineups
games = c.get("/api/games").get_json()["games"]
checked = 0
for gm in games:
    g = c.get("/api/games/" + gm["id"]).get_json()
    for code, l in g["lineups"].items():
        checked += 1
        check(len(l["starters"]) == 5 and [x["spot"] for x in l["starters"]] == P, f"game {gm['id']} {code}: starters must fill the five spots")
        check(all(x["min"] <= 48 for x in l["starters"] + l["bench"]), "minutes out of range")
check(checked >= 90, f"expected lineups for ~96 team-games, got {checked}")

# --- the admin can correct a position
check(c.post("/admin/api/positions", json={"changes": {}}, environ_overrides=ADDR).status_code == 401, "anonymous cannot change positions")
check(c.get("/admin/api/positions", environ_overrides=ADDR).status_code == 401, "anonymous cannot read the positions editor")
check(c.post("/admin/api/login", json={"token": os.environ["ADMIN_TOKEN"]}, environ_overrides=ADDR).status_code == 200, "admin login")
rows = c.get("/admin/api/positions", environ_overrides=ADDR).get_json()
check(rows["positions"] == P and len(rows["players"]) == len(d["players"]), "positions editor lists every player")
star = max((r for r in rows["players"] if r["team"] == "CA"), key=lambda r: r["total_min"])
other = "C" if star["auto"] != "C" else "PG"
check(c.post("/admin/api/positions", json={"changes": {star["id"]: other}}, environ_overrides=ADDR).status_code == 200, "save a correction")
after = next(p for p in stats.build()["players"] if p["id"] == star["id"])
check(after["pos"] == other and after["pos_source"] == "manual" and after["auto_pos"] == star["auto"], "the correction wins, the guess is kept")
check([x["spot"] for x in stats.team_view("CA")["lineup"]] == P, "lineup still fills the five spots after a correction")
check(c.post("/admin/api/positions", json={"changes": {star["id"]: "XX"}}, environ_overrides=ADDR).status_code == 422, "bad position refused")
check(c.post("/admin/api/positions", json={"changes": {"nobody-1": "PG"}}, environ_overrides=ADDR).status_code == 422, "unknown player refused")
check(c.post("/admin/api/positions", json={"changes": {star["id"]: None}}, environ_overrides=ADDR).status_code == 200, "remove the correction")
check(next(p for p in stats.build()["players"] if p["id"] == star["id"])["pos_source"] == "auto", "back to automatic")

print("positions:", "FAILED" if fails else f"ok ({checked} game lineups checked)")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
