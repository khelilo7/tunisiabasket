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

print("national team:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
