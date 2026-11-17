"""Several sources for one game: every version sent is kept, the admin compares them and chooses what is published (one source, or a mix cell by cell); a chosen game is locked against later pushes."""
import copy
import json
import os
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
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda path, body: c.post("/admin/api/" + path, json=body, headers=H)


def player(num, name, pts, ast=0):
    return {"number": num, "name": name, "starter": True, "captain": False, "dnp": False, "min": 200.0, "fgm": pts // 2, "fga": pts // 2, "p2m": pts // 2, "p2a": pts // 2, "p3m": 0, "p3a": 0,
            "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0, "reb": 0, "ast": ast, "tov": 0, "stl": 0, "blk": 0, "pf": 0, "fd": 0, "pm": 0, "pts": pts}


def game(ast, tov=0, extra=False, source="a.pdf"):
    a = [player(2, "TEST ONE", 66, ast)] + ([{**player(7, "TEST EXTRA", 0), "min": 0.0}] if extra else [])
    a[0]["tov"] = tov
    return {"competition": "TEST", "date": "2026-09-30", "source": "pdf", "date_approx": False, "matchday_no": 2, "matchday": "J2", "source_file": source, "id": "up-src00001",
            "teams": [{"code": "USM", "name": "UNION SPORTIVE MONASTIRIENNE", "coach": "", "points": 66, "players": a}, {"code": "CSS", "name": "CLUB SPORTIF SFAXIEN", "coach": "", "points": 54, "players": [player(9, "TEST TWO", 54)]}]}


pub = lambda: json.loads((config.DATA_DIR / "games" / "up-src00001.json").read_text())
check(c.get("/admin/api/game-sources").status_code == 401, "sources are admin only")
check(post("game", {"game": game(3)}).status_code == 200 and pub()["teams"][0]["players"][0]["ast"] == 3, "first version published as always")
check(c.get("/admin/api/game-sources", headers=H).get_json()["games"] == [], "one source: nothing to compare")
r = post("game", {"game": game(5, source="b.csv")})
check(r.status_code == 200 and not r.get_json().get("kept") and pub()["teams"][0]["players"][0]["ast"] == 5, "not locked: the newest version is published, as before")
lst = c.get("/admin/api/game-sources", headers=H).get_json()["games"]
check(len(lst) == 1 and lst[0]["sources"] == 2 and lst[0]["diffs"] == 1 and not lst[0]["locked"], f"the earlier version was kept as a source: {lst}")
cmp_ = c.get("/admin/api/game-sources/up-src00001", headers=H).get_json()
check(cmp_["diffs"] == ["USM|2|ast"] and [s["label"] for s in cmp_["sources"]] == ["a.pdf", "b.csv"], f"one difference found, in the assists of #2: {cmp_['diffs']}")
check(cmp_["teams"][0]["players"][0]["stats"]["ast"] == {"s1": 3, "s2": 5}, "values per source")
# a mix: everything from the newest, but the assists of #2 from the first
r = post("game-sources/up-src00001/publish", {"base": "s2", "picks": {"USM|2|ast": "s1"}})
check(r.status_code == 200 and pub()["teams"][0]["players"][0]["ast"] == 3 and pub()["merged_from"] == ["s1", "s2"], f"mixed version published: {r.get_json()}")
check(c.get("/admin/api/game-sources/up-src00001", headers=H).get_json()["locked"] is True, "the choice locks the game")
# a later push only adds a source
r = post("game", {"game": game(9, tov=1, source="c.pdf")})
check(r.status_code == 200 and r.get_json().get("kept") is True and pub()["teams"][0]["players"][0]["ast"] == 3, f"locked: the push is only kept as a source: {r.get_json()}")
lst = c.get("/admin/api/game-sources", headers=H).get_json()["games"]
check(lst[0]["sources"] == 3 and lst[0]["unreviewed"] == 1, "flagged as a new source to review")
# the same content again does not add a source
post("game", {"game": game(9, tov=1, source="c.pdf")})
check(c.get("/admin/api/game-sources", headers=H).get_json()["games"][0]["sources"] == 3, "the same version twice is one source")
# a mix that breaks the checks is refused, nothing written
big = copy.deepcopy(game(3, source="g.pdf"))
big["teams"][0]["players"][0].update(pts=70, fgm=35, fga=35, p2m=35, p2a=35)
big["teams"][0]["points"] = 70                                  # consistent on its own
check(post("game", {"game": big}).status_code == 200, "a second consistent version")
post("game-sources/up-src00001/unlock", {})
sids = c.get("/admin/api/game-sources/up-src00001", headers=H).get_json()["sids"]
r = post("game-sources/up-src00001/publish", {"base": sids[-2], "picks": {"USM||points": sids[-1]}})
check(r.status_code == 422 and r.get_json().get("problems") and pub()["teams"][0]["players"][0]["pts"] == 66, f"a mix that fails the checks is refused, nothing written: {r.status_code}")
check(post("game-sources/up-src00001/publish", {"base": "s9"}).status_code == 422, "an unknown source is refused")
# a player on one sheet only: the row can be taken or left
post("game-sources/up-src00001/unlock", {})
post("game", {"game": game(3, extra=True, source="d.pdf")})
cmp_ = c.get("/admin/api/game-sources/up-src00001", headers=H).get_json()
check("USM|7|*" in cmp_["diffs"], "a player who is on one sheet only is a difference")
sid_extra = cmp_["sids"][-1]
r = post("game-sources/up-src00001/publish", {"base": sid_extra, "picks": {"USM|7|*": "s1"}})
check(r.status_code == 200 and [p["number"] for p in pub()["teams"][0]["players"]] == [2], f"the admin leaves the extra player out: {r.get_json()}")
# unlock: the next push is published again
post("game-sources/up-src00001/unlock", {})
r = post("game", {"game": game(11, source="e.pdf")})
check(not r.get_json().get("kept") and pub()["teams"][0]["players"][0]["ast"] == 11, "unlocked: published as before")
# two files for one game
other = game(3, source="f.pdf")
other["id"] = "up-src00002"
post("game", {"game": other})
dups = c.get("/admin/api/game-sources", headers=H).get_json()["duplicates"]
check(any(set(d["ids"]) == {"up-src00001", "up-src00002"} for d in dups), f"two files for the same game are found: {dups}")
r = post("game-sources/up-src00001/attach", {"from": "up-src00002"})
check(r.status_code == 200 and not (config.DATA_DIR / "games" / "up-src00002.json").exists() and (config.DATA_DIR / "games_replaced").exists(), f"attached: {r.get_json() and r.get_json().get('error')}")
check(post("game-sources/up-src00001/attach", {"from": "up-src00001"}).status_code == 422, "a game cannot be attached to itself")
check(c.get("/admin-sources.js").status_code == 200, "the tab's script is served")
print("game sources:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
