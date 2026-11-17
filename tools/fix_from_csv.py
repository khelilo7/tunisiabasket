"""Correct a game already on the site from a board CSV (the counting board's export), keeping everything the CSV does not carry.

    python tools/fix_from_csv.py --site https://tunisiabasket.com --game d7cff7189e379e5a [board.csv] [--set TEAM:NUM:field=value ...] [--base fix-file.json] [--dry-run]

The CSV wins for the columns it has (PTS FGM FGA 3PM 3PA FTM FTA OREB DREB REB AST STL BLK TOV PF; 2P is FG minus 3P). Minutes, +/-, drawn fouls, starters,
captain, did-not-play rows, coaches, names, id, date and source stay as the site has them. --set adds one more change on top (for example ESS:45:blk=1).
--base starts from a file already written by a tool (so two corrections of one game add up) instead of the site's copy.
--made-only is for a CSV that counted only what one team MADE (made shots, free throws, points) and what it happened to see: made shots and points come from the CSV, the misses
the site already has stay (attempts = new makes + the site's misses), rebounds / assists / steals / blocks / turnovers / fouls only go UP to the CSV's number (never down: the
CSV may have missed some), and a CSV player the site's sheet does not have is added with 0 minutes. Only the teams in the CSV change.
Runs the site's checks and writes exports/games_inbox/fix-<game id>.json; send that file only:  python tools/send_games.py --site ... fix-<game id>.json
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from fix_player_stat import fetch, rebuild  # noqa: E402
from validate import validate  # noqa: E402

COLUMNS = {"PTS": "pts", "FGM": "fgm", "FGA": "fga", "3PM": "p3m", "3PA": "p3a", "FTM": "ftm", "FTA": "fta", "OREB": "oreb", "DREB": "dreb", "REB": "reb",
           "AST": "ast", "STL": "stl", "BLK": "blk", "TOV": "tov", "PF": "pf"}


def read_rows(path):
    """{(team, number): {field: int}} from a board CSV."""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        d = {k: int(r[c]) for c, k in COLUMNS.items()}
        if r.get("FD") not in (None, ""):                       # fouls drawn: only when the board counted them (board v2 has an FD button)
            d["fd"] = int(r["FD"])
        d["p2m"], d["p2a"] = d["fgm"] - d["p3m"], d["fga"] - d["p3a"]
        out[(r["team"].strip(), int(r["number"]))] = d
    return out


def read_names(path):
    return {(r["team"].strip(), int(r["number"])): r["player"].strip() for r in csv.DictReader(open(path, encoding="utf-8"))}


def apply_made_only(game, rows, names):
    """The --made-only rule (see the top of this file); returns the printed changes."""
    log = []
    index = {(t["code"], p["number"]): p for t in game["teams"] for p in t["players"] if not p.get("dnp")}
    for key, c in rows.items():
        p = index.get(key)
        if p is None:
            team = next((t for t in game["teams"] if t["code"] == key[0]), None)
            if team is None:
                raise SystemExit(f"{key[0]} is not a team of this game")
            p = {"number": key[1], "name": names[key], "starter": False, "captain": False, "dnp": False, "min": 0.0, "fgm": 0, "fga": 0, "p2m": 0, "p2a": 0, "p3m": 0, "p3a": 0,
                 "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0, "reb": 0, "ast": 0, "tov": 0, "stl": 0, "blk": 0, "pf": 0, "fd": 0, "pm": 0, "pts": 0}
            team["players"] = [q for q in team["players"] if not (q.get("dnp") and q["number"] == key[1])] + [p]
            log.append(f"{key[0]} #{key[1]} {p['name']}: not on the site's sheet, added (0 minutes)")
        before = dict(p)
        miss2, miss3, missft = p["p2a"] - p["p2m"], p["p3a"] - p["p3m"], p["fta"] - p["ftm"]
        p["p2m"], p["p3m"], p["ftm"], p["pts"] = c["p2m"], c["p3m"], c["ftm"], c["pts"]
        p["p2a"], p["p3a"], p["fta"] = p["p2m"] + miss2, p["p3m"] + miss3, p["ftm"] + missft
        p["fgm"], p["fga"] = p["p2m"] + p["p3m"], p["p2a"] + p["p3a"]
        for k in ("oreb", "dreb", "ast", "stl", "blk", "tov", "pf"):
            p[k] = max(p[k], c[k])
        p["reb"] = p["oreb"] + p["dreb"]
        for k in ("pts", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf"):
            if p[k] != before[k]:
                log.append(f"{key[0]} #{key[1]} {p['name']}: {k} {before[k]} -> {p[k]}")
    return log


def apply(game, rows, sets=()):
    """Overlay the CSV rows (then the --set changes) on the game; returns the list of printed changes. A CSV player the game does not have is an error."""
    log = []
    index = {(t["code"], p["number"]): p for t in game["teams"] for p in t["players"] if not p.get("dnp")}
    missing = [k for k in rows if k not in index]
    if missing:
        raise SystemExit("in the CSV but not playing in the game: " + ", ".join(f"{t} #{n}" for t, n in missing))
    for key, vals in rows.items():
        p = index[key]
        for k, v in vals.items():
            if p.get(k) != v:
                log.append(f"{key[0]} #{key[1]} {p['name']}: {k} {p.get(k)} -> {v}")
                p[k] = v
    for s in sets:
        team, num, kv = s.split(":", 2)
        k, _, v = kv.partition("=")
        p = index.get((team, int(num)))
        if p is None:
            raise SystemExit(f"{team} #{num} is not playing in the game")
        log.append(f"{team} #{num} {p['name']}: {k} {p.get(k)} -> {v}  (--set)")
        p[k] = int(v)
        if k in ("oreb", "dreb"):
            p["reb"] = p["oreb"] + p["dreb"]
        if k in ("fgm", "p3m"):
            p["p2m"] = p["fgm"] - p["p3m"]
        if k in ("fga", "p3a"):
            p["p2a"] = p["fga"] - p["p3a"]
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--base", help="a fix file already written for this game, to build on instead of the site's copy")
    ap.add_argument("--set", action="append", default=[], help="TEAM:NUMBER:field=value, repeatable")
    ap.add_argument("--made-only", action="store_true", help="the CSV counted made shots only: keep the site's misses, only raise the other counts, add a missing player")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("csv", nargs="?", help="the board CSV (optional when only --set changes are given)")
    a = ap.parse_args()
    game = json.load(open(a.base)) if a.base else rebuild(fetch(a.site, a.game))
    rows = read_rows(a.csv) if a.csv else {}
    log = apply_made_only(game, rows, read_names(a.csv)) if a.made_only else []
    log += apply(game, {} if a.made_only else rows, a.set)
    print("\n".join(log) or "nothing differs")
    problems = validate(game)
    if problems:
        sys.exit("REFUSED:\n  " + "\n  ".join(problems))
    out = ROOT / "exports" / "games_inbox" / f"fix-{a.game}.json"
    if a.dry_run:
        print("checks passed (dry run, nothing written)")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(game, indent=1, ensure_ascii=False))
    print("checks passed ->", out)


if __name__ == "__main__":
    main()
