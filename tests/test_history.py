"""The history pages (history.py, assets/history): champions, one detail per season with its format, sections and box scores; the API and the page both answer."""
import os
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault("SITE_URL", "https://example.test")
import app  # noqa: E402
import history  # noqa: E402
import stats  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


champ = history.champions()
check(len(champ) >= 70 and champ[0]["season"] == "1955-1956" and champ[-1]["season"] >= "2025-2026", "champions run from 1955-56 to the last season")
check(len({c["season"] for c in champ}) == len(champ), "one champion per season")
check(all(re.fullmatch(r"\d{4}-\d{4}", c["season"]) for c in champ), "season ids look like 2018-2019")

fm = history.formats()
ids = history.season_ids()
check(len(ids) >= 10, f"detail for at least ten seasons ({len(ids)})")
check(all(fm.get(s, {}).get("en") and fm[s].get("fr") for s in ids), "every season with a detail has its format in English and in French: " + ",".join(s for s in ids if not fm.get(s)))

check(history.phase_name("Deuxième phase · Play-off · Classement") == "Second phase · Play-off", "phase names are made English and plain")
check(history.phase_name("Phase 3 (super play-off) · Demi-finale") == "Super play-off · Semi-finals", "the French super play-off semi-final")
check(history.phase_name("Deuxième phase · Play-off · Play-out") == "Second phase · Play-out", "a play-out nested in a play-off heading is a play-out")
check(history.view("not-a-season") is None and history.view("1900-1901") is None, "unknown seasons are None")

import json  # noqa: E402
from french_parser import KNOWN  # noqa: E402

files = sorted(stats.HISTORY_GAMES_DIR.glob("*.json"))
check(len(files) >= 90, f"the archived box scores are in the repository ({len(files)})")
for f in files:
    g = json.loads(f.read_text())
    check("2016-08" <= g["date"] < "2026-08", f"{f.name}: a history game belongs to a past season, not {g['date']}")
    check(all(t["code"] in KNOWN for t in g["teams"]) and len(g["teams"]) == 2, f"{f.name}: two clubs of the league")
    check(all(sum(p["pts"] for p in t["players"] if not p.get("dnp")) == t["points"] for t in g["teams"]), f"{f.name}: player points add up to the score")
    check(f.stem == g["id"] and g.get("history_label"), f"{f.name}: id and label")
box_seasons = {stats.season_of(json.loads(f.read_text())["date"]) for f in files}
check({"2017-2018", "2018-2019", "2021-2022"} <= box_seasons, f"box scores for 2017-18, 2018-19 and 2021-22 ({sorted(box_seasons)})")

c = app.app.test_client()
r = c.get("/api/history")
check(r.status_code == 200 and r.json["champions"] and r.json["seasons"], "/api/history answers")
for s in ids:
    r = c.get(f"/api/history/{s}")
    check(r.status_code == 200, f"/api/history/{s}")
    v = r.json
    check(v["champion"], f"{s}: champion")
    for sec in v["sections"]:
        for row in sec["table"] or []:
            check(row["w"] + row["l"] == row["j"], f"{s} {sec['name']}: {row['name']} played {row['j']} but won {row['w']} and lost {row['l']}")
        for ser in sec["series"]:
            check(all(len(g) == 2 for g in ser["games"]), f"{s}: series games are pairs")
check(c.get("/api/history/2999-3000").status_code == 404, "unknown season: 404")

s = c.get("/historique/2018-2019")
check(s.status_code == 200 and "2018/2019" in s.get_data(as_text=True), "the French page of a season renders for crawlers")
check(c.get("/en/history").status_code == 200 and c.get("/historique").status_code == 200, "both languages")
check(c.get("/historique/abc").status_code == 404, "a bad season address is a 404")
print("history:", "FAILED" if fails else "ok")
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
