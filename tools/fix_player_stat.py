"""Correct one stat of one player in a game already on the site (for example an OCR misread), without touching anything else.

    python tools/fix_player_stat.py --site https://tunisiabasket.com --game dafa2ad5e7f2af49 --team CSS --number 21 dreb=3 [--date 2026-11-11] [--name 9="Montassar Lajmi"] [--dry-run]

It downloads the game from the site, rebuilds the stored game (same id, source, date), changes only the stats given (reb is recomputed as oreb + dreb when one of them changes),
runs the site's checks and writes exports/games_inbox/fix-<game id>.json; then send that file only:  python tools/send_games.py --site ... fix-<game id>.json
Sending a game with the same id rewrites it. Stats that are not on the sheet's own columns (pir, rating) are never stored, the site recomputes them.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from validate import validate  # noqa: E402

PLAYER = ("number", "name", "starter", "captain", "dnp", "min", "fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts")
EDITABLE = ("min", "fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts")
GAME = ("competition", "date", "date_approx", "id", "matchday", "matchday_no", "source", "source_file")


def fetch(site, gid):
    req = urllib.request.Request(f"{site.rstrip('/')}/api/games/{gid}", headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def rebuild(api):
    game = {k: api[k] for k in GAME if k in api}
    game["uploaded"] = True
    game["teams"] = []
    for t in api["teams"]:
        players = []
        for p in t["players"]:
            keep = ("number", "name", "starter", "captain", "dnp") if p.get("dnp") else PLAYER
            players.append({k: p[k] for k in keep if k in p and p[k] is not None})
        team = {"code": t["code"], "name": t["name"], "coach": t.get("coach", ""), "points": t.get("box_points", t["points"]), "players": players}
        for k in ("not_attributed", "extra"):             # what a sheet says about the team itself (team rebounds, points in the paint...) is part of the game
            if t.get(k):
                team[k] = t[k]
        game["teams"].append(team)
    return game


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--team", required=True)
    ap.add_argument("--number", type=int, required=True)
    ap.add_argument("--date", help="the exact day of the game (YYYY-MM-DD), when the sheet prints it and the site only has an approximate one")
    ap.add_argument("--name", action="append", default=[], help="NUMBER=Correct Name for a player of --team (a spelling the OCR got wrong); repeatable")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("changes", nargs="*", help="field=value for --team/--number, e.g. dreb=3 or pm=-4")
    a = ap.parse_args()
    api = fetch(a.site, a.game)
    game = rebuild(api)
    team = next((t for t in game["teams"] if t["code"] == a.team), None)
    p = next((p for p in (team or {"players": []})["players"] if p["number"] == a.number), None)
    if p is None or p.get("dnp"):
        sys.exit(f"{a.team} #{a.number} did not play in game {a.game}")
    if a.date:
        print(f"date {game.get('date')} (approx: {game.get('date_approx')}) -> {a.date} (exact)")
        game["date"], game["date_approx"] = a.date, False
    for nm in a.name:
        num, _, new = nm.partition("=")
        q = next((q for q in team["players"] if q["number"] == int(num)), None)
        if q is None:
            sys.exit(f"{a.team} #{num} is not in the game")
        print(f"{a.team} #{num}: name {q['name']!r} -> {new!r}")
        q["name"] = new
    for ch in a.changes:
        k, _, v = ch.partition("=")
        if k not in EDITABLE:
            sys.exit(f"cannot change {k!r}: one of {', '.join(EDITABLE)}")
        print(f"{a.team} #{a.number} {p['name']}: {k} {p.get(k)} -> {v}")
        p[k] = float(v) if k == "min" else int(v)
    if any(c.split("=")[0] in ("oreb", "dreb") for c in a.changes):
        p["reb"] = p["oreb"] + p["dreb"]
        print(f"  reb is now {p['reb']}")
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
