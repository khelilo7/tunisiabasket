"""Corrections to games already on the site that travel with the code (assets/game_fixes/<game id>.json, each a complete game, same format as tools/send_games.py sends).

On start-up each fix file is applied ONCE (the file's name and content hash are remembered in data/applied_fixes.json):
  * the game it names must already exist in data/games, otherwise the fix is skipped for good (a copy of the site never gains a game this way);
  * the game as it was is first copied to data/games_replaced/<id>-<UTC time>.json, then replaced by the fix (same as sending the game again);
  * a fix that fails the site's consistency checks is refused and reported, never stored.
Changing the content of a fix file applies it again; a game sent or edited from the admin afterwards is NOT overwritten at the next start-up.
Live data is otherwise never touched by a deploy: this is only for a correction we decided to ship with a release.
"""
import datetime
import hashlib
import json
import sys

import config

FIXES_DIR = config.ASSETS_DIR / "game_fixes"
STATE = config.DATA_DIR / "applied_fixes.json"


def apply(fixes_dir=None, data_dir=None):
    """Apply the shipped fixes that were not applied yet; returns the lines describing what happened (also printed to stderr when something was done)."""
    fixes_dir, data_dir = fixes_dir or FIXES_DIR, data_dir or config.DATA_DIR
    files = sorted(fixes_dir.glob("*.json")) if fixes_dir.exists() else []
    if not files:
        return []
    from validate import validate
    state_file = data_dir / "applied_fixes.json"
    try:
        state = json.loads(state_file.read_text())
    except (OSError, ValueError):
        state = {}
    log = []
    for f in files:
        raw = f.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()[:16]
        if state.get(f.name, {}).get("hash") == digest:
            continue
        game, target = json.loads(raw), data_dir / "games" / f"{f.stem}.json"
        problems = validate(game)
        if problems or game.get("id") != f.stem:
            log.append(f"{f.name}: REFUSED ({'; '.join(problems) or 'id differs from the file name'})")
            continue                                    # not remembered: it is tried again once the file is corrected
        if target.exists():
            old = target.read_text()
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            (data_dir / "games_replaced").mkdir(parents=True, exist_ok=True)
            (data_dir / "games_replaced" / f"{f.stem}-{stamp}.json").write_text(old)
            target.write_text(json.dumps(game, indent=1, ensure_ascii=False))
            state[f.name] = {"hash": digest, "result": "applied", "at": stamp}
            log.append(f"{f.name}: applied (the previous version is in games_replaced/)")
        else:
            state[f.name] = {"hash": digest, "result": "skipped: the game is not on this site"}
            log.append(f"{f.name}: skipped, the game is not on this site")
    data_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=1))
    if log:
        print("game_fixes:", *log, sep="\n  ", file=sys.stderr)
    return log
