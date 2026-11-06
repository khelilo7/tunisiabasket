"""Player profiles (assets/players_info.json): format, plausible values, and every id is a real player."""
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import stats  # noqa: E402

config.ensure_data()
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


raw = json.loads((config.ASSETS_DIR / "players_info.json").read_text())
players = {p["id"]: p for p in stats.build()["players"]}
n = 0
for pid, b in raw.items():
    if pid.startswith("_"):
        continue
    n += 1
    check(pid in players, f"{pid}: no such player in the data")
    check(set(b) <= {"height", "weight", "birth", "approx", "src"}, f"{pid}: unknown fields {set(b) - {'height', 'weight', 'birth', 'approx'}}")
    h = b.get("height")
    for v in (h if isinstance(h, list) else [h] if h else []):
        check(isinstance(v, int) and 150 <= v <= 240, f"{pid}: implausible height {v}")
    if isinstance(h, list):
        check(len(h) == 2 and h[0] < h[1], f"{pid}: height range must be [min, max]")
    if "weight" in b:
        check(isinstance(b["weight"], int) and 45 <= b["weight"] <= 180, f"{pid}: implausible weight")
    if "birth" in b:
        try:
            d = datetime.date.fromisoformat(b["birth"])
            check(1965 <= d.year <= 2010, f"{pid}: implausible birth year")
        except ValueError:
            check(False, f"{pid}: birth must be YYYY-MM-DD")
    check(set(b.get("approx", [])) <= {"height", "weight", "birth"}, f"{pid}: bad approx list")

# the API shows them
if "ca-24" in players:
    b = players["ca-24"]["bio"]
    check(b and b["height"] == 189 and b["birth"] == "1993-04-20", "ca-24 profile not attached")
check(all("bio" in p for p in players.values()), "every player must carry a bio key (None when unknown)")

# category leaders (home page): 8 categories, top 10 each, sorted best first, only players with enough games
L = stats.leaders(list(stats.build()["players"]))
check([c["key"] for c in L] == list(stats.LEADER_STATS), "leaders: categories")
for c in L:
    vals = [x["value"] for x in c["top"]]
    check(len(c["top"]) == 10 and vals == sorted(vals, reverse=True), f"leaders: {c['key']} must hold 10 players, best first")
    check(all(players[x["id"]]["qualified"] for x in c["top"]), f"leaders: {c['key']} has an unqualified player")
pts = max(p["pts"] for p in players.values() if p["qualified"])
check(L[0]["top"][0]["value"] == pts, "leaders: top scorer is not the highest points average")

# qualification: at least 70% of the games of the player's team(s) (NBA rule), so nobody below that can rank
import math  # noqa: E402
built = stats.build()
games = built["games"]
played = {r["code"]: r["j"] for r in built["standings"]}      # official games played (box scores may be missing)
for p in players.values():
    avail = sum(max(sum(1 for g in games for t in g["teams"] if t["code"] == c), played.get(c, 0)) for c in p["teams"])
    check(p["qualified"] == (p["gp"] >= max(1, math.ceil(0.7 * avail)) and p["min"] >= stats.MIN_MINUTES_FOR_RANKING), f"qualified flag wrong for {p['id']}")

print("bios:", "FAILED" if fails else f"ok ({n} profiles)")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
