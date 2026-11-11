"""Basketball stats web app. Run: python app.py  ->  http://localhost:5055"""
import os
import re
import threading
import time

from functools import partial

from flask import Flask, Response, abort, jsonify, make_response, redirect, request, send_from_directory

import auth
import config
import content
import lineups
import mvp
import predict
import rounds
import seo
import stats
import traffic

app = Flask(__name__, static_folder="static", static_url_path="")
if os.environ.get("BEHIND_PROXY") == "1":  # Caddy/nginx in front: trust its X-Forwarded-Proto so cookies get the Secure flag
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # admin uploads (PDF/image stacks, ZIPs)
import admin  # noqa: E402  (registers the /admin tool)
app.register_blueprint(admin.bp)
import analytics  # noqa: E402  (/analytics: analysts count games by hand; the admin approves them)
app.register_blueprint(analytics.bp)
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


def _page_view(lang, page, arg=None):
    """Every public page URL: the single-page app plus the head tags and crawler content for that exact URL."""
    m = seo.meta(lang, page, arg)
    if m is None:
        resp = make_response(seo.shell(lang, "home", seo.not_found_meta(lang)), 404)
    else:
        if page == "player" and m["redirect_arg"] and arg != m["redirect_arg"]:
            return redirect(seo.path(lang, "player", m["redirect_arg"]), 301)   # one canonical URL per player
        if page == "team" and arg != m["arg"]:
            return redirect(seo.path(lang, "team", m["arg"]), 301)
        resp = make_response(seo.shell(lang, page, m))
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp


for _lang in seo.LANGS:   # French: /, /classement, /equipe/CA ...   English: /en/, /en/standings, /en/team/CA ...
    for _page in seo.LIST_PAGES:
        app.add_url_rule(seo.path(_lang, _page), f"page_{_lang}_{_page}", partial(_page_view, _lang, _page))
    for _page in seo.ITEM_PAGES:
        app.add_url_rule(seo.path(_lang, _page, "<arg>"), f"page_{_lang}_{_page}", partial(_page_view, _lang, _page))


def _redirect_to(lang, page, arg=None):
    return redirect(seo.path(lang, page, arg), 301)


# Addresses used before French became the default: /fr/equipe/CA -> /equipe/CA and /team/CA -> /en/team/CA
for _page in seo.LIST_PAGES:
    app.add_url_rule("/fr/" if _page == "home" else "/fr" + seo.path("fr", _page), f"old_fr_{_page}", partial(_redirect_to, "fr", _page))
    if _page != "home":
        app.add_url_rule("/" + seo.SLUGS["en"][_page], f"old_en_{_page}", partial(_redirect_to, "en", _page))
for _page in seo.ITEM_PAGES:
    app.add_url_rule("/fr" + seo.path("fr", _page, "<arg>"), f"old_fr_{_page}", partial(_redirect_to, "fr", _page))
    app.add_url_rule("/" + seo.SLUGS["en"][_page] + "/<arg>", f"old_en_{_page}", partial(_redirect_to, "en", _page))


@app.get("/index.html")
def raw_template():
    return redirect("/", 301)   # the file holds template tokens: never show or index it


