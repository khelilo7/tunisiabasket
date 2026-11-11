"""Jersey numbers change (phase 2): a player who changes number keeps his statistics, a newcomer who takes the number of somebody who left gets his own
profile, a deleted player frees his number, and a game's real day can be corrected."""
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import config  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# --- 1. the rule itself, on made-up games --------------------------------------------------------------------------------------------------------------
def row(number, name, dnp=False):
    return {"number": number, "name": name, "dnp": dnp, **({} if dnp else {"min": 10})}


def game(date, *players):
    return {"source": "text", "date": date, "teams": [{"code": "ESR", "name": "ES Rades", "players": list(players)}, {"code": "CA", "name": "Club Africain", "players": []}]}


def rules(*rs):
    stats.ROSTER_BASE = Path(tempfile.mkdtemp()) / "roster.json"           # an empty shipped roster: only the rules of this test
    stats.ROSTER_BASE.write_text(json.dumps({"numbers": list(rs)}))


rules()
games = [game("2026-10-01", row(25, "ALPHOUSSEYNI DIEDHIOU")), game("2026-10-08", row(25, "ALPHOUSSEYNI DIEDHIOU")), game("2026-11-11", row(25, "HEDI BEN ROMDHANE"))]
stats._canonicalise(games)
names = [t["players"][0]["name"] for g in games for t in g["teams"][:1]]
check(names[2] == "Alphousseyni Diedhiou", f"without a rule the number keeps its usual owner's name: {names}")      # the bug the rules exist for
rules({"team": "ESR", "number": 25, "id": "esr-125", "name": "Hedi Ben Romdhane", "from": "2026-11-11"})
games = [game("2026-10-01", row(25, "ALPHOUSSEYNI DIEDHIOU")), game("2026-10-08", row(25, "ALPHOUSSEYNI DIEDHIOU")), game("2026-11-11", row(25, "HEDI BEN ROMDHANE"))]
stats._canonicalise(games)
pl = [g["teams"][0]["players"][0] for g in games]
check([p["pid"] for p in pl] == ["esr-25", "esr-25", "esr-125"], f"the newcomer has an id of his own: {[p['pid'] for p in pl]}")
check(pl[2]["name"] == "Hedi Ben Romdhane" and pl[0]["name"] == "Alphousseyni Diedhiou", "each keeps his own name")

# a player who changes number: his rows under the new number are his, with his usual spelling
rules({"team": "ESR", "number": 8, "id": "esr-3", "from": "2026-11-11"})
games = [game("2026-10-01", row(3, "MEHDI OUESLATI"), row(8, "MOURAD MABROUK")), game("2026-10-08", row(3, "MEHDI OUESLATI"), row(8, "MOURAD MABROUK")),
         game("2026-11-11", row(8, "OUESLATI Mehdi"), row(3, "NEW GUY"))]
stats._canonicalise(games)
last = games[2]["teams"][0]["players"]
check(last[0]["pid"] == "esr-3" and last[0]["name"] == "Mehdi Oueslati", f"he keeps his profile and his name under the new number: {last[0]['pid']} {last[0]['name']}")
check(games[1]["teams"][0]["players"][1]["pid"] == "esr-8" and games[1]["teams"][0]["players"][1]["name"] == "Mourad Mabrouk", "the number's former owner keeps his past")

# a period: the rule stops after `to`
rules({"team": "ESR", "number": 10, "id": "esr-40", "name": "Jason Hobel", "from": "2026-10-28", "to": "2026-10-28"})
games = [game("2026-10-21", row(10, "ZROUR YOUSSEF")), game("2026-10-28", row(10, "JASON HOBEL")), game("2026-11-04", row(10, "ZROUR YOUSSEF"))]
stats._canonicalise(games)
check([g["teams"][0]["players"][0]["pid"] for g in games] == ["esr-10", "esr-40", "esr-10"], "a rule limited to one day touches that day only")
# malformed rules are ignored, never crash
rules({"team": "ESR", "number": "x", "id": "a"}, {"team": "ESR", "number": 5}, {"team": "ESR", "number": 5, "id": "esr-5", "from": "soon"}, "junk")
check(stats.load_roster()["numbers"] == [], "malformed rules are ignored")
stats.ROSTER_BASE = Path(stats.config.ASSETS_DIR / "roster.json")

