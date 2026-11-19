"""Nationale 1: teams and results typed by the admin, the table computed from them, the public page and API, the About page, and the menu entries."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import nat1  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda body: c.post("/admin/api/nat1", json=body, headers=H)

# 1. nothing yet: an honest empty page, no crash
check(c.get("/api/nat1").get_json()["standings"] == [], "no team yet: an empty table")
check(c.get("/nationale-1").status_code == 200 and c.get("/en/national-one").status_code == 200, "both addresses of the page exist")
check(all(c.get(u).status_code == 200 for u in ("/nationale-1/matchs", "/nationale-1/calendrier", "/en/national-one/games", "/en/national-one/calendar")), "the Games and Calendar tabs have their own addresses")
check(c.get("/nationale-1/nope").status_code == 404, "an unknown tab is a 404")
check(c.post("/admin/api/nat1", json={"op": "team", "code": "ESM", "name": "ES Marsa"}).status_code in (401, 403), "only the admin edits Nationale 1")

# 2. teams
for code, name in (("ESM", "ES Marsa"), ("EOS", "EO Sidi Bouzid"), ("ASM", "AS Menzah"), ("CSK", "CS Korba")):
    check(post({"op": "team", "code": code.lower(), "name": name}).status_code == 200, f"team {code} added (codes are upper-cased)")
check(post({"op": "team", "code": "x", "name": "Bad"}).status_code == 422 and post({"op": "team", "code": "OKK", "name": "A"}).status_code == 422, "a bad code or name is refused")

# 3. results: one by one and pasted, all or nothing
r = post({"op": "result", "matchday": 1, "home": "ESM", "away": "EOS", "home_score": 78, "away_score": 71, "date": "2026-10-04"})
check(r.status_code == 200 and r.get_json()["games"] == 1, "a result is saved")
bad = [({"op": "result", "matchday": 1, "home": "ESM", "away": "ESM", "home_score": 1, "away_score": 2}, "a team cannot play itself"),
       ({"op": "result", "matchday": 1, "home": "ESM", "away": "XXX", "home_score": 1, "away_score": 2}, "an unknown team"),
       ({"op": "result", "matchday": 1, "home": "ESM", "away": "ASM", "home_score": 70, "away_score": 70}, "a tie"),
       ({"op": "result", "matchday": 1, "home": "ESM", "away": "ASM", "home_score": 70, "away_score": 60}, "ESM twice in one matchday"),
       ({"op": "result", "matchday": 99, "home": "ASM", "away": "CSK", "home_score": 70, "away_score": 60}, "matchday out of range"),
       ({"op": "result", "matchday": 2, "home": "ASM", "away": "CSK", "home_score": 70, "away_score": 60, "date": "04/10/2026"}, "a badly written date")]
for body, why in bad:
    check(post(body).status_code == 422, f"refused: {why}")
r = post({"op": "paste", "text": "# list\n1, ASM, CSK, 66, 70\n2; ESM; ASM; 59; 61\nJ2\tCSK\tEOS\t80\t77"})
check(r.status_code == 200 and r.get_json()["games"] == 4, f"a pasted list is saved: {r.get_json()}")
r = post({"op": "paste", "text": "3, ESM, CSK, 70, 60\n3, ASM, ZZZ, 70, 60"})
check(r.status_code == 422 and "line 2" in r.get_json()["error"] and c.get("/api/nat1").get_json()["games"] == 4, "one bad line: nothing saved, the line is named")
r = post({"op": "result", "matchday": 1, "home": "ESM", "away": "EOS", "home_score": 80, "away_score": 71})
check(r.get_json()["games"] == 4, "the same pairing in the same matchday is replaced, not doubled")

# 4. the table and the public page
v = c.get("/api/nat1").get_json()
st = {t["code"]: t for t in v["standings"]}
check([t["code"] for t in v["standings"]][:2] == ["CSK", "ASM"], f"table order (the law: points, then the game between ASM and ESM, level on 3 points, although ESM has the better difference): {[t['code'] for t in v['standings']]}")
check(st["CSK"]["pts"] == 4 and st["CSK"]["w"] == 2 and st["EOS"]["pts"] == 2 and st["ESM"]["pf"] == 80 + 59 and st["ESM"]["diff"] == (80 + 59) - (71 + 61), "2 points a win, 1 a loss, points for and against")
check([m["matchday"] for m in v["matchdays"]] == [1, 2] and v["matchdays"][0]["games"][0]["home_name"] and all(m["played"] for m in v["matchdays"]), "matchdays in order, with names, played because they have scores")
check("<table" in c.get("/nationale-1").get_data(as_text=True) and "CS Korba" in c.get("/nationale-1").get_data(as_text=True), "the page carries the table for crawlers")
check(post({"op": "remove_team", "code": "ESM"}).status_code == 422, "a team with results cannot be removed")
check(post({"op": "remove_result", "matchday": 2, "home": "ESM", "away": "ASM"}).get_json()["games"] == 3, "a result is removed")
check(post({"op": "season", "season": "2026-2027"}).status_code == 200 and post({"op": "season", "season": "26"}).status_code == 422, "the season")
check(nat1.parse_lines("1,A,B,1,2")[0]["matchday"] == "1", "list parsing")

# 5. About page and menu
page = c.get("/a-propos").get_data(as_text=True)
check("gratuitement" in page and "<h1>À propos</h1>" in page, "the About page says it is free (French)")
check("for free" in c.get("/en/about").get_data(as_text=True), "the About page says it is free (English)")
home = c.get("/").get_data(as_text=True)
check('data-p="predict"' in home and "hot" in home.split('data-p="predict"')[1][:80], "predictions are back in the menu, marked hot")
check('href="/a-propos"' in home and 'href="/analytics"' in home and 'href="/admin"' in home, "the footer links About, Analytics and Admin")
check("/nationale-1" in c.get("/sitemap.xml").get_data(as_text=True) and "/a-propos" in c.get("/sitemap.xml").get_data(as_text=True), "both pages are in the sitemap")
# the calendar and the federation's own table
r = post({"op": "fixtures", "text": "1, ESM, EOS, 2026-10-04\n5, ESM, CSK, 2999-01-01\n5, ASM, EOS, 2999-01-01, projected"})
check(r.status_code == 200, f"calendar saved: {r.get_json()}")
v = c.get("/api/nat1").get_json()
m5 = next(m for m in v["matchdays"] if m["matchday"] == 5)
check(not m5["played"] and m5["games"][0]["home_score"] is None and not m5["projected"], "a future matchday is not played and its games have no score")
check(next(g for m in v["matchdays"] if m["matchday"] == 1 for g in m["games"] if g["home"] == "ESM")["home_score"] == 80, "a calendar game with a result shows the result")
check(post({"op": "fixtures", "text": "5, ESM, NOPE, 2999-01-01"}).status_code == 422, "a calendar line with an unknown team is refused")
off = "date: 2026-11-15\nCSK, 4, 4, 0, +97, 8\nESM, 4, 3, 1, +10, 7\nASM, 4, 1, 3, -50, 5\nEOS, 4, 0, 4, -57, 4"
r = post({"op": "official", "text": off})
check(r.status_code == 200 and r.get_json()["official"]["published"] == "2026-11-15", f"the federation's table is saved: {r.get_json()}")
v = c.get("/api/nat1").get_json()
check([t["code"] for t in v["standings"]] == ["CSK", "ESM", "ASM", "EOS"] and v["standings"][0]["diff"] == 97 and v["standings"][0]["pf"] is None, "the federation's table IS the table (order and numbers as given, no invented points for / against)")
check(post({"op": "official", "text": "CSK, 4, 4, 0, 97, 9"}).status_code == 422 and post({"op": "official", "text": "CSK, 4, 3, 0, 97, 6"}).status_code == 422, "a table whose points or games do not add up is refused")
check(post({"op": "official", "text": ""}).status_code == 200 and c.get("/api/nat1").get_json()["official"] is None, "an empty table removes it: the table is computed again")
# every club of the league has its badge (tools/build_team_logos.py), so the page never falls back to initials for the clubs we know
import tools.build_nat1_seed as _seed  # noqa: E402
missing = [code for code in _seed.TEAMS if not (Path(__file__).resolve().parent.parent / "static" / "img" / "teams" / f"{code}.png").exists()]
check(not missing, f"a badge for every National One club: missing {missing}")
# the play-off for the promotion: eight clubs seeded 1v8, 4v5, 2v7, 3v6, semi-finals, a one-game final; the two semi-final winners go up
check(c.get("/api/nat1").get_json()["playoff"] is None, "fewer than eight clubs: no play-off yet")
for i in range(1, 9):
    post({"op": "team", "code": f"PO{i}", "name": f"Club {i}"})
post({"op": "official", "text": "date: 2026-11-15\n" + "\n".join(f"PO{i}, 4, {5 - i if i < 5 else 0}, {i - 1 if i < 5 else 4}, {20 - i}, {2 * (5 - i if i < 5 else 0) + (i - 1 if i < 5 else 4)}" for i in range(1, 9))})
po = c.get("/api/nat1").get_json()["playoff"]
check(po is not None and [r["name"] for r in po["rounds"]] == ["Quarter-finals", "Semi-finals", "Championship final"], f"quarter-finals, semi-finals, final: {po and [r['name'] for r in po['rounds']]}")
qf = {s["id"]: s for s in po["rounds"][0]["series"]}
check([(qf[k]["a"]["code"], qf[k]["b"]["code"]) for k in ("qf1", "qf2", "qf3", "qf4")] == [("PO1", "PO8"), ("PO4", "PO5"), ("PO2", "PO7"), ("PO3", "PO6")], "1v8, 4v5, 2v7, 3v6")
check(all(s["best_of"] == 3 for s in qf.values()) and po["rounds"][2]["series"][0]["best_of"] == 1, "quarter-finals best of three, the final one game")
check(qf["qf1"]["a"]["provisional"] and not po["seeds_final"], "seeds are provisional while the calendar is not over")
check(post({"op": "playoff_games", "text": "GAME, qf9, PO1, 80, 70"}).status_code == 422 and post({"op": "playoff_games", "text": "GAME, qf1, PO1, 70, 70"}).status_code == 422, "an unknown series or equal scores are refused")
r = post({"op": "playoff_games", "text": "GAME, qf1, PO1, 80, 70, 2027-04-24\nGAME, qf1, PO1, 75, 70\nGAME, qf4, PO3, 60, 65\nGAME, qf4, PO3, 60, 65\nGAME, qf2, PO4, 70, 60\nGAME, qf2, PO4, 70, 60\nGAME, qf3, PO2, 70, 60\nGAME, qf3, PO2, 70, 60"})
check(r.status_code == 200, f"play-off games saved: {r.get_json()}")
po = c.get("/api/nat1").get_json()["playoff"]
sf = {s["id"]: s for s in po["rounds"][1]["series"]}
check(sf["sf1"]["a"].get("code") == "PO1" and sf["sf1"]["b"].get("code") == "PO4" and sf["sf2"]["a"].get("code") == "PO2" and sf["sf2"]["b"].get("code") == "PO6", "the winners meet in the semi-finals (1-8 v 4-5, 2-7 v 3-6)")
post({"op": "playoff_games", "text": "GAME, sf1, PO1, 80, 70\nGAME, sf1, PO1, 80, 70\nGAME, sf2, PO2, 80, 70\nGAME, sf2, PO2, 80, 70\nGAME, final, PO1, 90, 85"})
po = c.get("/api/nat1").get_json()["playoff"]
check(po["promoted"] == ["PO1", "PO2"] and po["champion"]["code"] == "PO1", f"two clubs go up, the one-game final gives the champion: {po['promoted']} {po['champion']}")
check(c.get("/nationale-1/playoff").status_code == 200 and c.get("/en/national-one/play-off").status_code == 200, "the play-off tab answers in French and in English")
check(c.get("/api/competitions").get_json()["nat1_playoff"] is False, "the National One play-off tab is hidden until the admin announces it")
check(post({"op": "playoff_announce", "on": True}).status_code == 200 and c.get("/api/competitions").get_json()["nat1_playoff"] is True, "announced: the tab shows")
check(post({"op": "playoff_clear"}).status_code == 200 and not any(x["games"] for rd in c.get("/api/nat1").get_json()["playoff"]["rounds"] for x in rd["series"]), "the play-off games can be removed")
print("nationale 1, about, menu:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
