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
check([t["code"] for t in v["standings"]][:2] == ["CSK", "ESM"] and not any(t["final"] for t in v["standings"]), f"table order while the season is on (points, then point difference: ESM and ASM are level on 3 points, ESM has the better difference): {[t['code'] for t in v['standings']]}")
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
# the hour of a game: in the calendar (18:30 or 18h30, before or after "projected"), set later game by game, kept when the result comes, and refused when it is not an hour
r = post({"op": "fixtures", "text": "5, ESM, CSK, 2999-01-01, 18h30\n5, ASM, EOS, 2999-01-01, projected, 8:00"})
v = c.get("/api/nat1").get_json()
m5 = next(m for m in v["matchdays"] if m["matchday"] == 5)
tm = {g["home"]: g["time"] for g in m5["games"]}
check(r.status_code == 200 and tm == {"ESM": "18:30", "ASM": "08:00"} and all(g["projected"] for g in m5["games"] if g["home"] == "ASM"), f"hours in the calendar: {tm}")
check(post({"op": "fixtures", "text": "5, ESM, CSK, 2999-01-01, 25:99"}).status_code == 200 and next(g for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 5 for g in m["games"] if g["home"] == "ESM")["time"] is None, "a column that is not an hour is not taken for one")
check(post({"op": "time", "matchday": 5, "home": "ESM", "away": "CSK", "time": "7pm"}).status_code == 422, "an hour that is not hh:mm is refused")
check(post({"op": "time", "matchday": 5, "home": "ESM", "away": "EOS", "time": "19:00"}).status_code == 422, "the hour of a game that is not in the calendar is refused")
check(post({"op": "time", "matchday": 5, "home": "ESM", "away": "CSK", "time": "19h00", "date": "2999-01-02"}).status_code == 200, "an hour (and a new day) is set for a game")
g5 = next(g for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 5 for g in m["games"] if g["home"] == "ESM")
check(g5["time"] == "19:00" and g5["date"] == "2999-01-02", f"the game shows its new hour and day: {g5}")
check(post({"op": "time", "matchday": 5, "home": "ESM", "away": "CSK", "time": ""}).status_code == 200 and next(g for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 5 for g in m["games"] if g["home"] == "ESM")["time"] is None, "an empty hour removes it")
post({"op": "time", "matchday": 5, "home": "ASM", "away": "EOS", "time": "20:15"})
check(post({"op": "result", "matchday": 5, "home": "ASM", "away": "EOS", "home_score": 70, "away_score": 60}).status_code == 200
      and next(g for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 5 for g in m["games"] if g["home"] == "ASM")["time"] == "20:15", "the hour of the calendar stays when the result is typed")
post({"op": "remove_result", "matchday": 5, "home": "ASM", "away": "EOS"})
post({"op": "fixtures", "text": "5, ESM, CSK, 2999-01-01\n5, ASM, EOS, 2999-01-01, projected"})        # back to the calendar the tests below rely on
off = "date: 2026-11-15\nCSK, 4, 4, 0, +97, 8\nESM, 4, 3, 1, +10, 7\nASM, 4, 1, 3, -50, 5\nEOS, 4, 0, 4, -57, 4"
r = post({"op": "official", "text": off})
check(r.status_code == 200 and r.get_json()["official"]["published"] == "2026-11-15", f"the federation's table is saved: {r.get_json()}")
v = c.get("/api/nat1").get_json()
check([t["code"] for t in v["standings"]] == ["CSK", "ESM", "ASM", "EOS"] and v["standings"][0]["diff"] == 97 and v["standings"][0]["pf"] is None, "the federation's table IS the table (order and numbers as given, no invented points for / against)")
check(post({"op": "official", "text": "CSK, 4, 4, 0, 97, 9"}).status_code == 422 and post({"op": "official", "text": "CSK, 4, 3, 0, 97, 6"}).status_code == 422, "a table whose points or games do not add up is refused")
# a result typed after the federation's table moves the table on from it (the FTBB numbers stay the base): added, corrected, removed
order = lambda: [t["code"] for t in c.get("/api/nat1").get_json()["standings"]]
row = lambda code: next(t for t in c.get("/api/nat1").get_json()["standings"] if t["code"] == code)
check(c.get("/api/nat1").get_json()["official"]["since"] == 0, "nothing typed since the FTBB table")
r = post({"op": "result", "matchday": 5, "home": "ESM", "away": "CSK", "home_score": 70, "away_score": 60})
check(r.status_code == 200 and "table" in r.get_json()["message"], f"a result of the calendar is saved: {r.get_json()}")
v = c.get("/api/nat1").get_json()
st = {t["code"]: t for t in v["standings"]}
check((st["ESM"]["j"], st["ESM"]["w"], st["ESM"]["pts"], st["ESM"]["diff"]) == (5, 4, 9, 20) and (st["CSK"]["j"], st["CSK"]["l"], st["CSK"]["pts"], st["CSK"]["diff"]) == (5, 1, 9, 87),
      f"the new game is added to the FTBB rows: {st['ESM']} {st['CSK']}")