# --- 2. the admin tools, on the seed data --------------------------------------------------------------------------------------------------------------
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda body: c.post("/admin/api/roster", json=body, headers=H)
players = lambda: {p["id"]: p for p in stats.build(keep_hidden=True)["players"]}
visible = lambda: {p["id"]: p for p in c.get("/api/players").get_json()["players"]}

base = players()
old = max((p for p in base.values() if p["team"] == "USM" and p["gp"] >= 3), key=lambda p: p["gp"])
num, gp0, pts0 = old["number"], old["gp"], old["pts"]
check(post({"op": "add", "team": "USM", "name": "Newcomer Test", "number": num}).status_code == 409, "a number somebody wears is not free")
check(post({"op": "hide", "id": old["id"]}).status_code == 200 and old["id"] not in visible(), "he is deleted")
r = post({"op": "add", "team": "USM", "name": "newcomer  test", "number": num, "since": "2026-12-01"})
check(r.status_code == 200, f"his number is free once he is deleted: {r.get_json()}")
new_id = r.get_json()["id"]
check(new_id != old["id"] and re.fullmatch(r"usm-\d+", new_id), f"the newcomer has an id of his own: {new_id}")
mine = json.loads(stats.ROSTER_FILE.read_text())
check(any(n["id"] == new_id and n["number"] == num and n["from"] == "2026-12-01" for n in mine["numbers"]), "a number rule was written")
check(visible()[new_id]["number"] == num and visible()[new_id]["gp"] == 0, "he is on the roster with no games")
check(post({"op": "add", "team": "USM", "name": "Another", "number": num}).status_code == 409, "and the number is taken again")

# his first sheet (made up): a copy of a seed game of that team, played after the date, with the newcomer under the old number
src = next(g for g in stats.load_games() if any(t["code"] == "USM" for t in g["teams"]))
raw = json.loads(next((config.DATA_DIR / "games").glob(f"{src['id']}.json")).read_text()) if (config.DATA_DIR / "games" / f"{src['id']}.json").exists() else copy.deepcopy(src)
raw = copy.deepcopy(raw)
raw["id"], raw["date"] = "numbers-test-1", "2026-12-01"
usm = next(t for t in raw["teams"] if t["code"] == "USM")
usm["points"] += 1                                                    # not the same game uploaded twice
usm["players"] = [dict(p) for p in usm["players"]]
slot = next(p for p in usm["players"] if not p.get("dnp") and p["number"] != num)
for p in usm["players"]:
    if p["number"] == num:
        usm["players"].remove(p)
        break
slot["number"], slot["name"] = num, "NEWCOMER TEST"
(config.DATA_DIR / "games" / "numbers-test-1.json").write_text(json.dumps(raw))
after = players()
check(after[new_id]["gp"] == 1 and after[new_id]["name"] == "Newcomer Test", f"the sheet is the newcomer's: gp {after[new_id]['gp']} {after[new_id]['name']}")
check(after[old["id"]]["gp"] == gp0 and after[old["id"]]["pts"] == pts0, "the player who left keeps exactly his games and averages")
check(c.get("/api/overview").status_code == 200 and c.get(f"/api/players/{new_id}").status_code == 200, "the site works with the newcomer")
check(post({"op": "restore", "id": old["id"]}).status_code == 200 and old["id"] in visible(), "restoring the old player works")
post({"op": "hide", "id": old["id"]})

# an added signing who never played: deleting him really removes him (number and id free again)
r = post({"op": "add", "team": "CA", "name": "Never Played", "number": 91})
check(r.status_code == 200 and r.get_json()["id"] == "ca-91", "a free number gets the usual id")
check(post({"op": "hide", "id": "ca-91"}).status_code == 200 and "ca-91" not in players(), "deleting a signing who never played removes him")
check(post({"op": "add", "team": "CA", "name": "Second Try", "number": 91}).get_json().get("id") == "ca-91", "the id is reusable")

