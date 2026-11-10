"""One-team games (assets/partial_games.json): a hand-kept sheet for ONE team must add its stats without harming anything else.
The sheet never becomes a box score; what it does not give stays unknown (None), never 0; every other number of the site is unchanged."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import mvp  # noqa: E402
import stats  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def without_sheets():
    """Context: the same site with no one-team game at all."""
    class _Ctx:
        def __enter__(self):
            self.saved, stats.PARTIAL_FILES = stats.PARTIAL_FILES, ()

        def __exit__(self, *a):
            stats.PARTIAL_FILES = self.saved
    return _Ctx()


# this test is about the complete one-team sheet of the shipped file (CA, J1); the one-player sheets have their own test (test_partial_estimates.py)
shipped = json.loads(stats.PARTIAL_FILES[0].read_text())["games"]
sheet = [g for g in shipped if g["id"] == "p-j1-esg-ca"]
check(len(sheet) == 1, "the shipped sheet file has the CA game")
pg = sheet[0]
_only = Path(tempfile.mkdtemp()) / "partial_games.json"
_only.write_text(json.dumps({"games": sheet}))
stats.PARTIAL_FILES = (_only,)

# 1. the sheet itself is arithmetically sound and adds up to the official score
for p in pg["players"]:
    who = f"#{p['number']} {p['name']}"
    p2m = p["fgm"] - p["p3m"]
    check(p["pts"] == 2 * p2m + 3 * p["p3m"] + p["ftm"], f"{who}: PTS != 2*2P + 3*3P + FT")
    check(0 <= p["p3m"] <= p["p3a"] <= p["fga"] and p["fgm"] <= p["fga"] and p["ftm"] <= p["fta"], f"{who}: made/attempted order")
d = stats.build()
off = next(r for r in stats.load_official()["results"] if r["matchday"] == pg["matchday"] and {r["home"], r["away"]} == {pg["home"], pg["away"]})
official = {off["home"]: off["home_score"], off["away"]: off["away_score"]}
check(sum(p["pts"] for p in pg["players"]) == official[pg["recorded"]], "the players add up to the official score of their team")

# 2. it has its own match page and is listed as a partial game; it is not a full box score of the site
check(len(d["partials"]) == len(sheet), "build() exposes the one-team game")
check(all(g["id"] != pg["id"] for g in d["games"]), "a one-team game never enters build()['games']")
c = app.app.test_client()
listed = [g for g in c.get("/api/games").get_json()["games"] if g["id"] == pg["id"]]
check(len(listed) == 1 and listed[0]["partial"] is True, "listed once in the games list, marked partial")
mv = listed[0]["mvp"] if listed else None
sheet_score = lambda p: p["pts"] + (p["oreb"] + p["dreb"]) + p["ast"] + p["stl"] + p["blk"] - (p["fga"] - p["fgm"]) - (p["fta"] - p["ftm"])
rec_players = [{"oreb": 0, "dreb": 0, **p} for p in pg["players"]]
best = max(rec_players, key=lambda p: (sheet_score(p), p["pts"]))
winner = official[pg["recorded"]] == max(official.values())
check((mv is None) == (not winner), "a game MVP only if the team on the sheet won")
check(mv is None or (mv["name"].split()[0] in best["name"] or best["name"].split()[-1] in mv["name"]) and mv["pir"] is None and mv["team"] == pg["recorded"],
      "game MVP = best of the winning team's sheet players (PIR without turnovers/fouls), and it carries no PIR")
ov = {r["code"]: r["box"] for r in c.get("/api/overview").get_json()["standings"]}
with without_sheets():
    ov0 = {r["code"]: r["box"] for r in c.get("/api/overview").get_json()["standings"]}
check(ov[pg["recorded"]] == ov0[pg["recorded"]] + 1 and all(ov[k] == ov0[k] for k in ov if k != pg["recorded"]), "box scores column: +1 for the team on the sheet only")
r = c.get("/api/games/" + pg["id"])
v = r.get_json() if r.status_code == 200 else {}
check(r.status_code == 200 and v.get("partial") is True, "its match page exists and says it is partial")
by = {t["code"]: t for t in v.get("teams", [])}
check(len(by.get(pg["recorded"], {}).get("players", [])) == len(pg["players"]), "the recorded team lists its players")
other = [t for t in v.get("teams", []) if t["code"] != pg["recorded"]]
check(len(other) == 1 and other[0]["players"] == [], "the other team has no players, not zeros")
check({t["code"]: t["points"] for t in v.get("teams", [])} == official, "official scores on the match page")
row0 = by[pg["recorded"]]["players"][0]
check(all(row0[k] is None for k in stats.PARTIAL_UNKNOWN), "minutes, turnovers, fouls, +/-, PIR and rating are unknown (None), not 0")
check(c.get("/api/games/nope").status_code == 404, "an unknown game is still a 404")
check(c.get("/match/" + pg["id"]).status_code == 200 and c.get("/en/game/" + pg["id"]).status_code == 200, "server-rendered match page")
tv = {x["matchday"]: x for x in stats.team_view(pg["recorded"])["results"]}
check(tv[pg["matchday"]]["game_id"] == pg["id"], "the team page links the result to the match page")

# 3. nothing else moves: standings, full games, team averages, ratings, every player who is not on the sheet
with without_sheets():
    base = stats.build()
    base_rows = mvp._race_data(1)[0]
    base_games = json.dumps(base["games"], sort_keys=True, default=str)
    base_stand = base["standings"]
    base_ts = stats.team_stats()
check(json.dumps(d["games"], sort_keys=True, default=str) == base_games, "full box scores unchanged")
check(d["standings"] == base_stand, "standings unchanged")
rows = mvp._race_data(1)[0]
check([r["id"] for r in rows] == [r["id"] for r in base_rows], "phase MVP race: same candidates, same order")
for r, b in zip(rows, base_rows):
    if r["id"] in {p["pid"] for p in by[pg["recorded"]]["players"]}:
        check(r["gp"] == b["gp"] + 1 and r["pir"] == b["pir"] and r["impact"] == b["impact"], f"MVP race {r['id']}: one more game, PIR and impact still from known games")
    else:
        check(r == b, f"MVP race {r['id']} unchanged")
ts = stats.team_stats()
for a, b in zip(ts["teams"], base_ts["teams"]):
    a, b = {k: v for k, v in a.items() if k != "top_scorer"}, {k: v for k, v in b.items() if k != "top_scorer"}
    check(a == b, f"team averages of {a['code']} unchanged")
A, B = {p["id"]: p for p in base["players"]}, {p["id"]: p for p in d["players"]}
check(set(A) == set(B), "same set of players")
listed = {p["pid"] for p in by[pg["recorded"]]["players"]}
check(listed <= set(B) and len(listed) == len(pg["players"]), "every sheet player is a known profile (no duplicate, no new player)")
for i in B:
    if i not in listed:
        check(json.dumps(A[i], sort_keys=True, default=str) == json.dumps(B[i], sort_keys=True, default=str), f"{i} (not on the sheet) is unchanged")
        continue
    # sheet player: the stats the sheet does not give are exactly what they were; the others include the new game
    for k in ("min", "tov", "pf", "fd", "pm", "pir", "impact", "rating", "total_min", "reb36", "ast36", "blk36", "stl36", "p3_share", "pos"):
        check(A[i][k] == B[i][k], f"{i}: {k} must not change (the sheet does not know it)")
    check(B[i]["mvp_games"] == A[i]["mvp_games"] + (1 if mv and mv["player_id"] == i else 0), f"{i}: game MVP count changes only for the sheet's MVP")
    check(B[i]["gp"] == A[i]["gp"] + 1 and B[i]["wins"] == A[i]["wins"] + (1 if official[pg["recorded"]] == max(official.values()) else 0), f"{i}: one more game, one more win")
    rows = B[i]["log"]
    sheet_row = [r for r in rows if r.get("partial")]
    check(len(sheet_row) == 1 and sheet_row[0]["min"] is None and sheet_row[0]["pir"] is None, f"{i}: one sheet row in the game log, unknown stats None")
    check(B[i]["pts"] == round(sum(r["pts"] for r in rows) / len(rows), 1), f"{i}: points average counts the sheet game")
    full = [r for r in rows if not r.get("partial")]
    check(B[i]["min"] == round(sum(r["min"] for r in full) / len(full), 1), f"{i}: minutes average ignores the sheet game")
    check(B[i]["tov"] == round(sum(r["tov"] for r in full) / len(full), 1), f"{i}: turnovers average ignores the sheet game")
    check(B[i]["qualified"] == A[i]["qualified"] or B[i]["gp"] >= B[i]["games_needed"], f"{i}: qualification only changes by games played")

# 4. a sheet that cannot be tied to an official result, or whose team is not in it, is ignored (never invented)
tmp = Path(tempfile.mkdtemp()) / "partial_games.json"
bad = [{**pg, "id": "x1", "matchday": 99}, {**pg, "id": "x2", "recorded": "USM"}, {**pg, "id": "x3", "date": None}]
tmp.write_text(json.dumps({"games": bad}))
saved = stats.PARTIAL_FILES
stats.PARTIAL_FILES = (tmp,)
check(stats.build()["partials"] == [], "games without an official result / with a wrong team / without a date are ignored")
lost = [{**pg, "id": "x4", "recorded": "ESG", "players": [{"number": 41, "name": "Somebody", "pts": 2, "fgm": 1, "fga": 2, "p3m": 0, "p3a": 0, "ftm": 0, "fta": 0, "oreb": 0, "dreb": 1, "ast": 0, "stl": 0, "blk": 0}]}]
tmp.write_text(json.dumps({"games": lost}))
got = stats.build()["partials"]
check(len(got) == 1 and got[0]["mvp"] is None, "a sheet of the LOSING team has no game MVP")
stats.PARTIAL_FILES = saved

# 5. a full box score of the same game, uploaded later, replaces the sheet (never counted twice)
real_games = stats.build_all_games()
fake = {"id": "full", "matchday_no": pg["matchday"], "teams": [{"code": pg["home"], "players": []}, {"code": pg["away"], "players": []}]}
check(stats.partial_games(real_games) != [] and stats.partial_games([*real_games, fake]) == [], "the real box score of the same game replaces the sheet")
check(stats.partial_game("nope") is None, "no such game")

print("partial games:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
