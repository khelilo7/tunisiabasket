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

print("bios:", "FAILED" if fails else f"ok ({n} profiles)")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