# --- 3. renumber keeps the statistics -------------------------------------------------------------------------------------------------------------------
ca = max((p for p in players().values() if p["team"] == "CA" and p["gp"] >= 3 and not p.get("hidden")), key=lambda p: p["gp"])
before = {k: ca[k] for k in ("gp", "pts", "reb", "ast", "pir", "total_min")}
free = next(n for n in range(60, 99) if not any(p["team"] == "CA" and p["number"] == n for p in players().values()))
taken = next(p["number"] for p in players().values() if p["team"] == "CA" and p["id"] != ca["id"] and not p.get("hidden") and p["number"] != ca["number"])
check(post({"op": "renumber", "id": ca["id"], "number": taken}).status_code == 409, "a number worn by a teammate is refused")
check(post({"op": "renumber", "id": ca["id"], "number": 120}).status_code == 422, "an impossible number is refused")
check(post({"op": "renumber", "id": ca["id"], "number": free, "since": "2026-11-11"}).status_code == 200, "renumber")
now = players()[ca["id"]]
check(now["number"] == free and {k: now[k] for k in before} == before, f"new number, same statistics: #{now['number']} {before} -> { {k: now[k] for k in before} }")
check(next(p for p in c.get("/admin/api/roster", headers=H).get_json()["players"] if p["id"] == ca["id"])["number"] == free, "the admin list shows it")
check(post({"op": "add", "team": "CA", "name": "Takes The Old Number", "number": ca["number"]}).status_code == 200, "the number he left is free")
check(post({"op": "undo_number", "index": 99}).status_code == 404, "unknown number change")
idx = next(i for i, n in enumerate(json.loads(stats.ROSTER_FILE.read_text())["numbers"]) if n["id"] == ca["id"])
check(post({"op": "undo_number", "index": idx}).status_code == 200 and players()[ca["id"]]["number"] == ca["number"], "undo gives the old number back")
check(post({"op": "renumber", "id": ca["id"], "number": free, "since": "2026-13-45"}).status_code == 422, "a bad date is refused")
check(c.post("/admin/api/roster", json={"op": "renumber", "id": ca["id"], "number": free}).status_code == 401, "renumbering is admin only")

# --- 4. the real day of a game --------------------------------------------------------------------------------------------------------------------------
g = stats.load_games()[0]
check(c.post("/admin/api/game-date", json={"id": g["id"], "date": "2026-11-11"}).status_code == 401, "changing a date is admin only")
check(c.post("/admin/api/game-date", json={"id": "nope", "date": "2026-11-11"}, headers=H).status_code == 404, "unknown game")
check(c.post("/admin/api/game-date", json={"id": g["id"], "date": "11/11/2026"}, headers=H).status_code == 422, "bad date")
check(c.post("/admin/api/game-date", json={"id": g["id"], "date": "2026-11-11"}, headers=H).status_code == 200, "date saved")
check(next(x for x in stats.load_games() if x["id"] == g["id"])["date"] == "2026-11-11", "the game is on the corrected day")
c.post("/admin/api/game-date", json={"id": g["id"], "date": ""}, headers=H)
check(next(x for x in stats.load_games() if x["id"] == g["id"])["date"] == g["date"], "an empty date removes the correction")

# --- 5. what ships with the code is well formed ---------------------------------------------------------------------------------------------------------
shipped = json.loads((config.ASSETS_DIR / "roster.json").read_text())
for n in shipped.get("numbers", []):
    check(re.fullmatch(r"[a-z0-9]+-\d+", n["id"]) and 0 <= n["number"] <= 99 and n["team"].isupper(), f"shipped rule is well formed: {n}")
    check(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", n[k]) for k in ("from", "to") if n.get(k)), f"shipped rule dates: {n}")
check(len(shipped.get("numbers", [])) == len(stats._number_rules(shipped.get("numbers", []))), "no shipped rule is dropped as malformed")
for gid, d in json.loads((config.ASSETS_DIR / "game_dates.json").read_text()).items():
    if not gid.startswith("_"):
        check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and re.fullmatch(r"[A-Za-z0-9_-]{4,40}", gid), f"shipped game date: {gid} {d}")

print("numbers:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