check([t["code"] for t in v["standings"]][:2] == ["CSK", "ESM"] and [t["rank"] for t in v["standings"]] == [1, 2, 3, 4], f"level on 9 points, season not over: no tie-break law (ESM won the game between them, it does not count yet): the point difference puts CSK first: {order()}")
check(v["official"]["since"] == 1 and st["ESM"]["pf"] is None, "the page says one result was typed since the FTBB table; still no invented points for / against")
check(next(g for m in v["matchdays"] if m["matchday"] == 5 for g in m["games"] if g["home"] == "ESM")["home_score"] == 70, "the game shows its score on the results page")
check(nat1.load()["results"][-1].get("date") == "2999-01-01" or any(x.get("date") == "2999-01-01" for x in nat1.load()["results"] if x["matchday"] == 5), "the result takes the calendar's day")
page = c.get("/nationale-1").get_data(as_text=True)
check(page.index("CS Korba") < page.index("ES Marsa"), "the page for crawlers carries the same order")
r = post({"op": "result", "matchday": 5, "home": "EOS", "away": "CSK", "home_score": 70, "away_score": 60})
check(r.status_code == 422 and "not a game of J5" in r.get_json()["error"], f"a game that is not in that matchday's calendar is refused: {r.get_json()}")
check(post({"op": "result", "matchday": 5, "home": "EOS", "away": "ASM", "home_score": 75, "away_score": 70}).status_code == 200, "home and away swapped (a venue change) is accepted")
check(post({"op": "result", "matchday": 5, "home": "ESM", "away": "CSK", "home_score": 60, "away_score": 70}).status_code == 200, "a result is edited")
check((row("CSK")["w"], row("CSK")["pts"], row("ESM")["pts"], row("EOS")["pts"], row("ASM")["j"]) == (5, 10, 8, 6, 5) and order()[0] == "CSK" and c.get("/api/nat1").get_json()["official"]["since"] == 2,
      f"an edited score replaces the old one in the table: {c.get('/api/nat1').get_json()['standings']}")
for h, a in (("ESM", "CSK"), ("EOS", "ASM")):
    check(post({"op": "remove_result", "matchday": 5, "home": h, "away": a}).status_code == 200, "a result is removed")
check(order() == ["CSK", "ESM", "ASM", "EOS"] and row("CSK")["diff"] == 97 and c.get("/api/nat1").get_json()["official"]["since"] == 0, f"both removed: the FTBB table again, in its order: {order()}")
post({"op": "result", "matchday": 1, "home": "ESM", "away": "EOS", "home_score": 85, "away_score": 71})
check(row("ESM")["diff"] == 15 and row("EOS")["diff"] == -62 and row("ESM")["j"] == 4, "a corrected score of a game the FTBB table counts corrects the difference, not the games played")
post({"op": "result", "matchday": 1, "home": "ESM", "away": "EOS", "home_score": 80, "away_score": 71})
check(row("ESM")["diff"] == 10 and c.get("/api/nat1").get_json()["official"]["since"] == 0, "set back: the FTBB numbers again")
# the same checks as a Pro A result
for body, why in (({"op": "result", "matchday": 5, "home": "ESM", "away": "CSK", "home_score": 251, "away_score": 60}, "a score above 250"),
                  ({"op": "result", "matchday": 5, "home": "ESM", "away": "CSK", "home_score": "", "away_score": 60}, "a missing score"),
                  ({"op": "result", "matchday": 5, "home": "ESM", "away": "CSK", "home_score": 60, "away_score": 60}, "a tie")):
    check(post(body).status_code == 422, f"refused: {why}")
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
# the admin: National One and the Cup are subsections of Games & scores; the image generator has a National One group with the final score of one game
adm = (Path(__file__).resolve().parent.parent / "static" / "admin.html").read_text()
img = (Path(__file__).resolve().parent.parent / "static" / "admin-nat1img.js").read_text()
check('id="gamesub"' in adm and 'data-sub="nat1"' in adm and 'data-sub="cup"' in adm and 'id="nat1box"' in adm and 'id="cupbox"' in adm and 'data-tab="nat1"' not in adm and 'data-tab="cup"' not in adm,
      "admin: National One and Cup live under Games & scores, not as tabs of their own")
