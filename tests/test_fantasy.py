"""Fantasy Pro A (fantasy.py): hidden unless FANTASY=1; squad rules, scoring, captain and chips, auto-subs, transfers, grades, ranking and leagues.
Also the app's /api/schedule and the API's cross-origin headers (the mobile app's web preview)."""
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="fantasy-test-")
os.environ.pop("FANTASY", None)
import app  # noqa: E402
import fantasy  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
check(c.get("/api/fantasy/config").status_code == 404 and c.post("/api/fantasy/team", json={}).status_code == 404, "hidden: every fantasy route is a 404 without FANTASY=1")

# scoring of one line: efficiency counts, both ways, no floor and no cap
line = {"min": 30, "pts": 20, "reb": 10, "ast": 5, "stl": 2, "blk": 1, "tov": 3, "p3m": 2, "fga": 15, "fgm": 8, "fta": 4, "ftm": 2, "pf": 2, "pm": 10}
want = 20 + 12 + 7.5 + 4 + 2 + 1 - 0.75 * 7 - 0.5 * 2 - 4.5 - 1 + 1 + 3
check(fantasy.fantasy_points(line) == round(want, 1), f"points: the formula and the double-double bonus ({fantasy.fantasy_points(line)} v {want})")
check(fantasy.fantasy_points({**line, "ast": 10}) == round(want + 7.5 + 5, 1), "points: triple-double bonus on top")
bad_day = {"min": 28, "pts": 4, "reb": 2, "ast": 1, "stl": 0, "blk": 0, "tov": 5, "p3m": 0, "fga": 12, "fgm": 2, "fta": 2, "ftm": 0, "pf": 4, "pm": -18}
check(fantasy.fantasy_points(bad_day) < 0, f"a long, inefficient game goes below zero ({fantasy.fantasy_points(bad_day)})")
check(sum(x["points"] for x in fantasy.breakdown(line)) == fantasy.fantasy_points(line) or abs(sum(x["points"] for x in fantasy.breakdown(line)) - fantasy.fantasy_points(line)) < 0.06, "the breakdown adds up to the points")
check(fantasy.fantasy_points({**line, "min": 0}) is None and fantasy.fantasy_points({**line, "dnp": True}) is None, "no minutes: did not play")
check(fantasy.grade(96, 100) == "A+" and fantasy.grade(50, 100) == "D", "grades")

os.environ["FANTASY"] = "1"
os.environ["FANTASY_TEST"] = "1"
pool = c.get("/api/fantasy/pool").json["players"]
P = {p["id"]: p for p in pool}
check(pool and all(4 <= p["price"] <= 15 and p["pos"] in "GFC" for p in pool), "pool: every player has a price and a position")


def pick(budget, skip=()):
    need, sq, clubs = {"G": 3, "F": 3, "C": 2}, [], {}
    for p in sorted(pool, key=lambda x: -x["avg"]):
        if p["id"] in skip or need[p["pos"]] == 0 or clubs.get(p["team"], 0) >= 3:
            continue
        if sum(P[x]["price"] for x in sq) + p["price"] + (sum(need.values()) - 1) * 4.5 > budget:
            continue
        sq.append(p["id"])
        need[p["pos"]] -= 1
        clubs[p["team"]] = clubs.get(p["team"], 0) + 1
    return sq


sq = pick(fantasy.BUDGET)
G = [x for x in sq if P[x]["pos"] == "G"]
F = [x for x in sq if P[x]["pos"] == "F"]
C = [x for x in sq if P[x]["pos"] == "C"]
st = [G[0], G[1], F[0], F[1], C[0]]
check(len(sq) == 8, "a legal squad can be built")

bad = c.post("/api/fantasy/team", json={"vid": "testdevice0001", "squad": sq, "starters": [G[0], G[1], G[2], F[0], F[1]], "captain": G[0], "md": 4})
check(bad.status_code == 400 and any("centre" in e for e in bad.json["errors"]), "starters need a guard, a forward and a centre")
bad = c.post("/api/fantasy/team", json={"vid": "testdevice0001", "squad": sq[:7], "starters": st, "captain": G[0], "md": 4})
check(bad.status_code == 400, "a squad is 8 players")
bad = c.post("/api/fantasy/team", json={"vid": "x", "squad": sq, "starters": st, "captain": G[0], "md": 4})
check(bad.status_code == 400, "a device id is required")
rich = sorted(pool, key=lambda p: -p["price"])
dear = [p["id"] for p in rich if p["pos"] == "G"][:3] + [p["id"] for p in rich if p["pos"] == "F"][:3] + [p["id"] for p in rich if p["pos"] == "C"][:2]
if sum(P[x]["price"] for x in dear) > fantasy.BUDGET and max(sum(1 for x in dear if P[x]["team"] == t) for t in {P[x]["team"] for x in dear}) <= 3:
    r = c.post("/api/fantasy/team", json={"vid": "testdevice0001", "squad": dear, "starters": dear[:2] + dear[3:5] + dear[6:7], "captain": dear[0], "md": 4})
    check(r.status_code == 400 and any("budget" in e for e in r.json["errors"]), "the budget is enforced")

