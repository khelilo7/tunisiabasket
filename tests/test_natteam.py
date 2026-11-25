"""The Tunisian national team (natteam.py): the list that ships with the code, the admin's changes over it, the games and the next game, the statistics, the pages."""
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
import natteam  # noqa: E402

auth.time.sleep = lambda s: None
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda body: c.post("/admin/api/national-team", json=body, headers=H)
pub = lambda: c.get("/api/national-team").get_json()
league = {p["id"]: p for p in c.get("/api/players").get_json()["players"]}
ship = json.loads((config.ASSETS_DIR / "national_team.json").read_text())

# --- what ships with the code: every called-up player is a player of the league or a listed outsider, the stats are the ones of the qualifiers
for pid in ship["callup"]["players"]:
    check(pid in league or pid in ship["externals"], f"shipped call-up: {pid} is neither a league player nor an external")
check(len(ship["callup"]["players"]) == 15, "the shipped call-up has the 15 players of the qualifiers")
check(sum(1 for x in ship["callup"]["players"] if x not in league) == 1 and "yacine-toumi" in ship["externals"], "exactly one player is outside the league: Yacine Toumi")
rows = {r["pid"]: r for r in ship["stats"][0]["rows"]}
check(len(rows) == 15 and rows["ca-24"] == {"pid": "ca-24", "g": 7, "min": 33, "pts": 18.1, "reb": 4.3, "ast": 5.7}, "the pasted statistics are shipped")
check(rows["yacine-toumi"]["pts"] == 12.8 and rows["usm-11"]["pts"] == 1.9, "stats of the outsider and of the last player")
ids = {g["id"] for g in ship["games"]}
check(len(ids) == len(ship["games"]), "game ids are unique")
check({c_["id"] for c_ in ship["competitions"]} >= {g["competition"] for g in ship["games"]}, "every shipped game has a known competition")
check(all(g["tun"] != g["opp_score"] for g in ship["games"] if g["tun"] is not None), "no tie in a shipped game")
check(natteam.record("wcq27", natteam.load()) == {"w": 5, "l": 4, "pf": 645, "pa": 629}, "the record of the qualifiers adds up (5-4, 645-629)")

# --- public view
v = pub()
check([p["pid"] for p in v["callup"]["players"]] == ship["callup"]["players"], "the call-up is shown in the list's order")
ab = next(p for p in v["callup"]["players"] if p["pid"] == "ca-24")
check(ab["name"] == "Omar Abada" and ab["team"] == "CA" and ab["stats"][0]["pts"] == 18.1, "a league player carries his club and national team stats")
yt = next(p for p in v["callup"]["players"] if p["pid"] == "yacine-toumi")
check(yt["ext"] and yt["team"] is None and yt["stats"][0]["g"] == 4, "the outsider has no club of the league and his stats")
check(v["stats"][0]["rows"][0]["pid"] == "ca-24", "the stats block starts with the best scorer")
check(v["next"] is None or (not v["next"]["played"] and v["next"]["date"] >= natteam.today()), "the next game is one still to come")
check(v["history"] and all(h["en"] and h["fr"] and h["src"] for h in v["history"]), "every history fact has both languages and a source")
check(c.get("/api/national-team/called").get_json()["ids"] == ship["callup"]["players"], "the light list for the labels")
pl = c.get("/api/players/ca-24").get_json()
check(pl["national"]["called"] and pl["national"]["stats"][0]["g"] == 7, "the player page API carries the national team block")
check(not c.get("/api/players/ca-1").get_json()["national"]["called"], "a player who was not called up is not labelled")

# --- the pages
for url, word in (("/equipe-nationale", "Équipe nationale"), ("/en/national-team", "national basketball team"), ("/en/national-team/yacine-toumi", "Yacine Toumi")):
    r = c.get(url)
    check(r.status_code == 200 and word in r.get_data(as_text=True), f"{url} is a page")
check(c.get("/en/national-team/nobody").status_code == 404, "an unknown outsider is a 404")
check("/en/national-team" in c.get("/sitemap.xml").get_data(as_text=True) and "yacine-toumi" in c.get("/sitemap.xml").get_data(as_text=True), "the sitemap lists the page and the outsider")
check("equipe-nationale" in c.get("/").get_data(as_text=True), "the footer links to the page")

# --- admin only
check(c.get("/admin/api/national-team").status_code == 401 and c.post("/admin/api/national-team", json={"op": "callup", "ids": []}).status_code == 401, "admin only")
check(c.get("/admin/api/national-team", headers=H).get_json()["players"], "the admin tab loads the players to choose from")

