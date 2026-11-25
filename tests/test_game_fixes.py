"""game_fixes.py: a correction that ships with the code is applied once to a game already on the site, keeps the old copy, never invents a game, and never overwrites a later admin edit."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
import game_fixes  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None


def player(n, pts):
    return {"number": n, "name": f"P{n}", "starter": False, "captain": False, "dnp": False, "min": 200.0 / 2, "fgm": pts // 2, "fga": pts // 2, "p2m": pts // 2, "p2a": pts // 2, "p3m": 0, "p3a": 0,
            "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0, "reb": 0, "ast": 0, "tov": 0, "stl": 0, "blk": 0, "pf": 0, "fd": 0, "pm": 0, "pts": pts}


def game(gid, a, b):
    return {"id": gid, "date": "2026-11-14", "teams": [{"code": "AAA", "name": "A", "points": a, "players": [player(1, a), player(2, 0)]}, {"code": "BBB", "name": "B", "points": b, "players": [player(1, b), player(2, 0)]}]}


data, fixes = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
(data / "games").mkdir()
(data / "games" / "g1.json").write_text(json.dumps(game("g1", 60, 50)))
(fixes / "g1.json").write_text(json.dumps(game("g1", 62, 50)))
(fixes / "gone.json").write_text(json.dumps(game("gone", 40, 30)))                       # a game this site does not have
(fixes / "bad.json").write_text(json.dumps({**game("bad", 40, 30), "teams": [{**game("bad", 40, 30)["teams"][0], "points": 99}, game("bad", 40, 30)["teams"][1]]}))
(data / "games" / "bad.json").write_text(json.dumps(game("bad", 40, 30)))

log = game_fixes.apply(fixes, data)
check(json.loads((data / "games" / "g1.json").read_text())["teams"][0]["points"] == 62, "the fix replaced the game")
old = list((data / "games_replaced").glob("g1-*.json"))
check(len(old) == 1 and json.loads(old[0].read_text())["teams"][0]["points"] == 60, "the previous version is kept")
check(not (data / "games" / "gone.json").exists(), "a game the site does not have is not created")
check(json.loads((data / "games" / "bad.json").read_text())["teams"][0]["points"] == 40 and any("bad.json: REFUSED" in x for x in log), "a fix that fails the checks is refused and the game stays")
# applied once: an admin edit afterwards stays, and a second start-up does nothing
(data / "games" / "g1.json").write_text(json.dumps(game("g1", 70, 50)))
check(game_fixes.apply(fixes, data) == [] or all("bad.json" in x for x in game_fixes.apply(fixes, data)), "nothing is applied twice")
check(json.loads((data / "games" / "g1.json").read_text())["teams"][0]["points"] == 70, "a later admin edit is not overwritten")
# a fix file whose content changes is applied again
(fixes / "g1.json").write_text(json.dumps(game("g1", 64, 50)))
game_fixes.apply(fixes, data)
check(json.loads((data / "games" / "g1.json").read_text())["teams"][0]["points"] == 64, "an edited fix file applies again")
# a patch changes a few numbers of the game as stored, with the same rules
pat, data2 = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
(data2 / "games").mkdir()
base = game("g2", 60, 50)
base["source"] = "ocr"
base["teams"][0]["players"][0].update(name="RAW NAME", p2m=2, p2a=4, p3m=0, p3a=0, ftm=0, fta=0, fgm=2, fga=4, pts=4)
base["teams"][0]["players"][1].update(pts=56, p2m=28, p2a=40, fgm=28, fga=40)
base["teams"][0]["points"] = 60
base["teams"][1]["players"][1].update(pts=0)
(data2 / "games" / "g2.json").write_text(json.dumps(base))
(pat / "ok.json").write_text(json.dumps({"game": "g2", "players": [{"team": "AAA", "vs": "BBB", "number": 1, "set": {"p2m": 1, "p3m": 1, "p3a": 2, "p2a": 3}}, {"team": "AAA", "number": 2, "set": {"p2m": 26, "p2a": 40, "p3m": 1, "p3a": 1, "ast": 4}}]}))
(pat / "bad.json").write_text(json.dumps({"game": "g2", "players": [{"team": "AAA", "number": 1, "set": {"p2m": 3}}]}))      # 2 more points: the team total no longer matches
(pat / "nobody.json").write_text(json.dumps({"game": "g2", "players": [{"team": "AAA", "number": 77, "set": {"ast": 1}}]}))
(pat / "gone.json").write_text(json.dumps({"game": "nope", "players": [{"team": "AAA", "number": 1, "set": {"ast": 1}}]}))
(pat / "pts.json").write_text(json.dumps({"game": "g2", "players": [{"team": "AAA", "number": 1, "set": {"pts": 9}}]}))      # points are never set, they follow from the shots
(pat / "wrongteam.json").write_text(json.dumps({"game": "g2", "players": [{"team": "XXX", "vs": "YYY", "number": 1, "set": {"ast": 1}}]}))
nofix = Path(tempfile.mkdtemp())
log = game_fixes.apply(nofix, data2, pat)
g2 = json.loads((data2 / "games" / "g2.json").read_text())
a1, a2 = g2["teams"][0]["players"]
check(a1["name"] == "RAW NAME" and g2["source"] == base.get("source") and g2["date"] == base["date"], "a patch keeps everything it does not name")
check(a1["pts"] == 5 and a2["pts"] == 55 and a1["fga"] == 5 and a1["fgm"] == 2 and a2["ast"] == 4, f"the patched lines are recomputed: {a1} {a2}")
check(any("patch:bad.json: REFUSED" in x for x in log), "a patch that breaks the team total is refused")
for n in ("nobody", "pts", "wrongteam"):
    check(any(f"patch:{n}.json: REFUSED" in x for x in log), f"patch {n} is refused")
check(any("patch:gone.json: skipped" in x for x in log), "a patch for a game the site does not have is skipped")
check(len(list((data2 / "games_replaced").glob("g2-*.json"))) == 1 and json.loads(next((data2 / "games_replaced").glob("g2-*.json")).read_text())["teams"][0]["players"][0]["pts"] == 4, "the game as it was is kept")
log = game_fixes.apply(nofix, data2, pat)
check(not any("patch:ok.json" in x for x in log) and json.loads((data2 / "games" / "g2.json").read_text())["teams"][0]["players"][0]["pts"] == 5, "a patch is applied once")
# the patches that ship with the code name a game, a team, a number and fields a patch may change
for f in sorted((ROOT / "assets" / "game_patches").glob("*.json")):
    d = json.loads(f.read_text())
    check(d["game"] == f.stem and d.get("why") and d["players"], f"{f.name}: a game named after the file, a reason and players")
    for e in d["players"]:
        check(set(e["set"]) <= game_fixes.FIELDS and isinstance(e["number"], int) and e["team"] and e["vs"], f"{f.name}: {e}")
# the fixes that ship with the code are all consistent games named after their file
from validate import validate  # noqa: E402
for f in sorted((ROOT / "assets" / "game_fixes").glob("*.json")):
    g = json.loads(f.read_text())
    check(g["id"] == f.stem and validate(g) == [], f"{f.name} is a valid game with its own id: {validate(g)}")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("game fixes checks passed")
