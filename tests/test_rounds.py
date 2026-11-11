"""Player of the round: the admin opens the vote of a matchday once every game is over; the players of the game are the candidates; one final vote per browser; winner by votes or crown."""
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
import mvp  # noqa: E402
import rounds  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
ADMIN = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
vid = lambda n: f"{n:032x}"
act = lambda **b: c.post("/admin/api/rounds", json=b, headers=ADMIN)
view = lambda v=1: c.get(f"/api/round?vid={vid(v)}").get_json()


def vote(pid, n=1, ip="203.0.113.5", ua=UA, md=11):
    return c.post("/api/round/vote", json={"round": md, "player": pid, "vid": vid(n)}, headers={"User-Agent": ua}, environ_overrides={"REMOTE_ADDR": ip})


# 1. only the admin; nothing to show before the vote is opened
check(c.get("/admin-rounds.js").status_code == 200, "the admin script is served")
check(c.get("/admin/api/rounds").status_code == 401 and c.post("/admin/api/rounds", json={"op": "open", "round": 11}).status_code == 401, "admin only")
check(view()["round"] is None and view()["history"] == [], "nothing opened: nothing shown")
check(c.get("/api/home").get_json()["round_vote"] is None, "the home page has no round card yet")

# 2. it opens only when every game of the matchday is over and there is a player of the game
av = {r["matchday"]: r for r in c.get("/admin/api/rounds", headers=ADMIN).get_json()["rounds"]}
check(av[11]["can_open"] and av[11]["state"] == "ready" and av[11]["results"] == av[11]["expected"] == 6 and av[11]["candidates"] >= 1, "J11: all results in, candidates: it can open")
s12 = rounds.status(12)
check(not s12["can_open"] and "0 of 6" in s12["reason"], f"J12 has no results yet: refused ({s12['reason']})")
r = act(op="open", round=12)
check(r.status_code == 422 and "results" in r.get_json()["error"], "the admin cannot open a matchday that is not over")
real = rounds.candidates
rounds.candidates = lambda md, d=None: []
check("no player of the game" in rounds.status(11)["reason"], "no player of the game: refused")
rounds.candidates = real
check(act(op="nope", round=11).status_code == 422 and act(op="open").status_code == 422 and act(op="close", round=11).status_code == 422, "unknown action, no matchday, never opened: refused")

# 3. opening freezes the ballot: the players of the game of J11, one per game
cands = rounds.candidates(11)
r = act(op="open", round=11, deadline="2099-01-01T12:00")
check(r.status_code == 200, f"opened: {r.get_json()}")
v = view()
check(v["round"] == 11 and v["open"] and v["winner"] is None and v["total_votes"] == 0 and v["history"] == [], "the open round is shown")
check({x["id"] for x in v["candidates"]} == {x["id"] for x in cands} and len(v["candidates"]) == len(cands), "the candidates are the players of the game")
check(all({"name", "team", "number", "pos", "pts", "reb", "ast", "game"} <= set(x) and {"opp", "score"} <= set(x["game"]) for x in v["candidates"]), "each candidate carries his game")
check(c.get("/api/home").get_json()["round_vote"]["round"] == 11, "the home page gets the round")
check(rounds.status(10)["reason"].startswith("The vote of J11 is still open"), "one vote open at a time")
a, b, third = [x["id"] for x in v["candidates"]][:3]

# 4. voting: one final vote per browser, candidates only, no bots, a cap per network
check(vote(a, n=1).status_code == 200, "a vote is counted")
check(vote(a, n=1).status_code == 409 and vote(b, n=1).status_code == 409, "a browser votes once: the second try, for anybody, is refused")
check(vote("nobody-0", n=2).status_code == 400, "only the ballot")
check(vote(a, n=3, ua="Googlebot/2.1").status_code == 400, "no crawlers")
check(c.post("/api/round/vote", json={"round": 11, "player": a, "vid": "short"}, headers={"User-Agent": UA}).status_code == 400, "bad browser code")
check(c.post("/api/round/vote", json={"round": "x", "player": a, "vid": vid(4)}, headers={"User-Agent": UA}).status_code == 400, "bad round")
check(vote(a, n=5, md=10).status_code == 403, "a round that is not open takes no vote")
for n in range(10, 17):
    vote(a, n=n, ip="198.51.100.7")