# --- the list: the admin's list replaces the shipped one
check(post({"op": "callup", "ids": ["ca-24", "nobody-9"]}).status_code == 422, "an unknown player is refused")
check(post({"op": "callup", "ids": ["ca-24", "ca-24"]}).status_code == 422, "a player twice is refused")
r = post({"op": "callup", "ids": ["usm-23", "ca-24", "yacine-toumi"], "label": "February window", "label_fr": "Fenêtre de février", "date": "2027-02-20"})
check(r.status_code == 200, f"list saved: {r.get_json()}")
v = pub()
check([p["pid"] for p in v["callup"]["players"]] == ["usm-23", "ca-24", "yacine-toumi"] and v["callup"]["label"] == "February window", "the admin's list wins, in his order")
check(c.get("/api/national-team/called").get_json()["ids"] == ["usm-23", "ca-24", "yacine-toumi"], "the labels follow the new list")
check(not c.get("/api/players/jsk-7").get_json()["national"]["called"], "somebody dropped from the list loses his label")
check(post({"op": "callup_reset"}).status_code == 200 and len(pub()["callup"]["players"]) == 15, "back to the shipped list")

# --- matching typed names
m = post({"op": "callup_names", "text": "Omar Abada\nFiras Lahiani\nOussama Marnaoui\nYacine Toumi\nSomebody Unknown"}).get_json()["matches"]
by = {x["input"]: x for x in m}
check(by["Omar Abada"]["pid"] == "ca-24" and not by["Omar Abada"]["uncertain"], "an exact name is sure")
check(by["Firas Lahiani"]["pid"] == "usm-23" and by["Firas Lahiani"]["uncertain"], "Lahiani is matched to Lahyani but marked to check")
check(by["Oussama Marnaoui"]["pid"] == "jsk-7", "Oussama / Oussema")
check(by["Yacine Toumi"]["pid"] == "yacine-toumi" and by["Yacine Toumi"]["ext"], "the outsider is found by his name")
check(by["Somebody Unknown"]["pid"] is None and by["Somebody Unknown"]["uncertain"], "no match: nothing is guessed")
check(natteam.similarity("Yasin Toumi", "Yacine Toumi") >= 0.9, "Yasin / Yacine")

# --- players outside the league
r = post({"op": "external", "name": "Karim Ben Salah", "birth": "1999-03-04", "height": 198, "position": "SF", "club": "Some Club", "nationality": "TN, FR", "note_en": "Plays in France."})
check(r.status_code == 200 and r.get_json()["key"] == "karim-ben-salah", "an outsider is created")
check(c.get("/en/national-team/karim-ben-salah").status_code == 200, "he has a page")
check(post({"op": "external", "name": ""}).status_code == 422 and post({"op": "external", "name": "X Y", "nationality": "ZZ"}).status_code == 422 and post({"op": "external", "name": "X Y", "height": 300}).status_code == 422, "bad values refused")
check(post({"op": "callup", "ids": ["ca-24", "karim-ben-salah"]}).status_code == 200 and pub()["callup"]["players"][1]["club"] == "Some Club", "he can be called up")
check(post({"op": "external", "name": "Yacine Toumi", "key": "yacine-toumi", "club": "Paris Basket"}).status_code == 200 and pub()["externals"]["yacine-toumi"]["career"], "editing a shipped outsider keeps his career lines")
check(post({"op": "external_delete", "key": "karim-ben-salah"}).status_code == 200 and all(p["pid"] != "karim-ben-salah" for p in pub()["callup"]["players"]), "deleting him takes him out of the list")
check(c.get("/en/national-team/karim-ben-salah").status_code == 404, "and his page is gone")
post({"op": "callup_reset"})

# --- competitions
r = post({"op": "competition", "en": "AfroBasket 2029 qualifiers"})
cid = r.get_json()["id"]
check(r.status_code == 200 and any(x["id"] == cid for x in pub()["competitions"]), "a competition is added")
check(post({"op": "competition", "en": "AfroBasket 2029 qualifiers"}).status_code == 422, "the same name twice is refused")
check(post({"op": "competition_delete", "id": "wcq27"}).status_code == 422, "a shipped competition cannot be removed")