ok = c.post("/api/fantasy/team", json={"vid": "testdevice0001", "name": "Tester", "team_name": "Test Five", "squad": sq, "starters": st, "captain": st[0], "vice": st[2], "md": 4})
check(ok.status_code == 200, f"a legal team is saved ({ok.json})")
ok = c.post("/api/fantasy/team", json={"vid": "testdevice0001", "squad": sq, "starters": st, "captain": st[0], "vice": st[2], "md": 6, "chip": "triple_captain"})
check(ok.status_code == 200, "a chip can be played")
again = c.post("/api/fantasy/team", json={"vid": "testdevice0001", "squad": sq, "starters": st, "captain": st[0], "vice": st[2], "md": 8, "chip": "triple_captain"})
check(again.status_code == 400, "a chip is played once a season")

me = c.get("/api/fantasy/me?vid=testdevice0001").json["entry"]
h = {x["md"]: x for x in me["history"] if not x.get("upcoming")}
check(4 in h and 5 in h, "the squad saved for matchday 4 plays 4 and the next ones")
check(h[6]["chip"] == "triple_captain" and "triple_captain" not in me["chips_left"], "the chip is spent")
for x in h.values():
    if not x.get("rows"):
        continue
    counted = round(sum(r["points"] for r in x["rows"]), 1)
    check(abs(counted - x["raw"]) < 0.11, f"J{x['md']}: the matchday total is the sum of the counted players ({counted} v {x['raw']})")
    cap = [r for r in x["rows"] if r["mult"] >= 2]
    check(len(cap) <= 1, f"J{x['md']}: one captain at most")
    if x["md"] == 6 and cap:
        check(cap[0]["mult"] == 3, "Triple Captain: x3")
    if x["best"]:
        check(x["raw"] <= x["best"] + 0.11 and x["grade"], f"J{x['md']}: never more than the best possible, and a grade")
check(abs(me["total"] - round(sum(x["points"] for x in h.values()), 1)) < 0.2, "the total is the sum of the matchdays")

lg = c.post("/api/fantasy/league", json={"vid": "testdevice0001", "action": "create", "name": "Friends"}).json
check(lg["ok"] and len(lg["code"]) == 6, "a private league has a 6-character code")
c.post("/api/fantasy/team", json={"vid": "testdevice0002", "name": "Other", "squad": sq, "starters": st, "captain": st[1], "md": 4})
check(c.post("/api/fantasy/league", json={"vid": "testdevice0002", "action": "join", "code": lg["code"]}).json["ok"], "joining a league with its code")
rows = c.get(f"/api/fantasy/ranking?league={lg['code']}").json["rows"]
check(len(rows) == 2 and rows[0]["rank"] == 1 and "vid" not in rows[0], "the league ranking lists its members, never their device ids")
check(c.get("/api/fantasy/ranking?league=ZZZZZZ").status_code == 404, "unknown league: 404")
check(c.get("/api/fantasy/dream/5").json["team"], "the team of a matchday")
pv = c.get(f"/api/fantasy/player/{sq[0]}").json
check(pv["games"] and pv["avg_breakdown"] and pv["real"]["pts"] >= 0, "a player's fantasy page: games, average breakdown, real averages")
g0 = next(x for x in pv["games"] if x["played"])
check(abs(sum(b["points"] for b in g0["breakdown"]) - g0["fp"]) < 0.06, "each game's breakdown adds up to its fantasy points")
check(c.get("/api/fantasy/player/nobody-1").status_code == 404, "unknown player: 404")
os.environ.pop("FANTASY")
os.environ.pop("FANTASY_TEST")

s = c.get("/api/schedule")
d = s.json
check(s.status_code == 200 and d["matchdays"] and d["current"], "/api/schedule: every matchday and the current one")
check(all(g["home"] and g["away"] for m in d["matchdays"] for g in m["games"]), "/api/schedule: every game has its two clubs")
check(len({(m["matchday"], g["home"], g["away"]) for m in d["matchdays"] for g in m["games"]}) == sum(len(m["games"]) for m in d["matchdays"]), "/api/schedule: no game twice")
check(s.headers.get("Access-Control-Allow-Origin") == "*" and "POST" not in s.headers.get("Access-Control-Allow-Methods", ""), "public API: readable from the app's web preview, GET only")
check("Access-Control-Allow-Origin" not in c.get("/").headers, "pages: no cross-origin header")

print("fantasy:", "FAILED" if fails else "ok")
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
