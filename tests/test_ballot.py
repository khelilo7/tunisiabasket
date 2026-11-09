"""The ballot freezes at the first vote, changing it never touches a vote, a site that already has votes freezes on arrival, admin-only."""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import config  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
ADMIN = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
vid = lambda n: f"{n:032x}"
vote = lambda pid, n, ip: c.post("/api/mvp/vote", json={"phase": 1, "player": pid, "vid": vid(n)}, headers={"User-Agent": UA}, environ_overrides={"REMOTE_ADDR": ip})
get = lambda: c.get("/api/mvp?phase=1").get_json()
rows = lambda: sqlite3.connect(config.DATA_DIR / "votes.db").execute("SELECT * FROM votes ORDER BY voter").fetchall()
c.post("/admin/api/mvp", json={"phase": 1, "winner": None, "voting_open": True, "deadline": "2099-01-01T12:00"}, headers=ADMIN)

r = get()
b0, cands = r["ballot"], r["candidates"]
check(len(b0) == 3 and not r["ballot_frozen"], "no vote yet: the ballot follows the stats and is not frozen")
keep, drop = b0[0], b0[2]
check(vote(keep, 1, "203.0.113.1").status_code == 200, "first vote")
r = get()
check(r["ballot_frozen"] and r["ballot"] == b0, "the first vote froze the ballot exactly as it was shown")
check(vote(drop, 2, "203.0.113.2").status_code == 200 and vote(drop, 3, "203.0.113.3").status_code == 200, "votes for the player who will leave")
r = get()
check(r["ballot_ranked"] == [drop, keep, b0[1]] and sorted(r["ballot_ranked"]) == sorted(b0) and r["ballot"] == b0, "the three finalists are shown most votes first (2, 1, 0), the ballot itself keeps its order")
check(c.get("/api/home").get_json()["phase_mvp"]["ballot"][0]["id"] == drop, "the home card lists the finalist with the most votes first")
before = rows()

# the stats change under a frozen ballot: it does not move
check(get()["ballot"] == b0, "a frozen ballot stays")

# admin changes it: Lahyani-for-Jackson style
newcomer = next(x["id"] for x in sorted(cands, key=lambda x: x["rank"]) if x["id"] not in b0)
check(c.post("/admin/api/mvp/ballot", json={"phase": 1, "ballot": [b0[0], b0[1], newcomer]}).status_code == 401, "changing the ballot is admin only")
for bad in ([b0[0], b0[1]], [b0[0], b0[0], newcomer], [b0[0], b0[1], "nobody-0"], "x"):
    check(c.post("/admin/api/mvp/ballot", json={"phase": 1, "ballot": bad}, headers=ADMIN).status_code == 400, f"refused: {bad}")
r = c.post("/admin/api/mvp/ballot", json={"phase": 1, "ballot": [b0[0], b0[1], newcomer]}, headers=ADMIN)
check(r.status_code == 200, "admin changes the ballot")
t = get()
by = {x["id"]: x for x in t["candidates"]}
check(set(t["ballot"]) == {b0[0], b0[1], newcomer} and drop not in t["ballot"], "the new ballot is shown")
check(rows() == before, "every vote row is untouched by the change")
check(by[drop]["votes"] == 2 and by[newcomer]["votes"] == 0 and t["total_votes"] == 3, "the dropped player keeps his votes, the new one starts at zero")
check(by[drop]["vote_rank"] == 4 and sorted(by[i]["vote_rank"] for i in t["ballot"]) == [1, 2, 3], "ballot players head the list; the dropped player is 4th")
check(vote(drop, 4, "203.0.113.4").status_code == 400, "nobody can vote for the dropped player any more")
check(vote(newcomer, 2, "203.0.113.2").status_code == 409, "someone who already voted cannot vote again")
check(c.get(f"/api/mvp?phase=1&vid={vid(2)}").get_json()["my_vote"] == drop, "his vote is still remembered")
check(vote(newcomer, 5, "203.0.113.5").status_code == 200 and get()["candidates"][0] is not None, "new voters can vote for the newcomer")

# saving the other settings keeps the ballot frozen
c.post("/admin/api/mvp", json={"phase": 1, "winner": None, "voting_open": True, "deadline": "2099-02-02T12:00", "note": "n"}, headers=ADMIN)
check(set(get()["ballot"]) == {b0[0], b0[1], newcomer} and get()["ballot_frozen"], "saving other settings does not unfreeze")

# a site that already has votes but no frozen ballot (the day this code arrives) freezes on the first read, as shown
live = config.DATA_DIR / "mvp.json"
d = json.loads(live.read_text()); d["1"].pop("ballot"); live.write_text(json.dumps(d))
shown = get()
check(shown["ballot_frozen"] and set(json.loads(live.read_text())["1"]["ballot"]) == set(shown["ballot"]), "votes exist, no frozen ballot: it freezes on arrival")

# a frozen player stays on the ballot even if he would not qualify now
lowest = max(cands, key=lambda x: x["rank"])["id"]
c.post("/admin/api/mvp/ballot", json={"phase": 1, "ballot": [b0[0], b0[1], lowest]}, headers=ADMIN)
check(lowest in get()["ballot"], "an admin-chosen player is on the ballot")
check(c.get("/admin/api/mvp", headers=ADMIN).get_json()["phases"][0]["ballot_frozen"], "the admin view shows the freeze")

print("ballot:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
