"""Who scored, from the commentator (tools/commentary_match.py, tools/live_scorer.py, livescore.scorer): the names are found in Tunisian Arabic words;
only the reader's token can send a scorer; it goes on the right basket; the plays and the live points show it; the admin's fix is never overwritten;
the reader queues one job per basket it sends, never for a correction."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["LIVESCORE_TOKEN"] = "TEST-LIVE-4444-5555"
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
os.environ["PUSH"] = "0"
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tools"))
import app  # noqa: E402
import commentary_match as cm  # noqa: E402
import live_reader  # noqa: E402
import livescore  # noqa: E402
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None

# 1. names in the commentary
DSG = [{"id": "dsg-30", "number": 30, "name": "Oussema Chabbouh"}, {"id": "dsg-41", "number": 41, "name": "Bechir Mouin"},
       {"id": "dsg-10", "number": 10, "name": "Mohamed Aymen Rachdi"}, {"id": "dsg-10b", "number": 10, "name": "Youssef Jarboui", "gp": 3},
       {"id": "dsg-14", "number": 14, "name": "Abderrahmen Diop"}, {"id": "dsg-12", "number": 12, "name": "Mohamed Selmi"}]
words = lambda text, t0=0.0: [{"t": t0 + i * 0.4, "w": w} for i, w in enumerate(text.split())]
pick = lambda text, roster=DSG: cm.who_scored(words(text), roster, t_board=len(text.split()) * 0.4, t_from=0)
check(pick("استناها شبوح يتوقل فيها يحاول ينجح فيها شبوح")["number"] == 30, "Chabbouh (شبوح) next to ينجح")
check(pick("الكل الراجد يبشير معين اوبن شوت يكمل معين")["number"] == 41, "Mouin (معين) next to يكمل")
check(pick("والراجدي في لعبة ينجح فيها الراجدي")["number"] == 10, "Rachdi said Rajdi (الراجدي): one letter apart still matches")
check(pick("محمد أيمن الراجدي ينجح")["player"]["id"] == "dsg-10", "Aymen (أيمن) is Rachdi's middle name, not Mouin; two #10 in the season stay apart")
check(pick("عبد الرحمن اندوان يكمل فيها عبد الرحمن")["number"] == 14, "a two-word first name (عبد الرحمن)")
check(pick("السلمي يضيع الضربة شبوح يكمل")["number"] == 30, "a name next to a miss (يضيع) is not the scorer")
check(pick("الجمهور يشجع الفريق")["number"] is None, "no name heard: nobody")
r = pick("ينجح فيها شبوح ينجح شبوح")
check(cm.sure(r) and r["conf"] == 1.0, f"one name, called twice with ينجح: sure ({r})")
check(cm.lat_skeleton("Chabbouh") == cm.ar_skeleton("شبوح") == "Sbh", "the same skeleton in Latin and Arabic")

# 2. the server: token, the right basket, plays and points
c = app.app.test_client()
H = {"Authorization": "Bearer TEST-LIVE-4444-5555"}
ADMIN = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
teams = list(stats.load_official()["teams"])
A, B = teams[0], teams[1]
env = {"REMOTE_ADDR": "192.0.2.20"}
send = lambda b: c.post("/api/livescore", json={**b, "matchday": 30}, headers=H, environ_overrides=env)
scorer = lambda b, h=H: c.post("/api/livescore/scorer", json={"teams": [A, B], "matchday": 30, **b}, headers=h, environ_overrides=env)
send({"teams": [A, B], "score": [0, 0], "q": 1, "clock": "10:00"})
send({"teams": [A, B], "score": [2, 0], "q": 1, "clock": "09:30"})
send({"teams": [A, B], "score": [2, 3], "q": 1, "clock": "09:00"})
send({"teams": [A, B], "score": [3, 3], "q": 1, "clock": "08:40"})
P1 = {"id": "x-7", "number": 7, "name": "Test Shooter"}
check(scorer({"score": [2, 0], "team": A, "pts": 2, "player": P1, "conf": 0.9, "sure": True}, {}).status_code == 401, "a scorer needs the reader's token")
r = scorer({"score": [2, 0], "team": A, "pts": 2, "player": P1, "conf": 0.9, "sure": True})
check(r.status_code == 200 and r.get_json()["basket"]["name"] == "Test Shooter", f"scorer accepted: {r.get_json()}")
check(scorer({"score": [9, 9], "team": A, "pts": 2, "player": P1}).status_code == 404, "a score that never happened: no such basket")
check(scorer({"score": [2, 3], "team": "XYZ", "pts": 3, "player": P1}).status_code == 400, "a team not in the game is refused")
scorer({"score": [2, 3], "team": B, "pts": 3, "player": None, "conf": 0, "sure": False})                  # nobody named
scorer({"score": [3, 3], "team": A, "pts": 1, "player": P1, "conf": 0.55, "sure": False})
g = next(x for x in c.get("/api/live").get_json()["games"] if x["source"] == "scoreboard")
named = [(p["team"], p["name"], p["pts"]) for p in g["plays"]]
check(named == [(A, "Test Shooter", 1), (B, "", 3), (A, "Test Shooter", 2)], f"the plays carry the scorer's name: {named}")
check(g["scorers"]["by_team"][A] == [{"id": "x-7", "number": 7, "name": "Test Shooter", "pts": 3}] and g["scorers"]["unknown"][B] == 3,
      f"points per player, and the points nobody was named for: {g['scorers']}")

# 3. the admin: the list, a fix, and the reader never overwrites it
d = c.get("/admin/api/livescore/scorers", headers=ADMIN).get_json()
gm = d["games"][0]
check(gm["to_check"] == 2 and len(gm["baskets"]) == 3, f"3 baskets, 2 to check (nobody named, not sure): {gm['to_check']}")
idx = next(b["index"] for b in gm["baskets"] if b["team"] == B)
real = next(p for p in stats.build()["players"] if p["team"] == B)
r = c.post("/admin/api/livescore/scorer", json={"id": gm["id"], "index": idx, "team": B, "player": real["id"]}, headers=ADMIN)
check(r.status_code == 200 and r.get_json()["basket"]["admin"] and r.get_json()["basket"]["name"] == real["name"], f"the admin fixes a basket: {r.get_json()}")
scorer({"score": [2, 3], "team": B, "pts": 3, "player": P1, "conf": 0.99, "sure": True})
g = next(x for x in c.get("/api/live").get_json()["games"] if x["source"] == "scoreboard")
check(any(p["team"] == B and p["name"] == real["name"] for p in g["plays"]), "the reader cannot overwrite the admin's choice")
check(c.post("/admin/api/livescore/scorer", json={"id": gm["id"], "index": idx, "team": B, "player": "nobody-here"}, headers=ADMIN).status_code == 404, "an unknown player is refused")
check(c.get("/admin/api/livescore/scorers").status_code in (401, 403), "the admin list needs the admin")


# 4. the reader queues one job per basket it sends (never for a correction, a heartbeat or a final at the same score)
class Fake:
    def __init__(self):
        self.jobs = []

    def basket(self, teams, team, pts, score, matchday=None, label=""):
        self.jobs.append((team, pts, tuple(score)))


class Args:
    matchday, file, dry = None, None, True


a = Args()
a._scorers = Fake()
G = live_reader.Game(("ESS", "DSG"))
for reading in [(0, 0, 1, "10:00"), (0, 0, 1, "09:58"), (2, 0, 1, "09:30"), (2, 0, 1, "09:28"), (2, 3, 1, "09:00"), (2, 3, 1, "08:58")]:
    body = G.update(*reading)
    if body:
        live_reader.send(a, G, body, 0)
check(a._scorers.jobs == [("ESS", 2, (2, 0)), ("DSG", 3, (2, 3))], f"one job per basket: {a._scorers.jobs}")
G.sent, G.prev = (5, 3, 1), (2, 3, 1)
live_reader.send(a, G, {"teams": ["ESS", "DSG"], "score": [4, 3], "q": 1, "clock": None, "fix": True}, 0)
check(len(a._scorers.jobs) == 2, "a correction is not a basket")

if fails:
    print("FAILED:\n  " + "\n  ".join(fails))
    sys.exit(1)
print("live scorers: all checks passed")