# --- games
g = {"op": "game", "competition": cid, "date": "2029-02-20", "opp_name": "nigéria", "site": "away", "venue": "Lagos", "tun": 80, "opp_score": 75}
r = post(g)
gid = r.get_json()["id"]
check(r.status_code == 200, f"game saved: {r.get_json()}")
gm = next(x for x in pub()["games"] if x["id"] == gid)
check(gm["opp"] == "NG" and gm["opp_name_fr"] == "Nigéria" and gm["won"] and gm["played"], "the opponent typed as a name becomes the country")
check(pub()["games"][0]["id"] == gid, "the newest game is first")
check(post({**g, "opp_score": 80}).status_code == 422, "a tie is refused")
check(post({**g, "opp_score": None}).status_code == 422, "one score alone is refused")
check(post({**g, "opp_name": ""}).status_code == 422 and post({**g, "opp_name": "Tunisia"}).status_code == 422 and post({**g, "competition": "nope"}).status_code == 422 and post({**g, "date": "2029-13-01"}).status_code == 422, "bad games refused")
check(post({**g, "id": gid, "tun": 70, "opp_score": 71}).status_code == 200 and not next(x for x in pub()["games"] if x["id"] == gid)["won"], "a game is edited")
import datetime  # noqa: E402
soon = (datetime.date.fromisoformat(natteam.today()) + datetime.timedelta(days=2)).isoformat()          # earlier than every shipped game still to come
check(post({"op": "game", "competition": cid, "date": soon, "opp_name": "Egypt", "site": "home"}).status_code == 200, "a game to come, with no score")
nx = pub()["next"]
check(nx and nx["opp"] == "EG" and nx["date"] == soon and not nx["played"], "it is the next game")
check(pub()["competitions"][-1]["record"] == {"w": 0, "l": 1, "pf": 70, "pa": 71}, "the record of the competition")
check(post({"op": "competition_delete", "id": cid}).status_code == 422, "a competition with games cannot be removed")
# a shipped game can be corrected or hidden without touching the shipped file
check(post({"op": "game", "id": "wcq27-04", "competition": "wcq27", "date": "2026-07-02", "opp_name": "Nigeria", "site": "neutral", "tun": 82, "opp_score": 84}).status_code == 200
      and next(x for x in pub()["games"] if x["id"] == "wcq27-04")["tun"] == 82, "a shipped game is corrected")
check(post({"op": "game_delete", "id": "wcq27-05"}).status_code == 200 and all(x["id"] != "wcq27-05" for x in pub()["games"]) and any(x["id"] == "wcq27-05" for x in ship["games"]), "a shipped game is hidden, not erased")
check(post({"op": "game_delete", "id": "nope"}).status_code == 422, "unknown game")
check(post({"op": "nonsense"}).status_code == 422, "unknown operation")

# --- pasted tables: parsing
pt = natteam.parse_table("Player MIN PTS REB AST\nOmar Abada 33:30 18 4 5\nFiras Lahiani;30;15;9,5;2\nTotal", ["min", "pts", "reb", "ast"])
check(pt == [{"name": "Omar Abada", "min": 33.5, "pts": 18.0, "reb": 4.0, "ast": 5.0}, {"name": "Firas Lahiani", "min": 30.0, "pts": 15.0, "reb": 9.5, "ast": 2.0}], f"header, minutes and decimals read: {pt}")
check(natteam.parse_table("Omar Abada\t7\t33\t18.1\t4,3\t5.7", ["g", "min", "pts", "reb", "ast"])[0]["ast"] == 5.7, "a line of a spreadsheet (tabs)")
check(natteam.parse_table("PTS REB\nOmar Abada 18 4", ["min"])[0] == {"name": "Omar Abada", "pts": 18.0, "reb": 4.0}, "the header sets the columns")
try:
    natteam.parse_table("nothing here\n\n", ["min"])
    check(False, "a text with no numbers is refused")
except ValueError:
    pass

