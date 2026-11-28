"""A finished season shown like the current one (archive.py): tables, series, the cup bracket, club pages with their missing box scores, phase filters, the Finals MVP."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()

v = c.get("/api/archive/2025-2026").get_json()
by = {b["key"]: b for b in v["phases"]}
check(list(by) == ["regular", "playoff", "playout", "super", "superout", "cup", "ftbb"], f"one view per phase: {list(by)}")
check([len(g["table"]) for g in by["regular"]["groups"]] == [6, 6], "two pools in the regular season")
check([r["code"] for r in by["playoff"]["groups"][0]["table"]][:4] == ["CA", "USM", "ESS", "JSK"], "the play-off table ends in the order the semi-finals were drawn from")
check(next(r for r in by["playoff"]["groups"][0]["table"] if r["code"] == "CA")["pts"] == 38, "the points of the regular season are carried")
check([r["name"] for r in by["super"]["rounds"]] == ["Semi-finals", "Championship final", "Third place"] and by["super"]["champion"]["code"] == "USM", "the super play-off")
cup = by["cup"]
check([len(r["ties"]) for r in cup["rounds"]] == [8, 4, 2, 1] and cup["champion"]["code"] == "CA" and [t["home"]["code"] for t in cup["earlier"]] == ["ESR"], "the cup bracket")
for r, nxt in zip(cup["rounds"], cup["rounds"][1:]):
    for i, t in enumerate(nxt["ties"]):
        check([r["ties"][2 * i]["winner"], r["ties"][2 * i + 1]["winner"]] == [t["home"]["code"], t["away"]["code"]], f"{nxt['name']} tie {i}: its clubs come from the two ties before it")
check(by["superout"]["missing"] == [{"home": "BCM", "away": "ASH"}] and len(by["ftbb"]["missing"]) == 3, "results nobody published are listed as missing")
check(v["finals_mvp"]["name"] == "Troy Franklin" and v["finals_mvp"]["games"] == 3, f"the Finals MVP: {v['finals_mvp']}")

t = c.get("/api/archive/2025-2026/teams/usm").get_json()
check(t["name"] and len(t["games"]) == sum(p["played"] for p in t["phases"]) and len(t["without_box"]) == sum(p["played"] - p["with_box"] for p in t["phases"]), "a club's games and what is missing")
only = c.get("/api/archive/2025-2026/teams/USM?phase=cup").get_json()
check(only["stats"]["gp"] == 3 and all(p["gp"] <= 3 for p in only["players"]), "club numbers for the cup alone")
check(c.get("/api/archive/2026-2027").status_code == 404 and c.get("/api/archive/2025-2026/teams/ZZZ").status_code == 404, "unknown season or club")

all_ = c.get("/api/players?season=2025-2026").get_json()
cupp = c.get("/api/players?season=2025-2026&phase=cup").get_json()
check(max(p["gp"] for p in cupp["players"]) <= 4 < max(p["gp"] for p in all_["players"]) and "ftbb cup" in all_["phases"], "the player list for one phase")
pid = v["finals_mvp"]["id"]
one = c.get(f"/api/players/{pid}?season=2025-2026&phase=super%20play-off").get_json()
check(one["finals_mvp"] and one["player"]["gp"] == 7 and one["phase"] == "super play-off", "a player's super play-off alone")
check(c.get(f"/api/players/{pid}?season=2025-2026&phase=play-out").get_json()["phase"] is None, "a phase the player did not play shows the whole season")
for u in (f"/joueur/{pid}-troy-franklin", "/equipe/EZS", "/equipe/USM", "/historique/2025-2026"):
    check(c.get(u).status_code == 200, f"{u} is served")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("archive checks passed")