check(vote(a, n=17, ip="198.51.100.7").status_code == 200 and vote(a, n=18, ip="198.51.100.7").status_code == 429, "8 browsers per network, the 9th is refused")
for n in range(100, 104):
    vote(b, n=n, ip=f"192.0.2.{n}")
vote(third, n=200, ip="192.0.2.200")
v = view(1)
votes = {x["id"]: x["votes"] for x in v["candidates"]}
check(votes[a] == 9 and votes[b] == 4 and votes[third] == 1, f"counts {votes}")
check([x["id"] for x in v["candidates"]][:3] == [a, b, third] and abs(sum(x["vote_share"] for x in v["candidates"]) - 100) < 0.3, "most votes first, shares add up")
check(v["my_vote"] == a and view(999)["my_vote"] is None and v["winner"] is None, "my vote is mine only; no winner while the vote is open")

# 5. closing: the fans' favourite wins; the admin can crown somebody else, or take the crown back
check(act(op="close", round=11).status_code == 200 and vote(b, n=300, ip="192.0.2.250").status_code == 403, "closed: no more votes")
v = view()
check(v["open"] is False and v["winner"]["id"] == a, "closed: the player with most votes wins")
check(act(op="crown", round=11, winner="nobody-0").status_code == 422, "only the ballot can be crowned")
check(act(op="crown", round=11, winner=b).status_code == 200 and view()["winner"]["id"] == b, "crowned: the crown wins")
check(act(op="crown", round=11, winner=None).status_code == 200 and view()["winner"]["id"] == a, "crown removed: the fans decide again")
check(c.get("/api/home").get_json()["round_vote"]["winner"]["id"] == a, "the home page shows the winner after the vote")

# 6. re-open, add players of a game whose stats arrive later (nobody is ever removed), and the next round
check(act(op="open", round=11).status_code == 200 and vote(b, n=301, ip="192.0.2.251").status_code == 200, "re-opened: votes are kept and new ones count")
extra = dict(cands[0], id="zz-1", name="LATE ARRIVAL")
rounds.candidates = lambda md, d=None: [*real(md, d), extra] if md == 11 else real(md, d)
check(act(op="refresh", round=11).status_code == 200 and "zz-1" in [x["id"] for x in view()["candidates"]] and len(view()["candidates"]) == len(cands) + 1, "refresh adds the new player of the game")
rounds.candidates = lambda md, d=None: [x for x in real(md, d) if x["id"] != a] if md == 11 else real(md, d)
act(op="refresh", round=11)
check(a in rounds.load()["11"]["ballot"] and "zz-1" in rounds.load()["11"]["ballot"], "refresh never removes a player from the ballot")
rounds.candidates = real
act(op="close", round=11)
r = act(op="open", round=10, deadline="not a date")
check(r.status_code == 422 and "deadline" in r.get_json()["error"].lower(), "a deadline must be readable")
check(act(op="open", round=10, deadline="2000-01-01T00:00").status_code == 200 and vote(rounds.candidates(10)[0]["id"], n=400, md=10).status_code == 403, "a vote whose deadline has passed takes no vote")
cur = view()
check(cur["round"] == 11 and cur["open"] is False, "the round that just closed is still shown (the other one ran out in 2000)")
data = rounds.load()
data["11"]["closed_at"] = 1       # long ago
data["10"]["closed_at"] = 1
data["10"]["open"] = False
rounds._write(data)
old = view()
check(old["round"] is None and [h["round"] for h in old["history"]] == [11], "a round that ended long ago leaves the home page; its winner stays in the history")
check(c.get("/api/home").get_json()["round_vote"] is None, "no round card once it is old")

# 7. votes are final in the database itself
con = sqlite3.connect(mvp.DB_FILE)
for q in ("UPDATE round_votes SET pid='x'", "DELETE FROM round_votes"):
    try:
        con.execute(q)
        check(False, f"the database must refuse: {q}")
    except sqlite3.DatabaseError:
        pass
cols = [r[1] for r in con.execute("PRAGMA table_info(round_votes)")]
check(cols == ["round", "voter", "net", "pid", "ts"] and all(len(x[0]) == 24 for x in con.execute("SELECT voter FROM round_votes")), "only hashes are stored")
con.close()

print("rounds:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