# --- box score of a game: the statistics follow
gid = post({"op": "game", "competition": "friendly", "date": "2026-12-12", "opp_name": "Algeria", "site": "home", "venue": "Radès", "tun": 81, "opp_score": 70}).get_json()["id"]
txt = "Player;MIN;PTS;REB;AST;STL;BLK;TO;PF\nOmar Abada;33:20;26;4;6;2;0;3;2\nFiras Lahiani;30;20;10;2;1;1;2;3\nYacine Toumi;25;18;5;1;0;0;1;2\nBilel Jaziri;12;9;1;3;0;0;0;1\nMr Nobody;8;8;2;0;0;0;1;1"
pv = post({"op": "box_preview", "text": txt}).get_json()["lines"]
check([x["pid"] for x in pv] == ["ca-24", "usm-23", "yacine-toumi", "ca-8", None] and pv[1]["uncertain"] and pv[4]["uncertain"] and pv[0]["values"]["min"] == 33.3, f"the box score lines are matched: {[(x['pid'], x['uncertain']) for x in pv]}")
lines = [{"pid": x["pid"], "name": x["input"], **x["values"]} for x in pv]
r = post({"op": "box_save", "id": gid, "lines": lines})
check(r.status_code == 200 and "add up" not in r.get_json()["message"], f"box score saved, 81 points add up (26+20+18+9+8): {r.get_json().get('message')}")
check(post({"op": "box_save", "id": gid, "lines": [{"pid": "ca-24", "pts": 5}, {"pid": "ca-24", "pts": 4}]}).status_code == 422, "a player twice in a box score is refused")
check(post({"op": "box_save", "id": gid, "lines": [{"pid": "ca-24", "pts": 500}]}).status_code == 422 and post({"op": "box_save", "id": gid, "lines": [{"pid": "nobody-1", "pts": 5}]}).status_code == 422, "absurd numbers and unknown players refused")
check("add up" in post({"op": "box_save", "id": gid, "lines": [{"pid": "ca-24", "min": 30, "pts": 20}]}).get_json()["message"], "a box score that does not add up to the score warns")
post({"op": "box_save", "id": gid, "lines": lines})
check(post({"op": "box_save", "id": "wcq27-10", "lines": lines}).status_code == 422, "no box score for a game still to come")
gm = next(x for x in pub()["games"] if x["id"] == gid)
check(len(gm["lines"]) == 5 and gm["lines"][0]["name"] == "Omar Abada" and any(x["pid"] is None and x["name"] == "Mr Nobody" for x in gm["lines"]), "the public view has the box score, the unmatched player kept by name")
st = {s["competition"]: s for s in c.get("/api/players/ca-24").get_json()["national"]["stats"]}
check(st["friendly"]["g"] == 1 and st["friendly"]["pts"] == 26 and st["friendly"]["stl"] == 2 and st["wcq27"]["src"] == "summary", "his stats: the friendly from the box score, the qualifiers from the summary")
box = {s["competition"]: s for s in c.get("/api/players/ca-8").get_json()["national"]["stats"]}
check(box["friendly"]["pts"] == 9.0, "another player")
# a box score that covers fewer games than the summary does not replace the summary
bg = post({"op": "game", "competition": "wcq27", "date": "2026-08-27", "opp_name": "Cape Verde", "site": "home", "tun": 60, "opp_score": 56}).get_json()["id"]
post({"op": "box_save", "id": bg, "lines": [{"pid": "ca-24", "min": 30, "pts": 10, "reb": 1, "ast": 1}]})
w = {s["competition"]: s for s in c.get("/api/players/ca-24").get_json()["national"]["stats"]}["wcq27"]
check(w["src"] == "summary" and w["pts"] == 18.1, "one box score does not replace a summary of seven games")
check(post({"op": "box_clear", "id": gid}).status_code == 200 and not next(x for x in pub()["games"] if x["id"] == gid)["lines"], "a box score is removed")

# --- statistics without box scores
sp = post({"op": "stats_preview", "text": "Omar Abada 5 30 20.0 4.0 6.0\nFiras Lahiani 5 28 14.5 8.0 2.0"}).get_json()["lines"]
rows_ = [{"pid": x["pid"], **x["values"]} for x in sp]
check(rows_[0] == {"pid": "ca-24", "g": 5, "min": 30, "pts": 20, "reb": 4, "ast": 6} or rows_[0]["pts"] == 20, f"the lines of a table are read: {rows_[0]}")
check(post({"op": "stats_save", "competition": "afrobasket", "rows": rows_}).status_code == 200, "statistics saved for a competition")
check({s["competition"]: s for s in c.get("/api/players/usm-23").get_json()["national"]["stats"]}["afrobasket"]["pts"] == 14.5, "they show on the player page")
check(any(t_["competition"] == "afrobasket" for t_ in pub()["stats"]), "and as a block of the page")
check(post({"op": "stats_save", "competition": "afrobasket", "rows": [{"pid": None, "g": 3}]}).status_code == 422 and post({"op": "stats_save", "competition": "nope", "rows": rows_}).status_code == 422, "bad statistics refused")
check(post({"op": "stats_save", "competition": "afrobasket", "rows": [{"pid": "ca-24", "pts": 3}]}).status_code == 422, "the number of games is needed")
check(post({"op": "stats_clear", "competition": "afrobasket"}).status_code == 200 and not any(t_["competition"] == "afrobasket" for t_ in pub()["stats"]), "removed")
check(post({"op": "stats_save", "competition": "wcq27", "rows": [{"pid": "ca-24", "g": 2, "min": 20, "pts": 10, "reb": 2, "ast": 2}]}).status_code == 200
      and {s["competition"]: s for s in c.get("/api/players/ca-24").get_json()["national"]["stats"]}["wcq27"]["pts"] == 10, "typed statistics replace the shipped ones of that competition")
check(post({"op": "stats_clear", "competition": "wcq27"}).status_code == 200 and {s["competition"]: s for s in c.get("/api/players/ca-24").get_json()["national"]["stats"]}["wcq27"]["pts"] == 18.1, "and going back restores them")

print("national team:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
