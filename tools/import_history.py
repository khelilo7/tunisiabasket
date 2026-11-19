"""Read the box scores collected by tools/archive_ftbb.py (and the 2021-22 Drive files) with the site's importer, check them, and store the good ones as history.

    python tools/import_history.py [--raw exports/history_raw] [--jobs 3] [--only SEASON]

Every PDF goes through extractor.extract (text layer, else Tesseract). The date is the one printed on a text PDF; for a scan it is the date of the label the FTBB gave the file. A game that
passes every consistency check (points, rebounds, shooting, minutes) is written to assets/history/games/<id>.json; the others are listed in OUT/problems.json for a human look. OUT/parsed.json
keeps everything that was read (scores included), which the history results are built from.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", str(ROOT / "exports" / "history_raw" / "_tmpdata"))
import extractor  # noqa: E402
from french_parser import KNOWN, canon  # noqa: E402

PHASES = [("superplayoff", "super play-off"), ("playoff", "play-off"), ("playout", "play-out"), ("coupe", "cup"), ("finalecoupe", "cup")]


def label_info(label, season):
    """(date, phase) from the label the FTBB gave: '29/09/2018_CA vs ESG', '20171004_DSG_CA', '20180224_ASH_SN_PlayOut'."""
    m = re.match(r"\s*(\d{2})[/_](\d{2})[/_](\d{4})", label)
    date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
    if not date:
        m = re.match(r"\s*(\d{4})(\d{2})(\d{2})", label)
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
    low = re.sub(r"[^a-z]", "", label.lower())
    phase = next((p for k, p in PHASES if k in low), "regular season")
    return date, phase


# Matchday 1 of each phase of a season whose files carry only "J3", "P-OFFJ2", "SPOSF-G3" (the 2021-22 Drive sheet; its tabs 1ère phase, P-OFF, P-OUT): a scan gets the date of its
# matchday (a week per matchday, three days per game of a series), flagged approximate: the page shows "J3" or "G3", not the date. A sheet with a text layer keeps its printed date.
MATCHDAY_BASE = {"2021-2022": {"regular season": ("2021-09-25", 7), "play-off": ("2022-02-05", 7), "play-out": ("2022-02-05", 7), "super play-out": ("2022-04-16", 4),
                               "super play-off": ("2022-04-14", 3), "super play-off final": ("2022-04-28", 3)}}


def label_matchday(label, season, phase):
    m = re.search(r"(?:^|[\s_-]|OUT|OFF)(J|G)\s*(\d+)(?=[_\s]|$)", label.strip())
    key = "super play-off final" if "SPOF-" in label else phase
    base = MATCHDAY_BASE.get(season, {}).get(key)
    if not m or not base:
        return None, None
    n = int(m.group(2))
    return f"{m.group(1)}{n}", (datetime.date.fromisoformat(base[0]) + datetime.timedelta(days=base[1] * (n - 1))).isoformat()


def work(args):
    path, label, season = args
    try:
        game, problems = extractor.extract(path, filename=Path(path).name)
    except Exception as e:                                         # noqa: BLE001 - one bad file never stops the batch
        return {"file": path, "label": label, "season": season, "error": repr(e)[:200]}
    for t in game["teams"]:
        t["code"] = canon(t["code"], t["name"])
    unknown = [t["code"] for t in game["teams"] if t["code"] not in KNOWN]
    if unknown:
        problems = [*problems, f"not a club of the league: {unknown}"]
    date, phase = label_info(label, season)
    if re.search(r"SPOUT", label):
        phase = "super play-out"
    elif re.search(r"SPOSF|SPOF-", label):
        phase = "super play-off"
    elif re.search(r"P-?OUT", label, re.I):
        phase = "play-out"
    elif re.search(r"P-?OFF", label, re.I):
        phase = "play-off"
    elif re.search(r"COUPE", label, re.I):
        phase = "cup"
    md, mdate = label_matchday(label, season, phase)
    if md:
        game["history_matchday"] = md
        if game.get("date_approx") or not date and game.get("source") == "ocr":
            game["date"], game["date_approx"] = mdate, True
    if game.get("source") == "ocr" and date:                       # a scan has no readable date: the FTBB's label has it
        game["date"], game["date_approx"] = date, False
    game["phase"] = phase
    game["history_label"] = label
    game["id"] = hashlib.sha1(f"{game['date']}{sorted(t['code'] for t in game['teams'])}{[t['points'] for t in game['teams']]}".encode()).hexdigest()[:16]
    if game.get("date_approx") and not game.get("history_matchday"):          # a date made up from today's season: the game cannot be placed
        problems = [*problems, "no usable date"]
    game["history_season"] = season
    return {"file": path, "label": label, "season": season, "game": game, "problems": problems}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", default="exports/history_raw")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--only")
    a = ap.parse_args()
    raw = ROOT / a.raw
    items = []
    for d in sorted(raw.iterdir()):                                # one folder per season; the file name starts with the label the FTBB gave
        if d.is_dir() and not d.name.startswith("_") and d.name != "2021-2022_drive":
            for f in sorted(d.glob("*.pdf")):
                if f.read_bytes()[:5] == b"%PDF-":
                    items.append((str(f), f.name.split("__")[0], d.name))
    for f in sorted((raw / "2021-2022_drive").iterdir()):
        if f.suffix.lower() in (".pdf", ".jpg", ".png"):
            items.append((str(f), f.stem, "2021-2022"))
    seen, uniq = set(), []
    for it in items:                                              # the FTBB page links some files twice
        h = hashlib.sha1(Path(it[0]).read_bytes()).hexdigest()
        if h not in seen:
            seen.add(h)
            uniq.append(it)
    if a.only:
        uniq = [i for i in uniq if i[2] == a.only]
    print(len(uniq), "files to read", flush=True)
    out = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for n, r in enumerate(ex.map(work, uniq), 1):
            out.append(r)
            g = r.get("game")
            print(n, len(uniq), "ERR " + r["error"] if "error" in r else ("ok " if not r["problems"] else "PROBLEMS ") + f"{g['date']} " + " v ".join(f"{t['code']} {t['points']}" for t in g["teams"]), flush=True)
    mine = out
    if a.only and (raw / "parsed.json").exists():                  # keep what was read for the other seasons
        out = [r for r in json.loads((raw / "parsed.json").read_text()) if r["season"] != a.only] + out
    (raw / "parsed.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    dest = ROOT / "assets" / "history" / "games"
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.json"):                                 # a game of a season read again is replaced, never left behind under an older id
        try:
            if json.loads(old.read_text()).get("history_season") in {r["season"] for r in mine}:
                old.unlink()
        except (OSError, ValueError):
            pass
    good = [r for r in out if "game" in r and not r["problems"]]
    mine_good = [r for r in mine if "game" in r and not r["problems"]]
    for r in good:
        (dest / f"{r['game']['id']}.json").write_text(json.dumps(r["game"], indent=1, ensure_ascii=False))
    (raw / "problems.json").write_text(json.dumps([{k: r.get(k) for k in ("file", "label", "season", "error", "problems")} for r in out if "error" in r or r.get("problems")], indent=1, ensure_ascii=False))
    print(f"{len(mine_good)} of {len(mine)} games stored for this run, {len(mine) - len(mine_good)} need a look (see {raw / 'problems.json'}); {len(good)} stored in all")


if __name__ == "__main__":
    main()