@app.get("/sitemap.xml")
def sitemap():
    return Response(seo.sitemap_xml(), mimetype="application/xml", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/robots.txt")
def robots():
    return Response(seo.robots_txt(), mimetype="text/plain", headers={"Cache-Control": "public, max-age=3600"})


def _phase_summary():
    r = mvp.race(1)
    keep = ("id", "name", "team", "number", "pos", "gp", "pts", "reb", "ast", "stl", "blk", "pir", "impact", "votes", "vote_share", "photo")
    pick = lambda c: {k: c[k] for k in keep} if c else None
    by = {c["id"]: c for c in r["candidates"]}
    return {"phase": 1, "complete": r["complete"], "voting_open": r["voting_open"], "deadline_ts": r["deadline_ts"], "total_votes": r["total_votes"],
            "winner": pick(r["winner"]), "leader": pick(r["leader"]), "vote_leader": pick(r["vote_leader"]),
            "current": pick(r["current"]), "current_by": r["current_by"],
            "ballot": [pick(by[i]) for i in r["ballot_ranked"] if i in by]}


@app.get("/api/overview")
def overview():
    d = stats.build(request.args.get("season"))
    pool = [p for p in d["players"] if p["mvp_eligible"]]
    counts = stats.box_counts(d["games"], d["partials"])
    return jsonify(
        season=d["season"], seasons=d["seasons"], games=len(d["games"]), players=len(d["players"]),
        mvp=({**slim(pool[0]), "photo": stats.load_photos().get(pool[0]["id"])} if pool else None),
        phase_mvp=_phase_summary(), top=[slim(p) for p in pool[:5]], top_teams=d["top_teams"], leaders=stats.leaders(d["players"]),
        facts={"games": len(d["games"]), "avg_points": round(sum(t["points"] for g in d["games"] for t in g["teams"]) / (2 * len(d["games"]) or 1), 1)},
        recent=[{k: g.get(k) for k in ("id", "date", "date_approx", "matchday", "mvp", "score_note")} | {
            "teams": [{"code": t["code"], "name": t["name"], "points": t["points"]} for t in g["teams"]]}
            for g in reversed(d["games"][-6:])],
        standings=[{**r, "box": counts.get(r["code"], 0)} for r in d["standings"]], status=public_status(),
    )


@app.get("/api/home")
def home_data():
    """What the home page needs besides the calendar: the latest results (box scores and hand-entered results) and the latest news."""
    d = stats.build()
    rv = rounds.view()
    r = jsonify(recent=content.recent_results(6, d), news=content.load_news(4), facebook=content.FACEBOOK, standings=d["standings"], phase_mvp=_phase_summary(),
                round_vote=rv if rv.get("round") else None)
    r.headers["Cache-Control"] = "no-cache"          # a result or a news item saved in the admin shows at once
    return r


@app.get("/api/news")
def news_public():
    r = jsonify(items=content.load_news(request.args.get("limit", type=int) or None), labels=list(content.LABELS))
    r.headers["Cache-Control"] = "no-cache"
    return r


def _phase_arg():
    try:
        ph = int(request.args.get("phase") or (request.get_json(silent=True) or {}).get("phase") or 1)
    except (TypeError, ValueError):
        abort(400)
    if ph not in mvp.PHASES:
        abort(404)
    return ph


@app.get("/api/mvp")
def mvp_race():
    """The phase MVP race: candidates, scores, fan votes, race chart, winner. ?vid= adds the caller's own vote."""
    ph = _phase_arg()
    out = mvp.race(ph)
    out["my_vote"] = mvp.my_vote(ph, request.args.get("vid", ""))
    return jsonify(out)


@app.get("/api/round")
def round_view():
    """Player of the round: the vote that is open (or just ended) with the fans' shares, and the winners of earlier rounds. ?vid= adds the caller's own vote."""
    r = jsonify(rounds.view(request.args.get("vid", "")))
    r.headers["Cache-Control"] = "no-store"
    return r


@app.post("/api/round/vote")
def round_vote():
    body = request.get_json(silent=True, force=True) or {}
    try:
        md = int(body.get("round"))
    except (TypeError, ValueError):
        abort(400)
    ok, why = rounds.cast(request, md, str(body.get("player", ""))[:40], str(body.get("vid", ""))[:80])
    return jsonify(ok=ok, reason=why), (200 if ok else {"closed": 403, "network": 429, "already": 409}.get(why, 400))


@app.post("/api/mvp/vote")
def mvp_vote():
    body = request.get_json(silent=True, force=True) or {}
    ph = _phase_arg()
    ok, why = mvp.cast(request, ph, str(body.get("player", ""))[:40], str(body.get("vid", ""))[:80])
    return jsonify(ok=ok, reason=why), (200 if ok else {"closed": 403, "network": 429, "already": 409}.get(why, 400))


@app.get("/api/predict")
def predict_view():
    r = jsonify(predict.view(str(request.args.get("vid", ""))[:80]))
    r.headers["Cache-Control"] = "no-store"          # personal: what I picked, what I may see
    return r


@app.post("/api/predict/pick")
def predict_pick():
    body = request.get_json(silent=True, force=True) or {}
    ok, why = predict.cast(request, str(body.get("game", ""))[:60], str(body.get("side", ""))[:2], str(body.get("vid", ""))[:80])
    r = jsonify(ok=ok, reason=why)
    r.status_code = 200 if ok else {"closed": 403, "network": 429, "already": 409}.get(why, 400)
    return r


@app.get("/photo/<pid>.jpg")
def player_photo(pid):
    """Photos uploaded from the admin panel (data/photos, outside the code so deployments never touch them)."""
    if not re.match(r"^[a-z0-9]+-\d+$", pid):
        abort(404)
    r = send_from_directory(config.DATA_DIR / "photos", f"{pid}.jpg", max_age=3600)
    return r


@app.get("/api/players")
def players():
    d = stats.build(request.args.get("season"))
    return jsonify(season=d["season"], players=[slim(p) for p in d["players"]], leaders=stats.leaders(d["players"]))


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
    allg = sorted([*d["games"], *d["partials"]], key=lambda g: (g["date"], g["id"]))      # one-team sheets are listed too, marked partial
    return jsonify(season=d["season"], games=[{
        "id": g["id"], "date": g["date"], "date_approx": g.get("date_approx"), "matchday": g.get("matchday"), "mvp": g["mvp"], "partial": bool(g.get("partial")),
        "teams": [{"code": t["code"], "name": t["name"], "points": t["points"], "won": t["won"]} for t in g["teams"]]}
        for g in reversed(allg)])


@app.get("/api/games/<gid>")
def game(gid):
    g = next((g for g in stats.build_all_games() if g["id"] == gid), None)
    if not g:
        g = stats.partial_game(gid)          # a game for which only one team's sheet exists
        if not g:
            abort(404)
        return jsonify(g)
    pos = {p["id"]: p for p in stats.build(stats.season_of(g["date"]))["players"]}
    return jsonify({**g, "lineups": stats.game_lineups(g, pos)})


@app.get("/api/teams/<code>")
def team(code):
    v = stats.team_view(code.upper(), request.args.get("season"))
    if not v:
        abort(404)
    return jsonify(v)


@app.get("/api/team-stats")
def team_stats_public():
    return jsonify(stats.team_stats(request.args.get("season")))


@app.get("/api/matchup")
def matchup():
    """Head-to-head preview of two teams from the games played so far (used by the next-games banner)."""
    m = stats.matchup(str(request.args.get("home", "")).upper(), str(request.args.get("away", "")).upper(), request.args.get("season"))
    if not m:
        abort(404)
    return jsonify(m)


@app.get("/api/lineups")
def lineups_view():
    """The EXPECTED starting five of both teams of a game (lineups.py): players the admin marked as absent are left out. Used by the next-games banner."""
    home, away = str(request.args.get("home", "")).upper(), str(request.args.get("away", "")).upper()
    if not re.fullmatch(r"[A-Z0-9]{2,6}", home) or not re.fullmatch(r"[A-Z0-9]{2,6}", away) or home == away:
        abort(404)
    r = jsonify(lineups.view(stats.build(), home, away))
    r.headers["Cache-Control"] = "no-store"          # follows the admin's absences at once
    return r


@app.get("/api/planning")
def planning():
    plan = stats.planning()
    plan["banner"] = stats.banner(plan)          # what the home banner shows today (Tunisian date): next games, or the results of the matchday that has just been played
    r = jsonify(plan)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.post("/api/sync")
def sync_now():
    auth.require_admin()  # only the admin may trigger a sync
    auth.audit("sync")
    threading.Thread(target=run_sync, daemon=True).start()
    return jsonify(started=True)


@app.post("/api/hit")
def hit():
    """Page-view beacon sent by the site itself (see traffic.py: no cookies, nothing personal stored)."""
    body = request.get_json(silent=True, force=True) or {}
    try:
        traffic.record(request, str(body.get("path", ""))[:200], str(body.get("ref", ""))[:300], str(body.get("lang", ""))[:5], str(body.get("rid", ""))[:40])
    except Exception:           # statistics must never break the site
        pass
    return "", 204


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
