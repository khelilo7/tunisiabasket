"""Match predictions: one pick per game, final, split hidden until you picked that game (percentages only), undeletable, admin sees counts."""
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
import predict  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None

G = [{"key": f"2026-2027|12|{h}-{a}", "home": h, "away": a, "home_name": h, "away_name": a} for h, a in (("CA", "USM"), ("ESS", "JSK"), ("CSS", "SN"))]
ROUND = {"matchday": 12, "date": "2099-11-11", "deadline_ts": 4099000000, "open": True, "season": "2026-2027", "games": G}
predict._round = lambda: ROUND
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
vid = lambda n: f"{n:032x}"
view = lambda v: c.get(f"/api/predict?vid={vid(v)}").get_json()["round"]
pick = lambda v, g, s, ip="10.0.0.1": c.post("/api/predict/pick", json={"game": g, "side": s, "vid": vid(v)}, headers={"User-Agent": "Mozilla/5.0", "X-Forwarded-For": ip}, environ_overrides={"REMOTE_ADDR": ip})

# nothing is shown before picking: no split, no counts, anywhere in the response
r = view(1)
check(r["matchday"] == 12 and len(r["games"]) == 3 and all(g["my"] is None and "split" not in g for g in r["games"]), "before picking: games only, no split")
check("total" not in str(c.get("/api/predict?vid=" + vid(1)).data).lower().replace("total_", ""), "no totals exposed")
check(pick(1, G[0]["key"], "H").status_code == 200, "first pick accepted")
r = view(1)
check(r["games"][0]["my"] == "H" and r["games"][0]["split"] == {"H": 100, "A": 0}, f"after picking game 1 its split appears: {r['games'][0]}")
check(r["games"][1]["my"] is None and "split" not in r["games"][1], "the other games stay hidden until picked")
check(view(2)["games"][0].get("split") is None and view(2)["games"][0]["my"] is None, "someone else still sees nothing")
# one final pick per game
check(pick(1, G[0]["key"], "A").status_code == 409, "second pick on the same game refused (final)")
check(view(1)["games"][0]["my"] == "H", "the pick did not change")
# percentages
for n, s in ((2, "A"), (3, "A"), (4, "H")):
    check(pick(n, G[0]["key"], s, f"10.0.1.{n}").status_code == 200, f"voter {n}")
sp = view(1)["games"][0]["split"]
check(sp == {"H": 50, "A": 50}, f"split in percent: {sp}")
check(set(sp) == {"H", "A"} and all(isinstance(x, int) for x in sp.values()), "percentages only")
# validation
check(pick(5, "2026-2027|12|XX-YY", "H").status_code == 400, "unknown game refused")
check(pick(5, G[1]["key"], "X").status_code == 400, "bad side refused")
check(c.post("/api/predict/pick", json={"game": G[1]["key"], "side": "H", "vid": "nope"}, headers={"User-Agent": "Mozilla/5.0"}).status_code == 400, "bad browser id refused")
check(c.post("/api/predict/pick", json={"game": G[1]["key"], "side": "H", "vid": vid(6)}, headers={"User-Agent": "Googlebot/2.1"}).status_code == 400, "crawler refused")
# network cap
codes = [pick(100 + i, G[2]["key"], "H", "10.9.9.9").status_code for i in range(10)]
check(codes.count(200) == predict.MAX_PER_NETWORK and codes[-1] == 429, f"network cap: {codes}")
# closed after the deadline (the matchday date)
ROUND["open"] = False
check(pick(7, G[1]["key"], "H").status_code == 403, "closed once the matchday starts")
check(view(1)["games"][0]["split"] and view(7)["games"][1].get("split") is None, "after the deadline, still no split without a pick")
ROUND["open"] = True
# votes are final: the database refuses to change or delete them, picks and MVP votes alike
db = sqlite3.connect(mvp.DB_FILE)
db.execute("INSERT INTO votes VALUES (1, 'v', 'n', 'ca-24', 1)"); db.commit()
for sql in ("DELETE FROM picks", "UPDATE picks SET side='A'", "DELETE FROM votes", "UPDATE votes SET pid='x'"):
    try:
        db.execute(sql)
        check(False, f"{sql} should be refused")
    except sqlite3.DatabaseError:
        pass
check(db.execute("SELECT COUNT(*) FROM picks").fetchone()[0] == 12 and db.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 1, "all picks and votes still there")
db.close()
# admin: real counts, admin only
check(c.get("/admin/api/predictions").status_code == 401, "admin only")
a = c.get("/admin/api/predictions", headers=H).get_json()
check(a["round"]["games"][0]["home_picks"] == 2 and a["round"]["games"][0]["away_picks"] == 2 and a["total_picks"] == 12, f"admin sees counts: {a}")
# the page exists in both languages
check(c.get("/pronostics").status_code == 200 and c.get("/en/predictions").status_code == 200, "page served in French and English")

print("predict:", "FAILED" if fails else "ok")
for m_ in fails:
    print("  FAIL", m_)
sys.exit(1 if fails else 0)
