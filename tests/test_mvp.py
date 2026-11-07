"""Phase MVP: race, fan vote (one per browser, network cap, closed voting, bots), winner, admin settings, no personal data stored."""
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
import mvp  # noqa: E402

auth.time.sleep = lambda s: None
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
ADMIN = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
vid = lambda n: f"{n:032x}"


def vote(pid, n=1, ip="203.0.113.5", ua=UA, phase=1):
    return c.post("/api/mvp/vote", json={"phase": phase, "player": pid, "vid": vid(n)}, headers={"User-Agent": ua}, environ_overrides={"REMOTE_ADDR": ip})


r = c.get("/api/mvp?phase=1").get_json()
cands = r["candidates"]
check(len(cands) >= 8, "the race needs candidates")
check([x["rank"] for x in cands] == list(range(1, len(cands) + 1)), "ranks are 1..n")
check(all(cands[i]["score"] >= cands[i + 1]["score"] for i in range(len(cands) - 1)), "candidates sorted by score")
check(r["complete"] and len(r["matchdays"]) == 11, "phase 1 is complete (J1-J11)")
check(all(len(x["series"]) == 11 for x in cands), "one race point per matchday")
check(cands[0]["score"] == 100 and r["weights"] == {"stats": 70, "fans": 30} and r["total_votes"] == 0 and not r["fans_count"], "no votes yet: score is the stats score")
check(all(x["gp"] >= x["need"] for x in cands), "candidates meet the 70% games rule")
check(r["winner"] is None and r["leader"]["id"] == "ca-24", "nobody crowned while fans can still vote; Abada leads on stats")
check(r["voting_open"] and r["deadline"] == "2026-11-11T12:00:00+01:00", f"deadline from the repo file: {r['deadline']}")
check(c.get("/api/mvp?phase=9").status_code == 404, "unknown phase")

a, b = cands[0]["id"], cands[1]["id"]
check(vote(a).status_code == 200, "a vote is accepted")
check(c.get(f"/api/mvp?phase=1&vid={vid(1)}").get_json()["my_vote"] == a, "my vote is remembered for my browser")
check(c.get("/api/mvp?phase=1&vid=" + vid(2)).get_json()["my_vote"] is None, "other browsers have no vote")
check(vote(b).status_code == 409, "a vote is final: no second vote, no change")
t = c.get("/api/mvp?phase=1").get_json()
check(t["total_votes"] == 1 and {x["id"]: x["votes"] for x in t["candidates"]}[a] == 1, "one vote counted once")
check(t["ballot"] == [x["id"] for x in cands[:3]], "the ballot is the top 3 by stats")
check(vote(cands[5]["id"], n=40).status_code == 400, "only the top 3 can be voted for")
check(vote("nobody-0").status_code == 400, "unknown player refused")
check(c.post("/api/mvp/vote", json={"phase": 1, "player": a, "vid": "short"}, headers={"User-Agent": UA}).status_code == 400, "bad browser code refused")
check(vote(a, n=3, ua="Googlebot/2.1").status_code == 400, "crawlers cannot vote")

# network cap: 8 browsers per network, the 9th is refused; another network is fine
for n in range(10, 17):
    vote(a, n=n, ip="198.51.100.7")
check(vote(a, n=17, ip="198.51.100.7").status_code == 200, "8th browser of one network still counts")
check(vote(a, n=18, ip="198.51.100.7").status_code == 429, "9th browser of one network is refused")
check(vote(a, n=17, ip="198.51.100.7").status_code == 409, "a known browser cannot vote again")
check(vote(a, n=19, ip="198.51.100.8").status_code == 200, "another network is fine")

# behind Caddy/Cloudflare everybody arrives from 127.0.0.1: the cap must use the visitor's own address
for n in range(600, 612):
    r = c.post("/api/mvp/vote", json={"phase": 1, "player": cands[2]["id"], "vid": vid(n)}, headers={"User-Agent": UA, "CF-Connecting-IP": f"203.0.113.{n % 200}"}, environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    check(r.status_code == 200, f"visitor {n} behind the proxy must not share one network cap ({r.status_code})")

# fans count once MIN_VOTES votes are in: the score then mixes both
for n in range(100, 100 + mvp.MIN_VOTES):
    vote(b, n=n, ip=f"192.0.2.{n % 250}")
t = c.get("/api/mvp?phase=1").get_json()
check(t["fans_count"], "fan weight switches on after MIN_VOTES")
top = {x["id"]: x for x in t["candidates"]}
check(top[b]["fan_score"] == 100 and 0 < top[a]["fan_score"] < 100, "fan score is scaled to the most-voted candidate")
check(abs(top[b]["score"] - (0.70 * top[b]["stats_score"] + 30)) < 0.11, "score = 70% stats + 30% fans")

# admin: needs login, can change winner / close voting
check(c.get("/admin/api/mvp").status_code == 401 and c.post("/admin/api/mvp", json={"phase": 1}).status_code == 401, "admin only")
check(c.post("/admin/api/mvp", json={"phase": 1, "winner": None, "voting_open": True, "deadline": "soon"}, headers=ADMIN).status_code == 400, "bad deadline refused")
check(c.post("/admin/api/mvp", json={"phase": 1, "winner": "nobody-0", "voting_open": True}, headers=ADMIN).status_code == 400, "winner must be a candidate")
check(c.post("/admin/api/mvp", json={"phase": 1, "winner": b, "voting_open": False, "note": "x"}, headers=ADMIN).status_code == 200, "admin saves")
t = c.get("/api/mvp?phase=1").get_json()
check(t["winner"]["id"] == b and not t["voting_open"] and t["note"] == "x", "live settings override the repo file")
check(vote(a, n=500, ip="192.0.2.250").status_code == 403, "closed voting refuses votes")
# the deadline closes voting by itself, then the best 70/30 score is the winner
c.post("/admin/api/mvp", json={"phase": 1, "winner": None, "voting_open": True, "deadline": "2020-01-01T12:00"}, headers=ADMIN)
t = c.get("/api/mvp?phase=1").get_json()
check(not t["voting_open"] and vote(a, n=501, ip="192.0.2.251").status_code == 403, "voting closes at the deadline")
check(t["winner"] and t["winner"]["id"] == t["candidates"][0]["id"], "after the deadline the best score wins")
c.post("/admin/api/mvp", json={"phase": 1, "winner": None, "voting_open": False}, headers=ADMIN)
t = c.get("/api/mvp?phase=1").get_json()
check(t["winner"] and t["winner"]["id"] == t["candidates"][0]["id"], "no crown + voting closed + phase complete: race leader wins")
check(c.get("/admin/api/mvp", headers=ADMIN).get_json()["phases"][0]["votes"]["total"] > 20, "admin sees vote totals")
ov = c.get("/api/overview").get_json()["phase_mvp"]
check(ov["winner"] and ov["runners"] and "log" not in ov["winner"], "home summary")

# pages
for p in ("/course-mvp", "/en/mvp-race"):
    r = c.get(p)
    check(r.status_code == 200 and b"<h1>" in r.data, f"{p} renders for crawlers")

# nothing personal on disk
con = sqlite3.connect(config.DATA_DIR / "votes.db")
dump = "".join(str(x) for x in con.execute("SELECT * FROM votes"))
check("203.0.113" not in dump and "198.51.100" not in dump and "iPhone" not in dump and vid(1) not in dump, "no address, browser string or raw browser code stored")
check(oct((config.DATA_DIR / "votes.db").stat().st_mode & 0o777) == "0o600", "votes file is private")

print("MVP tests:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
