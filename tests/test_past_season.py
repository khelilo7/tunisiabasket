"""Last season's box scores (assets/history, 2025-2026): kept apart from this season's identities and official scores, every result on the season page, wrapped names read."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT))
import french_parser  # noqa: E402
import history  # noqa: E402
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None

check(stats.same_person("ABADA OMAR", "Omar Abeda") and stats.same_person("MNAFEDH MOHAMED", "Mohamed Mnafedh"), "the same player under two spellings")
check(not stats.same_person("Khalil Rouissi", "Rayen Rouissi") and not stats.same_person("Troy Franklin", "Ghadyal Khayach"), "brothers and strangers are two players")

files = {f.stem: json.loads(f.read_text()) for f in (ROOT / "assets" / "history" / "games").glob("*.json")}
mine = {i: g for i, g in files.items() if g.get("history_season") == "2025-2026"}
loaded = {g["id"]: g for g in stats.build_all_games()}
check(len(mine) == 157, f"157 box scores of 2025-2026 ({len(mine)})")
for i, g in mine.items():
    x = loaded.get(i)
    check(x and [(t["code"], t["points"]) for t in x["teams"]] == [(t["code"], t["points"]) for t in g["teams"]] and not x.get("matchday_no"),
          f"{g['history_label']}: the sheet's score stays, this season's official result never takes its place")

past, now = stats.build("2025-2026"), stats.build("2026-2027")
names = {p["id"]: p["name"] for p in now["players"]}
for p in past["players"]:
    if p["id"] in names:
        check(stats.same_person(p["name"], names[p["id"]]), f"{p['id']}: {p['name']} would show on the profile of {names[p['id']]}")

v = history.view("2025-2026")
got = {s["name"]: s for s in v["sections"]}
check({k: len(s["games"]) for k, s in got.items() if s["games"]} == {"First phase": 60, "Play-off": 30, "Play-out": 30, "Super play-out": 11, "Tunisian Cup": 11, "FTBB Cup": 9},
      "every result of the season is listed, with or without a box score")
check(sum("box" in g for s in got.values() for g in s["games"]) + sum(1 for s in got.values() for x in s["series"] for b in x.get("box") or [] if b) == 157, "every box score is linked to its result")

lines = ["8 ZIED MEHREZ 16:43 2/2", "MOHAMED YASSINE", "*6 26:42 9/11 81,8", "MARMOUCH", "9 NIDHAL HAFNAOUI 23:54"]
check(french_parser.unwrap(lines) == ["8 ZIED MEHREZ 16:43 2/2", "*6 MOHAMED YASSINE MARMOUCH 26:42 9/11 81,8", "9 NIDHAL HAFNAOUI 23:54"], "a wrapped name goes back in its row")

if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails[:20]))
print("past season checks passed")
