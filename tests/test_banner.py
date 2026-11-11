"""The home banner: the games that are going to be played next; once played, their results stay one day (after the game date), then the next matchday and its predictions."""
import datetime
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import predict  # noqa: E402
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
D = datetime.date.fromisoformat
iso = lambda d: d.isoformat()


def game(home, away, played, hs=None, as_=None, game_date=None):
    return {"home": home, "away": away, "played": played, "home_score": hs, "away_score": as_, "time": None, "game_date": game_date, "featured": None, "key": f"x:{home}-{away}"}


def plan(*mds):
    return {"projected": False, "teams": {}, "matchdays": [{"matchday": n, "date": d, "games": gs} for n, d, gs in mds]}


day = D("2026-11-11")
p = plan((12, "2026-11-11", [game("CA", "ESG", True, 77, 65), game("DSG", "CSHS", True, 69, 55)]),
         (13, "2026-11-14", [game("CSS", "USM", False), game("ESG", "SN", False)]))
b = lambda today, **kw: stats.banner(p, D(today), **kw)

# 1. the games that are going to be played: still shown on their own day, as games to predict
nxt = plan((12, "2026-11-11", [game("CA", "ESG", False), game("DSG", "CSHS", False)]), (13, "2026-11-14", [game("CSS", "USM", False)]))
for today in ("2026-11-05", "2026-11-11"):
    r = stats.banner(nxt, D(today))
    check(r and r["matchday"] == 12 and r["mode"] == "next" and all(not g["played"] for g in r["games"]), f"{today}: the next games (J12) are shown")
# the day after, still without a result: nothing to show for J12, the banner moves on
check(stats.banner(nxt, D("2026-11-12"))["matchday"] == 13, "a game whose date has passed and that has no result is dropped")

# 2. played: the results stay on the game date and one day after, then the next matchday
for today, want in (("2026-11-11", 12), ("2026-11-12", 12), ("2026-11-13", 13), ("2026-11-14", 13)):
    r = b(today)
    check(r and r["matchday"] == want, f"{today}: J{want} expected, got {r and r['matchday']}")
check(b("2026-11-12")["mode"] == "results" and all(g["played"] and g["home_score"] is not None for g in b("2026-11-12")["games"]), "J12 is shown as results")
check(b("2026-11-13")["mode"] == "next" and all(not g["played"] for g in b("2026-11-13")["games"]), "then J13 is shown as games to predict")
check(b("2026-11-12", days=0)["matchday"] == 13 and b("2026-11-11", days=0)["matchday"] == 12, "the number of days is a setting")
check(stats.RESULTS_DAYS == 1, "results stay one day by default")

# 3. a matchday partly played: results and next games together; a game moved by the admin follows its own date
mix = plan((12, "2026-11-11", [game("CA", "ESG", True, 77, 65), game("DSG", "CSHS", False, game_date="2026-11-12")]))
r = stats.banner(mix, D("2026-11-12"))
check(r and r["mode"] == "mixed" and [g["played"] for g in r["games"]] == [True, False], "mixed matchday: one result, one game to come")
check(r["games"][1]["date"] == "2026-11-12", "the game's own date is used")
check(stats.banner(mix, D("2026-11-13")) is None, "everything over: nothing left")

# 4. a result links to the game's box score page when the site has one
real = next(g for g in stats.build()["games"] if g.get("matchday_no"))
a_, b_ = real["teams"]
box = plan((real["matchday_no"], iso(D("2026-11-11")), [game(a_["code"], b_["code"], True, a_["points"], b_["points"]), game("CA", "XXX", True, 60, 50)]))
r = stats.banner(box, day)
check(r["games"][0]["game_id"] == real["id"] and r["games"][1]["game_id"] is None, "game_id: the box score page, or None")

# 5. the API gives the banner of today and is never cached
c = app.app.test_client()
resp = c.get("/api/planning")
j = resp.get_json()
check("banner" in j and resp.headers.get("Cache-Control") == "no-store", "/api/planning carries the banner, uncached")
today = datetime.datetime.now(stats.TUNIS).date()
check(j["banner"] is None or (j["banner"]["games"] and all(g["date"] is None or D(g["date"]) >= today - datetime.timedelta(days=1) for g in j["banner"]["games"])), "nothing older than yesterday on the banner today")

# 6. predictions close at 12:00 (Tunisian time) on the first game day; the next day the next matchday opens
saved = stats.planning
stats.planning = lambda *a, **k: nxt
at = lambda s: datetime.datetime.fromisoformat(s).replace(tzinfo=predict.TUNIS)
try:
    r = predict._round(at("2026-11-11T11:59"))
    check(r and r["matchday"] == 12 and r["open"] is True, "11:59 on game day: still open")
    check(r["deadline_ts"] == int(at("2026-11-11T12:00").timestamp()), "the deadline is noon on the game day")
    r = predict._round(at("2026-11-11T12:00"))
    check(r["matchday"] == 12 and r["open"] is False, "12:00 on game day: closed (J12 is still the round: its games are on the banner without predictions)")
    check(predict._round(at("2026-11-11T23:30"))["open"] is False, "closed all evening")
    r = predict._round(at("2026-11-12T08:00"))
    check(r["matchday"] == 13 and r["open"] is True, "the next day J13 opens")
    check(predict._round(at("2026-11-05T09:00"))["open"] is True, "days before: open")
finally:
    stats.planning = saved

print("banner:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
