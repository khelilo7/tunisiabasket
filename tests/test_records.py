"""League records (records.py): sorted best-first, believable values, the games that set them say so, and the pages answer."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault("SITE_URL", "https://example.test")
import app  # noqa: E402
import records  # noqa: E402
import stats  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


d = records.all_records()
check("players" in stats.build(), "records and stats keep separate caches (a cached function named like another must not answer for it)")
for grp in ("player", "team", "season", "league"):
    check(d[grp], f"{grp} records exist")
    for r in d[grp]:
        vals = [x["value"] for x in r["top"]]
        check(vals == sorted(vals, reverse=True), f"{r['label']}: best first")
caps = {k: cap for k, _l, cap in records.PLAYER_STATS}
for r in d["player"]:
    check(all(0 < x["value"] <= caps[r["key"]] for x in r["top"]), f"{r['label']}: believable values")
    check(all(x["game_id"] and x["player"] and x["team"] and x["opp"] for x in r["top"]), f"{r['label']}: every line says who, for whom, against whom, and links the game")
titles = next(r for r in d["league"] if r["key"] == "titles")["top"]
check(titles and titles[0]["value"] >= 13, "most titles: the leader has at least 13")
check(sum(d["coverage"]["box_scores"].values()) == len(stats.build_all_games()), "coverage counts every box score")

# the game that holds the points record (and is not among the first games) says so on its page
games = stats.build_all_games()
order = sorted(games, key=lambda g: (g["date"], g["id"]))
pts = next(r for r in d["player"] if r["key"] == "pts")["top"]
holder = next((x for x in pts if x["game_id"] in {g["id"] for g in order[30:]}), None)
if holder and holder["value"] == pts[0]["value"]:
    got = {r["key"]: r for r in records.for_game(holder["game_id"])}
    check("pts" in got and got["pts"]["value"] == holder["value"], f"the record game {holder['game_id']} shows the points record")
check(records.for_game(order[0]["id"]) == [], "the first games set no record (nothing before them)")
check(records.for_game("no-such-game") == [], "unknown game: no record")

c = app.app.test_client()
r = c.get("/api/records")
check(r.status_code == 200 and r.json["player"], "/api/records")
check(c.get("/historique/records").status_code == 200 and c.get("/en/history/records").status_code == 200, "the records page renders in both languages")
check("records" in c.get(f"/api/games/{order[-1]['id']}").json, "a game's API says which records it set")
print("records:", "FAILED" if fails else "ok")
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
