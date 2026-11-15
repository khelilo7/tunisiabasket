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
# the fixes that ship with the code are all consistent games named after their file
from validate import validate  # noqa: E402
for f in sorted((ROOT / "assets" / "game_fixes").glob("*.json")):
    g = json.loads(f.read_text())
    check(g["id"] == f.stem and validate(g) == [], f"{f.name} is a valid game with its own id: {validate(g)}")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("game fixes checks passed")
