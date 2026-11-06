"""Basketball stats web app. Run: python app.py  ->  http://localhost:5055"""
import os
import threading
import time

from flask import Flask, abort, jsonify, request, send_from_directory

import auth
import stats

app = Flask(__name__, static_folder="static", static_url_path="")
if os.environ.get("BEHIND_PROXY") == "1":  # Caddy/nginx in front: trust its X-Forwarded-Proto so cookies get the Secure flag
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # admin uploads (PDF/image stacks, ZIPs)
import admin  # noqa: E402  (registers the /admin tool)
app.register_blueprint(admin.bp)
SYNC_EVERY_MIN = float(os.environ.get("SYNC_INTERVAL_MIN", "10"))
status = {"running": False, "last": None, "error": None, "enabled": True}
_lock = threading.Lock()


def run_sync():
    import shutil
    if not shutil.which("tesseract"):
        status["error"] = "Tesseract is not installed (brew install tesseract): scanned PDFs cannot be read."
        return
    if not _lock.acquire(blocking=False):
        return
    try:
        import drive_sync
        status.update(running=True, error=None)
        status["last"] = drive_sync.sync(log=app.logger.info)
    except Exception as e:
        status["error"] = str(e)
    finally:
        status["running"] = False
        _lock.release()


def _loop():
    while True:
        run_sync()
        time.sleep(SYNC_EVERY_MIN * 60)


def slim(p):
    return {k: v for k, v in p.items() if k != "log"}


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/overview")
def overview():
    d = stats.build(request.args.get("season"))
    pool = [p for p in d["players"] if p["mvp_eligible"]]
    counts = stats.box_counts(d["games"])
    return jsonify(
        season=d["season"], seasons=d["seasons"], games=len(d["games"]), players=len(d["players"]),
        mvp=slim(pool[0]) if pool else None,
        top=[slim(p) for p in pool[:5]], top_teams=d["top_teams"],
        recent=[{k: g.get(k) for k in ("id", "date", "date_approx", "matchday", "mvp", "score_note")} | {
            "teams": [{"code": t["code"], "name": t["name"], "points": t["points"]} for t in g["teams"]]}
            for g in reversed(d["games"][-6:])],
        standings=[{**r, "box": counts.get(r["code"], 0)} for r in d["standings"]], status=public_status(),
    )


@app.get("/api/players")
def players():
    d = stats.build(request.args.get("season"))
    return jsonify(season=d["season"], players=[slim(p) for p in d["players"]])


@app.get("/api/players/<pid>")
def player(pid):
    d = stats.build(request.args.get("season"))
    p = next((p for p in d["players"] if p["id"] == pid), None)
    if not p:
        abort(404)
    rank = [x["id"] for x in d["players"] if x["mvp_eligible"]]
    return jsonify(season=d["season"], rank=rank.index(pid) + 1 if pid in rank else None,
                   of=len(rank), top_teams=d["top_teams"], player=p)


@app.get("/api/games")
def games():
    d = stats.build(request.args.get("season"))
    return jsonify(season=d["season"], games=[{
        "id": g["id"], "date": g["date"], "date_approx": g.get("date_approx"), "matchday": g.get("matchday"), "mvp": g["mvp"],
        "teams": [{"code": t["code"], "name": t["name"], "points": t["points"], "won": t["won"]} for t in g["teams"]]}
        for g in reversed(d["games"])])


@app.get("/api/games/<gid>")
def game(gid):
    g = next((g for g in stats.build_all_games() if g["id"] == gid), None)
    if not g:
        abort(404)
    pos = {p["id"]: p for p in stats.build(stats.season_of(g["date"]))["players"]}
    return jsonify({**g, "lineups": stats.game_lineups(g, pos)})


@app.get("/api/teams/<code>")
def team(code):
    v = stats.team_view(code.upper(), request.args.get("season"))
    if not v:
        abort(404)
    return jsonify(v)


@app.get("/api/planning")
def planning():
    return jsonify(stats.planning())


@app.post("/api/sync")
def sync_now():
    auth.require_admin()  # only the admin may trigger a sync
    auth.audit("sync")
    threading.Thread(target=run_sync, daemon=True).start()
    return jsonify(started=True)


@app.after_request
def _headers(resp):
    return auth.add_security_headers(resp)


def public_status():
    """What visitors may see: no error text, paths or counts from the admin side."""
    last = status["last"] or {}
    return {"running": status["running"], "last_sync": last.get("at")}


@app.get("/api/status")
def get_status():
    if not auth.is_admin():
        return jsonify(public_status())
    review = stats.GAMES_DIR.parent / "review"
    return jsonify(**status, review=len(list(review.glob("*.json"))) if review.exists() else 0)


_started = False


def start_background():
    """Auto-sync from Google Drive every SYNC_INTERVAL_MIN minutes (idempotent)."""
    global _started
    if not _started and os.environ.get("AUTO_SYNC", "1") == "1":
        _started = True
        threading.Thread(target=_loop, daemon=True).start()


if os.environ.get("APP_ENV") == "production":  # under gunicorn there is no __main__
    start_background()

if __name__ == "__main__":
    start_background()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5055)))
