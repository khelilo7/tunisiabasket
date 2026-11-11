"""Admin endpoints for editorial content: game schedule (time, date, featured rank), hand-entered results with optional stats, and news.
Registered on the admin blueprint (every route needs the admin login, like the rest of the panel)."""
from flask import jsonify, request

import absences
import auth
import content
import stats
from admin import _add_result, _check_results, _file_lock, _official, _write_official, bp


def init():
    """Nothing to do: importing this module registered its routes on the admin blueprint."""


@bp.get("/admin/api/schedule")
def schedule_view():
    """The calendar with the admin's overlay: per game the key, kick-off time, own date, featured rank, result and optional stats."""
    plan = stats.planning()
    notes = content.load_notes()
    for m in plan["matchdays"]:
        for g in m["games"]:
            g["notes"] = notes.get(g["key"]) or notes.get(f"{m['matchday']}:{g['away']}-{g['home']}")
    return jsonify(season=stats.load_official().get("season"), teams=plan["teams"], matchdays=plan["matchdays"], labels=list(content.LABELS))


@bp.post("/admin/api/schedule")
def schedule_save():
    """Body {key, time, date, featured}: empty fields are cleared."""
    b = request.get_json(silent=True) or {}
    try:
        entry = content.set_schedule(str(b.get("key") or ""), b.get("time"), b.get("date"), b.get("featured"))
    except (ValueError, TypeError) as e:
        return jsonify(error=str(e) or "Invalid value."), 422
    auth.audit("schedule", f"{b.get('key')} {entry}")
    return jsonify(ok=True, entry=entry)


@bp.post("/admin/api/result")
def result_save():
    """Body {matchday, home, away, home_score, away_score, note, players: [{name, team, pts, reb, ast, stl, blk}]}.
    Writes the official result (standings, latest games and the calendar update at once); the stats are optional extras shown with the result."""
    b = request.get_json(silent=True) or {}
    try:
        md = int(b.get("matchday"))
        game = {"home": str(b.get("home") or ""), "away": str(b.get("away") or ""), "home_score": int(b.get("home_score")), "away_score": int(b.get("away_score"))}
    except (TypeError, ValueError):
        return jsonify(error="Matchday and both scores are required numbers."), 422
    if not 1 <= md <= 60:
        return jsonify(error="Enter the matchday number (1-60)."), 422
    players = b.get("players") or []
    if not isinstance(players, list) or any(str(p.get("team") or game["home"]) not in (game["home"], game["away"]) for p in players if isinstance(p, dict)):
        return jsonify(error="Each stat line belongs to one of the two teams."), 422
    with _file_lock:
        o = _official()
        errs = _check_results([game], o, md)
        if errs:
            return jsonify(error="; ".join(errs)), 422
        try:
            content.set_notes(content.game_key(md, game["home"], game["away"]), b.get("note"), [p for p in players if isinstance(p, dict)])
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e) or "Invalid stats."), 422
        how = _add_result(o, md, game["home"], game["away"], game["home_score"], game["away_score"])
        _write_official(o)
    auth.audit("result", f"J{md} {game['home']} {game['home_score']}-{game['away_score']} {game['away']} ({how})")
    return jsonify(ok=True, message=f"Result {how}: {game['home']} {game['home_score']} – {game['away_score']} {game['away']}. The home page, the calendar and the standings show it now.")


@bp.get("/admin/api/news")
def news_list():
    return jsonify(items=content.load_news(), labels=list(content.LABELS))


@bp.post("/admin/api/news")
def news_save():
    try:
        item = content.save_news(request.get_json(silent=True) or {})
    except (ValueError, TypeError) as e:
        return jsonify(error=str(e) or "Invalid value."), 422
    auth.audit("news", f"{item['id']} {item['label']}: {item['title'][:40]}")
    return jsonify(ok=True, item=item)


@bp.post("/admin/api/news/delete")
def news_delete():
    nid = (request.get_json(silent=True) or {}).get("id")
    n = content.delete_news(nid)
    auth.audit("news-delete", str(nid))
    return jsonify(ok=bool(n))


@bp.get("/admin/api/absences")
def absences_view():
    """Players marked as not playing: {player id: {note, since}}. They are left out of the expected starting five on the home page."""
    return jsonify(absences=absences.load())


@bp.post("/admin/api/absences")
def absences_save():
    """Body {id, absent: true|false, note}: mark a player as not playing (injured, suspended...) or put him back."""
    b = request.get_json(silent=True) or {}
    pid = str(b.get("id") or "")
    if pid not in {p["id"] for p in stats.build()["players"]}:
        return jsonify(error="Unknown player."), 422
    cur = absences.set_absent(pid, bool(b.get("absent")), b.get("note") or "")
    auth.audit("absence", f"{pid} {'out' if pid in cur else 'back'}")
    return jsonify(ok=True, absences=cur)
