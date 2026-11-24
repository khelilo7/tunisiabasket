"""Live scores read from the broadcast (livescore.py, tools/live_reader.py): only the reader's token can send; the score never goes down unless it is a correction; the game shows on
/api/live in the Live pages' shape; quarters and the final are announced once; the reader's filters ignore a misread."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["LIVESCORE_TOKEN"] = "TEST-LIVE-4444-5555"
os.environ["PUSH"] = "0"
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tools"))
import app  # noqa: E402
import live_reader  # noqa: E402
import livescore  # noqa: E402
import notify  # noqa: E402
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"Authorization": "Bearer TEST-LIVE-4444-5555"}
ip = lambda a: {"REMOTE_ADDR": a}
teams = list(stats.load_official()["teams"])
A, B = teams[0], teams[1]
fx = livescore.fixture(A, B)
send = lambda body, **kw: c.post("/api/livescore", json=body, headers=H, environ_overrides=ip("192.0.2.10"), **kw)

# 1. only the reader's token
check(c.post("/api/livescore", json={"teams": [A, B], "score": [2, 0], "q": 1}, environ_overrides=ip("192.0.2.1")).status_code == 401, "no token: 401")
codes = [c.post("/api/livescore", json={}, headers={"Authorization": "Bearer WRONG-%d" % i}, environ_overrides=ip("192.0.2.2")).status_code for i in range(6)]
check(codes == [401] * 5 + [429], f"lockout after 5 wrong tokens: {codes}")
check(send({"teams": [A, "XYZ"], "score": [0, 0], "q": 1}).status_code == 400, "an unknown team is refused")

# 2. a game: the side shown by the broadcast does not matter, home and away come from the calendar
send({"teams": [B, A], "score": [0, 0], "q": 1, "clock": "10:00", "matchday": 30})
r = send({"teams": [B, A], "score": [0, 2], "q": 1, "clock": "09:12", "matchday": 30})
check(r.status_code == 200, f"first reading accepted: {r.get_json()}")
g = r.get_json()["game"]
home, away = g["home"], g["away"]
check(g["score"] == {B: 0, A: 2}, f"scores follow the team codes, not the side: {g}")
check(g["clock"] == 9 * 60 + 12 and g["q"] == 1, "clock and quarter")
send({"teams": [B, A], "score": [3, 2], "q": 1, "clock": "08:01", "matchday": 30})
check(send({"teams": [B, A], "score": [1, 2], "q": 1, "matchday": 30}).status_code == 400, "a lower score is refused")
check(send({"teams": [B, A], "score": [30, 2], "q": 1, "matchday": 30}).status_code == 400, "a jump of 27 points is refused")
r = send({"teams": [A, teams[2]], "score": [41, 38], "q": 3, "matchday": 31})
check(r.status_code == 200 and r.get_json()["game"]["score"][A] == 41, "a reader started mid-game: the first reading is accepted whatever the score")
send({"teams": [A, teams[2]], "score": [43, 38], "q": 3, "matchday": 31})
jg = next(x for x in c.get("/api/live").get_json()["games"] if x["home"] in (A, teams[2]) and x["away"] in (A, teams[2]))
check([p["pts"] for p in jg["plays"]] == [2] and jg["quarters"] is None, f"joined mid-game: the score so far is not a basket, and the score by quarter is unknown: {jg['plays']}")
check(send({"teams": [B, A], "score": [3, 4], "q": 2, "clock": "09:40", "matchday": 30}).status_code == 200, "second quarter")
r = send({"teams": [B, A], "score": [3, 3], "q": 2, "matchday": 30, "fix": True})
check(r.status_code == 200 and r.get_json()["game"]["score"][A] == 3, "a correction may lower the score")
send({"teams": [B, A], "score": [3, 3], "q": 1, "matchday": 30})
check(livescore._load(g["id"])["q"] == 2, "a misread quarter never goes back")

C2, D2 = teams[3], teams[4]                                                  # corrections, on a game of their own
for sc, fix in (([0, 0], False), ([10, 6], False), ([16, 12], False)):
    send({"teams": [C2, D2], "score": sc, "q": 1, "matchday": 32, **({"fix": True} if fix else {})})
check(send({"teams": [C2, D2], "score": [13, 12], "q": 1, "matchday": 32, "fix": True}).status_code == 200, "a 3-point correction is accepted")
check(send({"teams": [C2, D2], "score": [13, 4], "q": 1, "matchday": 32, "fix": True}).status_code == 400, "a correction of 8 points is a misread: refused")

# 3. /api/live: the Live pages' shape
live = c.get("/api/live").get_json()["games"]
lg = next((x for x in live if x["id"] == g["id"]), None)
check(lg is not None and lg["source"] == "scoreboard", "the game is on /api/live")
if lg:
    check(lg["teams"][B]["score"] == 3 and lg["teams"][A]["score"] == 3 and lg["teams"][A]["players"] == [], "scores, no players")
    check(lg["quarters"]["pts"][B][:2] == [3, 0] and lg["quarters"]["pts"][A][:2] == [2, 1], f"points per quarter: {lg['quarters']}")
    check(lg["clock"] == {"q": 2, "t": 9 * 60 + 40}, f"clock: {lg['clock']}")
    check([p["pts"] for p in lg["plays"] if p["pts"]][:3] == [2, 3, 2], f"score changes, newest first: {lg['plays']}")
    check(lg["flow"]["changes"] >= 1, f"lead changes counted: {lg['flow']}")

# 4. pushes: the end of the 1st quarter once, to the fans of the two clubs only; the final under the official result's key
subs = {"tok-fan": {"level": "team", "team": A, "results": True, "lang": "fr"}, "tok-all": {"level": "all", "results": True, "lang": "en"}, "tok-other": {"level": "team", "team": teams[5], "results": True}}
notify._write(notify.FILE, subs)
ev = livescore.events("2026-27")
k1 = f"live:{g['id']}|q1"
check(k1 in ev and ev[k1][0] == "quarter" and ev[k1][2]["fr"][0] == f"{home} {3 if home == B else 2} – {2 if home == B else 3} {away}", f"end of Q1 announced with the Q1 score: {ev.get(k1)}")
check({t for t, _ in notify._audience("quarter", (A, B))} == {"tok-fan"}, "a quarter goes to the fans of the two clubs only")
send({"teams": [B, A], "score": [70, 64], "q": 4, "clock": "00:00", "matchday": 30, "fix": True})
r = send({"teams": [B, A], "score": [70, 64], "q": 4, "clock": "00:00", "matchday": 30, "final": True})
check(r.get_json()["game"]["final"] is True, "final")
ev = livescore.events("2026-27")
fk = f"result:2026-27|30|{home}-{away}"
check(fk in ev and ev[fk][0] == "results", f"the final has the official result's key: {[k for k in ev if k.startswith('result')]}")
check(all(f"|q{q}" in " ".join(ev) for q in (1, 2, 3)) and f"live:{g['id']}|q4" not in ev, "quarters 1-3 announced, the 4th is the final")
check(send({"teams": [B, A], "score": [70, 64], "q": 4, "matchday": 30}).get_json()["game"]["final"] is True, "the same score after the final changes nothing")
check(send({"teams": [B, A], "score": [70, 66], "q": 4, "matchday": 30}).get_json()["game"]["final"] is False, "a new basket after a final called too early opens the game again")
send({"teams": [B, A], "score": [70, 66], "q": 4, "matchday": 30, "final": True})

# 5. the calendar picks the matchday when the reader does not give one (and no game between the two teams is on Live)
if fx:
    livescore.CURRENT, keep = 0, livescore.CURRENT
    r = send({"teams": [fx[2], fx[1]], "score": [0, 0], "q": 1})
    livescore.CURRENT = keep
    gg = r.get_json()["game"]
    check(gg["matchday"] == fx[0] and gg["home"] == fx[1], f"matchday and home side from the calendar: {gg} vs {fx}")

# 5b. the reader stopped: the game leaves the Live page at once, and comes back if it is read again
stop = lambda body, **kw: c.post("/api/livescore/stop", json=body, environ_overrides=ip("192.0.2.10"), **kw)
C3, D3 = teams[6], teams[7]
send({"teams": [C3, D3], "score": [20, 18], "q": 2, "matchday": 33})
live_ids = lambda: [x["id"] for x in c.get("/api/live").get_json()["games"]]
sid = livescore.game_id(33, *livescore._which(C3, D3, 33, stats.load_official())[1:])
check(sid in live_ids(), "the game is live")
check(stop({"teams": [C3, D3], "matchday": 33}).status_code == 401, "stop needs the token")
check(stop({"teams": [C3, D3], "matchday": 33}, headers=H).status_code == 200 and sid not in live_ids(), "stopped: off the Live page at once")
check(stop({"teams": [teams[8], teams[9]], "matchday": 33}, headers=H).status_code == 404, "stopping a game that was never read: 404")
send({"teams": [C3, D3], "score": [20, 18], "q": 2, "matchday": 33})
check(sid not in live_ids(), "the same picture read again after a stop: still off Live")
send({"teams": [C3, D3], "score": [22, 18], "q": 2, "matchday": 33})
check(sid in live_ids(), "read again after a stop, a basket later: live again")
r = send({"teams": [D3, C3], "score": [18, 24], "q": 2})
check(r.status_code == 200 and r.get_json()["game"]["id"] == sid, f"a reading without a matchday joins the game already live (once its final is in the calendar, a second game opened): {r.get_json()}")
check(stop({"id": sid}, headers=H).status_code == 200 and sid not in live_ids(), "removed by id (Remove a game in the app)")
send({"teams": [C3, D3], "score": [24, 18], "q": 2, "clock": "05:00", "matchday": 33})
send({"teams": [C3, D3], "score": [24, 18], "q": 2, "clock": "04:51", "matchday": 33})
check(sid in live_ids(), "a removed game whose clock runs again is live again (the reader was restarted during a timeout)")
send({"teams": [C3, D3], "score": [80, 70], "q": 4, "clock": "00:00", "matchday": 33, "fix": True})
send({"teams": [C3, D3], "score": [80, 70], "q": 4, "clock": "00:00", "matchday": 33, "final": True})
stop({"id": sid}, headers=H)
for clock in ("00:00", "00:02", "00:00"):                                     # the window still shows the end, the clock misread now and then
    send({"teams": [C3, D3], "score": [80, 70], "q": 4, "clock": clock, "matchday": 33})
check(sid not in live_ids(), "an ended game removed while its window still shows the final score stays off Live")
check(stop({"id": "../etc/passwd"}, headers=H).status_code == 404 and stop({"id": "sb-nothing"}, headers=H).status_code == 404, "a bad or unknown id: 404")

# 6. a stale game leaves the Live page; a final stays a while
now = livescore._load(g["id"])["updated"]
check(any(x["id"] == g["id"] for x in livescore.live_games(now=now + livescore.FINAL_KEEP - 60)), "a final stays on the Live page for a while")
check(not any(x["id"] == g["id"] for x in livescore.live_games(now=now + livescore.FINAL_KEEP + 60)), "then it leaves")

check([livescore._clock_secs(v) for v in ("01:09", "00.48", "45.3", "10:00")] == [69, 48, 45, 600], "clock formats, the colon read as a dot included")

# 7. the reader's filters
G = live_reader.Game(("ESS", "DSG"))
out = [G.update(*x) for x in [(0, 2, 1, "08:44"), (0, 2, 1, "08:42"), (9, 2, 1, "08:40"), (3, 2, 1, "08:38"), (3, 2, 1, "08:36"), (3, 1, 1, "08:34")]]
sent = [o["score"] for o in out if o]
check(sent == [[0, 2], [3, 2]], f"sent only after two captures agree, a +7 misread ignored, a single lower reading ignored: {sent}")
G = live_reader.Game(("ESS", "DSG"))
check([G.update(0, 0, 1, "10:00"), G.update(0, 0, 1, "10:00")][1]["score"] == [0, 0], "before tip-off, 0-0 is sent once")
G = live_reader.Game(("ESS", "DSG"))
G.update(80, 71, 4, "06:30"); G.update(80, 71, 4, "06:28"); G.update(80, 71, 4, "06:26")
check(all(G.update(82, 4, 4, "06:12") is None or G.sent[1] == 71 for _ in range(30)), "a misread score far below (74 read as 4) is never sent as a correction")
check([G.update(80, 70, 4, "06:00") for _ in range(15)][-1]["fix"] is True, "a 1-point drop seen for 30 s is a correction")
check(live_reader.parse({"home": "", "away": "9", "q": "Q1", "clock": "02:21"}) == (None, 9, 1, "02:21"), "an empty score box is read as unknown")
G = live_reader.Game(("ESS", "DSG"))
sent = [o["score"] for o in (G.update(*x) for x in [(None, 2, 1, "09:00"), (None, 2, 1, "08:58"), (5, 7, 1, "05:00"), (5, 7, 1, "04:58"), (None, 7, 1, "04:40"), (None, 7, 1, "04:38")]) if o]
check(sent == [[0, 2], [5, 7]], f"an empty box is 0 while the team has 0, then a glitch that keeps the score: {sent}")
check(live_reader.parse({"home": "28", "away": "32", "q": "2", "clock": "01:09"}) == (28, 32, 2, "01:09"), "a quarter read without its Q")
check(live_reader.parse({"home": "28", "away": "32", "q": "22", "clock": "01:09"})[2] == 2, "the Q read as a 2")
check([live_reader.parse({"home": "1", "away": "2", "q": "Q2", "clock": c})[3] for c in ("00:08.", "20:08", ".07", "45.3", "00.48")] == ["00:08", None, None, "45.3", "00.48"], "impossible clocks are dropped")
check(live_reader.parse({"home": "50", "away": "48", "q": "OT1", "clock": "04:00"})[2] == 5, "overtime is period 5")
G = live_reader.Game(("ESS", "DSG"))
sent = [o["score"] for o in (G.update(*x) for x in [(67, 69, 4, "00:09"), (67, 69, 4, "00:07"), (67, 69, 4, "00:04")]) if o]
check(sent == [[67, 69]], f"started mid-game: the score is sent once three captures agree: {sent}")
G.sent, G.last_seen = (60, 60, 4), G.last_seen - 60
check(G.update(70, 69, 4, "00:03") is None and G.update(70, 69, 4, "00:03") is None and G.update(70, 69, 4, "00:02")["score"] == [70, 69], "after a gap a big jump needs three captures")
G.sent = (67, 69, 4)
G.last_seen -= 120
f = G.gone()
check(f and f["final"] and f["score"] == [67, 69], "the broadcast cut away after the last seconds of Q4: final")

# 8. the second scoreboard layout (24 November 2026): a light clock panel, a dark bar with the codes, one blue panel with both scores: found by its colours, and not
# mistaken for the bar shown at half-time (a white strip with navy score boxes, or a dark bar with no clock panel)
import numpy as np  # noqa: E402


def bar_picture(clock_light=True, dark_bar=True):
    img = np.zeros((700, 1500, 3), np.uint8) + np.array([200, 160, 100], np.uint8)         # a court (light wood)
    x0, y0, w = 760, 560, 130
    if dark_bar:
        img[y0 - 4:y0 + 52, x0 - 400:x0 + 540] = (30, 30, 36)
    if clock_light:
        img[y0 - 4:y0 + 52, x0 - 383:x0 - 213] = (200, 200, 200)
    img[y0:y0 + 48, x0:x0 + w] = (60, 120, 170)                                           # the blue panel
    return img


boards = live_reader.find_boards(bar_picture())
check(len(boards) == 1 and boards[0][3] == "B" and abs(boards[0][0] - 760) <= 3 and abs(boards[0][2] - 1.0) < 0.05, f"the second layout is found: {boards}")
check(live_reader.find_boards(bar_picture(clock_light=False)) == [], "a bar with no clock panel (half-time) is not read")
check(live_reader.find_boards(bar_picture(dark_bar=False)) == [], "a light strip around the panel (half-time, white strip) is not read")
fb = live_reader.FIELDS_B
check(set(fb) == set(live_reader.FIELDS) and fb["clock"][0] < fb["t_left"][0] < fb["home"][0] < fb["away"][0] < fb["t_right"][0], "the second layout has the same fields, left to right")

if fails:
    print("FAILED:\n  " + "\n  ".join(fails))
    sys.exit(1)
print("livescore: all checks passed")
