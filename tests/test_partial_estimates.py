"""One-player sheets with estimated values (assets/partial_games.json): the estimates are flagged, add up, and never turn a sheet into a box score."""
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


raw = json.loads(stats.PARTIAL_FILES[0].read_text())["games"]
one = [g for g in raw if g["id"] != "p-j1-esg-ca"]
check(len(one) >= 1, "the shipped file has one-player sheets")

# 1. each sheet is arithmetically sound: points = 2*2P + 3*3P + FT, made <= attempted, every estimated key is a real stat
for g in one:
    for p in g["players"]:
        who = f"{g['id']} #{p['number']}"
        check(p["pts"] == 2 * (p["fgm"] - p["p3m"]) + 3 * p["p3m"] + p["ftm"], f"{who}: PTS != 2*2P + 3*3P + FT")
        check(0 <= p["p3m"] <= p["p3a"] <= p["fga"] and p["fgm"] <= p["fga"] and p["ftm"] <= p["fta"], f"{who}: made/attempted order")
        check(set(p.get("est", [])) <= set(stats.ESTIMABLE) and "pts" not in p.get("est", []) and "oreb" not in p.get("est", []) and "dreb" not in p.get("est", []), f"{who}: only estimable stats are flagged (never points or rebounds)")

d = stats.build()
with_sheets = {g["id"]: g for g in d["partials"]}
c = app.app.test_client()
for g in one:
    pg = with_sheets.get(g["id"])
    check(pg is not None, f"{g['id']} is built")
    if not pg:
        continue
    check(pg["complete"] is False and pg["estimated"] is True, f"{g['id']}: flagged as incomplete and estimated")
    check(pg["mvp"] is None, f"{g['id']}: a sheet of one player gives no game MVP")
    rec = next(t for t in pg["teams"] if t["recorded"])
    check(all(p["est"] and p["pid"] for p in rec["players"]), f"{g['id']}: estimated values travel with the row")
    v = c.get("/api/games/" + g["id"]).get_json()
    check(v.get("partial") is True and v["complete"] is False, f"{g['id']}: API page marks it incomplete")
    check(c.get("/match/" + g["id"]).status_code == 200, f"{g['id']}: server-rendered page")

# 2. the box-score count only grows for complete sheets (the CA sheet), never for a one-player sheet
ov = {r["code"]: r["box"] for r in c.get("/api/overview").get_json()["standings"]}
saved, stats.PARTIAL_FILES = stats.PARTIAL_FILES, ()
ov0 = {r["code"]: r["box"] for r in c.get("/api/overview").get_json()["standings"]}
base = stats.build()
base_rows = mvp._race_data(1)[0]
stats.PARTIAL_FILES = saved
teams_one = {g["recorded"] for g in one}
for code in teams_one:
    check(ov[code] == ov0[code], f"{code}: one-player sheets are not box scores")

# 3. the player gets the games; points and rebounds are the sheet's, the others include the estimates; nothing unknown becomes 0
A, B = {p["id"]: p for p in base["players"]}, {p["id"]: p for p in d["players"]}
ids = {p["pid"] for g in d["partials"] if not g["complete"] for t in g["teams"] for p in t["players"]}
for i in ids:
    n_sheets = sum(1 for g in one for p in g["players"] if with_sheets.get(g["id"]) and any(x["pid"] == i for t in with_sheets[g["id"]]["teams"] for x in t["players"]))
    check(B[i]["gp"] == A[i]["gp"] + n_sheets, f"{i}: {n_sheets} more games played")
    rows = B[i]["log"]
    sheet_rows = [r for r in rows if r.get("partial")]
    check(len(sheet_rows) == n_sheets and all(r["min"] is None and r["pir"] is None and r["pm"] is None for r in sheet_rows), f"{i}: minutes, +/- and PIR of the sheet games stay unknown")
    check(all(r["est"] for r in sheet_rows), f"{i}: every sheet game says which values are estimated")
    check(B[i]["pts"] == round(sum(r["pts"] for r in rows) / len(rows), 1), f"{i}: points average counts the sheet games")
    check(B[i]["reb"] == round(sum(r["reb"] for r in rows) / len(rows), 1), f"{i}: rebounds average counts the sheet games")
    full = [r for r in rows if not r.get("partial")]
    check(B[i]["min"] == round(sum(r["min"] for r in full) / len(full), 1), f"{i}: minutes average ignores the sheet games")
    for k in ("pir", "impact", "rating", "pm"):
        check(A[i][k] == B[i][k], f"{i}: {k} unchanged (the sheet does not know it)")
    check(B[i]["mvp_games"] == A[i]["mvp_games"], f"{i}: no game MVP from a one-player sheet")

# 4. everything else is exactly what it was
for p in B.values():
    if p["id"] not in ids and not any(p["id"] == x["pid"] for g in d["partials"] for t in g["teams"] for x in t["players"]):
        check(json.dumps(A[p["id"]], sort_keys=True, default=str) == json.dumps(p, sort_keys=True, default=str), f"{p['id']} unchanged")
check(json.dumps(d["games"], sort_keys=True, default=str) == json.dumps(base["games"], sort_keys=True, default=str), "full box scores unchanged")
check(d["standings"] == base["standings"], "standings unchanged")
rows = mvp._race_data(1)[0]
check([r["id"] for r in rows] == [r["id"] for r in base_rows], "phase MVP race: same candidates and order")

print("partial estimates:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
