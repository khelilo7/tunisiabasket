"""Corrections to games already on the site that travel with the code (assets/game_fixes/<game id>.json, each a complete game, same format as tools/send_games.py sends).

On start-up each fix file is applied ONCE (the file's name and content hash are remembered in data/applied_fixes.json):
  * the game it names must already exist in data/games, otherwise the fix is skipped for good (a copy of the site never gains a game this way);
  * the game as it was is first copied to data/games_replaced/<id>-<UTC time>.json, then replaced by the fix (same as sending the game again);
  * a fix that fails the site's consistency checks is refused and reported, never stored.
Changing the content of a fix file applies it again; a game sent or edited from the admin afterwards is NOT overwritten at the next start-up.

A fix that changes a few numbers of a game does not have to carry the whole game: assets/game_patches/<name>.json says
  {"game": "<game id>", "why": "...", "players": [{"team": "DSG", "vs": "CSS", "number": 10, "set": {"p3m": 1, "tov": 2}}]}
and is applied to the game AS STORED on the site (so its spelling, source and date stay), with the same rules (once, old copy kept, refused if the checks fail).
After the `set`, FG, REB and PTS of that player are recomputed from the 2P/3P/FT/OR/DR the patch leaves him, and the team total must still equal the players' points.
"team" is the code on the sheet; when an OCR sheet carries another code for that team, "vs" (the other team's code) finds it.
Live data is otherwise never touched by a deploy: this is only for a correction we decided to ship with a release.
"""
import datetime
import hashlib
import json
import sys

import config

FIXES_DIR = config.ASSETS_DIR / "game_fixes"
PATCHES_DIR = config.ASSETS_DIR / "game_patches"
STATE = config.DATA_DIR / "applied_fixes.json"


FIELDS = {"min", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "ast", "tov", "stl", "blk", "pf", "fd", "pm"}   # what a patch may change (FG, REB and PTS follow from them)


def patched(game, patch):
    """`game` (as stored) with the patch's player lines changed; (new game, None) or (None, why it cannot be done). `game` itself is left as it was."""
    game = json.loads(json.dumps(game))
    for ed in patch.get("players", []):
        t = next((t for t in game["teams"] if t["code"] == ed.get("team")), None)
        if t is None and ed.get("vs") in [x["code"] for x in game["teams"]]:
            t = next(x for x in game["teams"] if x["code"] != ed["vs"])
        if t is None:
            return None, f"team {ed.get('team')} is not in the game ({', '.join(x['code'] for x in game['teams'])})"
        rows = [p for p in t["players"] if p["number"] == ed.get("number") and not p.get("dnp")]
        if len(rows) != 1:
            return None, f"{t['code']} #{ed.get('number')}: {len(rows)} lines that played, expected one"
        bad = set(ed.get("set", {})) - FIELDS
        if bad or not ed.get("set"):
            return None, f"{t['code']} #{ed['number']}: cannot set {sorted(bad) or 'nothing'}"
        p = rows[0]
        p.update(ed["set"])
        p["fgm"], p["fga"] = p["p2m"] + p["p3m"], p["p2a"] + p["p3a"]
        p["reb"], p["pts"] = p["oreb"] + p["dreb"], 2 * p["p2m"] + 3 * p["p3m"] + p["ftm"]
    return game, None


def apply(fixes_dir=None, data_dir=None, patches_dir=None):
    """Apply the shipped fixes and patches that were not applied yet; returns the lines describing what happened (also printed to stderr when something was done).
    Called without folders it uses the ones that ship with the code; a test names its own."""
    if fixes_dir is None and patches_dir is None:
        patches_dir = PATCHES_DIR
    fixes_dir, data_dir = fixes_dir or FIXES_DIR, data_dir or config.DATA_DIR
    files = sorted(fixes_dir.glob("*.json")) if fixes_dir.exists() else []
    patches = sorted(patches_dir.glob("*.json")) if patches_dir and patches_dir.exists() else []
    if not files and not patches:
        return []
    from validate import validate
    state_file = data_dir / "applied_fixes.json"
    try:
        state = json.loads(state_file.read_text())
    except (OSError, ValueError):
        state = {}
    log = []
    for f in [*files, *patches]:
        raw = f.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()[:16]
        key = f.name if f.parent == fixes_dir else f"patch:{f.name}"
        if state.get(key, {}).get("hash") == digest:
            continue
        doc = json.loads(raw)
        gid = f.stem if key == f.name else doc.get("game")
        target = data_dir / "games" / f"{gid}.json"
        if key == f.name:
            game = doc
            problems = validate(game)
            if game.get("id") != f.stem:
                problems.append("id differs from the file name")
        elif target.exists():
            game, why = patched(json.loads(target.read_text()), doc)
            problems = [why] if why else validate(game)
        else:
            game, problems = None, []
        if problems:
            log.append(f"{key}: REFUSED ({'; '.join(problems)})")
            continue                                    # not remembered: it is tried again once the file is corrected
        if target.exists():
            old = target.read_text()
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            (data_dir / "games_replaced").mkdir(parents=True, exist_ok=True)
            (data_dir / "games_replaced" / f"{gid}-{stamp}.json").write_text(old)
            target.write_text(json.dumps(game, indent=1, ensure_ascii=False))
            state[key] = {"hash": digest, "result": "applied", "at": stamp}
            log.append(f"{key}: applied (the previous version is in games_replaced/)")
        else:
            state[key] = {"hash": digest, "result": "skipped: the game is not on this site"}
            log.append(f"{key}: skipped, the game is not on this site")
    data_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=1))
    if log:
        print("game_fixes:", *log, sep="\n  ", file=sys.stderr)
    return log