check("K.extra.n1_game = { group: 'nat1'" in img and all(f"K.extra.{k} = {{ group: 'nat1'" in img for k in ("n1_results", "n1_table")) and "nat1:changed" in img, "admin images: a National One group with a final-score image, redrawn after a save")
# a FTBB table stored before it kept its basis (data of November 2026): it counts the results played on or before its date, the later ones move the table
import json  # noqa: E402
nat1.FILE.write_text(json.dumps({"season": "2026-2027", "teams": {"AAA": "Club A", "BBB": "Club B", "CCC": "Club C"},
                                 "results": [{"matchday": 1, "home": "AAA", "away": "BBB", "home_score": 70, "away_score": 60, "date": "2026-11-14"}],
                                 "official": {"published": "2026-11-15", "source": "FTBB", "rows": [{"code": "AAA", "j": 1, "w": 1, "l": 0, "diff": 10, "pts": 2}, {"code": "BBB", "j": 1, "w": 0, "l": 1, "diff": -10, "pts": 1}]}}))
check(order() == ["AAA", "BBB", "CCC"] and row("CCC")["j"] == 0, f"old FTBB table: the result before its date is not counted twice: {c.get('/api/nat1').get_json()['standings']}")
post({"op": "result", "matchday": 2, "home": "CCC", "away": "AAA", "home_score": 90, "away_score": 50, "date": "2026-11-21"})
check(order() == ["AAA", "CCC", "BBB"] and (row("AAA")["j"], row("AAA")["diff"], row("CCC")["pts"]) == (2, -30, 2) and "basis" in json.loads(nat1.FILE.read_text())["official"],
      f"old FTBB table: the later result moves the table, and the basis is now stored: {c.get('/api/nat1').get_json()['standings']}")
# the games of one matchday are not always played on the same day: each is "score missing" (or "to come") on its own day, the matchday shows both days
post({"op": "team", "code": "XA", "name": "Team A"}); post({"op": "team", "code": "XB", "name": "Team B"}); post({"op": "team", "code": "XC", "name": "Team C"}); post({"op": "team", "code": "XD", "name": "Team D"})
check(post({"op": "fixtures", "text": "40, XA, XB, 2020-01-04, 18:00\n40, XC, XD, 2999-01-05, 20:30"}).status_code == 200, "a matchday over two days is saved")
m40 = next(m for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 40)
gm = {g["home"]: g for g in m40["games"]}
check(gm["XA"]["missing"] and not gm["XC"]["missing"] and m40["missing"] == 1, f"only the game whose day has passed is missing its score: {m40}")
check(m40["date"] == "2020-01-04" and m40["date_end"] == "2999-01-05" and (gm["XA"]["time"], gm["XC"]["time"]) == ("18:00", "20:30"), "the matchday spans both days, each game keeps its own hour")
post({"op": "result", "matchday": 40, "home": "XA", "away": "XB", "home_score": 70, "away_score": 60})
gm = {g["home"]: g for g in next(m for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 40)["games"]}
check(not gm["XA"]["missing"] and gm["XA"]["date"] == "2020-01-04" and not gm["XC"]["missing"] and gm["XC"]["date"] == "2999-01-05", "a result keeps the day of its own game, the other game is still to come")
# a game typed in the calendar by mistake can be removed, unless it has a result
post({"op": "fixtures", "text": "41, XA, XC, 2999-02-01"})
check(post({"op": "remove_fixture", "matchday": 41, "home": "XC", "away": "XA"}).status_code == 200 and not [m for m in c.get("/api/nat1").get_json()["matchdays"] if m["matchday"] == 41], "a game typed by mistake is removed from the calendar (either order of the teams)")
check(post({"op": "remove_fixture", "matchday": 40, "home": "XA", "away": "XB"}).status_code == 422, "a game with a result is not removed from the calendar")
check(c.post("/admin/api/nat1", json={"op": "remove_fixture", "matchday": 41, "home": "XA", "away": "XC"}).status_code in (401, 403), "only the admin removes a calendar game")
print("nationale 1, about, menu:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
