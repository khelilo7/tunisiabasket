"""Admin endpoints for the sources of a game (game_sources.py): list, compare, choose / mix, unlock, attach a duplicate file. Registered on the admin blueprint (admin login required)."""
from flask import jsonify, request

import auth
import game_sources as gs
from admin import _file_lock, bp


def init():
    """Nothing to do: importing this module registered its routes on the admin blueprint."""


@bp.get("/admin/api/game-sources")
def sources_list():
    return jsonify(games=gs.list_games(), duplicates=gs.duplicates())


@bp.get("/admin/api/game-sources/<gid>")
def sources_compare(gid):
    try:
        return jsonify(gs.compare(gid))
    except (KeyError, ValueError):
        return jsonify(error="This game has no sources."), 404


@bp.post("/admin/api/game-sources/<gid>/publish")
def sources_publish(gid):
    """Body {"base": source id, "picks": {"TEAM|NUMBER|stat": source id}, "lock": true, "force": false}: publish that source, or the mix. 422 with `problems` when the result fails the consistency checks."""
    b = request.get_json(silent=True) or {}
    picks = b.get("picks") if isinstance(b.get("picks"), dict) else {}
    try:
        with _file_lock:
            game, problems = gs.publish(gid, str(b.get("base") or ""), picks, lock=b.get("lock", True) is not False, force=bool(b.get("force")))
    except KeyError:
        return jsonify(error="This game has no sources."), 404
    except (ValueError, TypeError) as e:
        return jsonify(error=str(e)), 422
    if game is None:
        return jsonify(error="The mixed game fails the consistency checks.", problems=problems), 422
    auth.audit("game-sources", f"{gid} {b.get('base')} +{len(picks)} pick(s)")
    return jsonify(ok=True, message=("Mixed version published." if picks else "Version published.") + (" The game is locked: later pushes are kept as sources only." if b.get("lock", True) is not False else ""),
                   problems=problems, **gs.compare(gid))


@bp.post("/admin/api/game-sources/<gid>/unlock")
def sources_unlock(gid):
    try:
        with _file_lock:
            gs.unlock(gid)
    except KeyError:
        return jsonify(error="This game has no sources."), 404
    auth.audit("game-sources", f"{gid} unlocked")
    return jsonify(ok=True, message="Unlocked: the next version sent for this game is published as before.", **gs.compare(gid))


@bp.post("/admin/api/game-sources/<gid>/attach")
def sources_attach(gid):
    """Body {"from": other game id}: that game file becomes one more source of this game and leaves the site."""
    other = str((request.get_json(silent=True) or {}).get("from") or "")
    try:
        with _file_lock:
            gs.attach(gid, other)
    except (ValueError, OSError) as e:
        return jsonify(error=str(e)), 422
    auth.audit("game-sources", f"{other} attached to {gid}")
    return jsonify(ok=True, message="Attached: the other file is now a source of this game.", **gs.compare(gid))
