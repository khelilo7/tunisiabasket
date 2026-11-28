"""Basketball stats web app. Run: python app.py  ->  http://localhost:5055"""
import os
import re
import threading
import time

from functools import partial

from flask import Flask, Response, abort, jsonify, make_response, redirect, request, send_from_directory
from flask import g as request_state

import auth
import config
import content
import cup
import fantasy
import finals
import health
import history
import records
import lineups
import livescore
import mvp
import nat1
import natteam
import notify
import plays
import predict
import rounds
import seo
import social
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
import archive  # noqa: E402  (a finished season, phase by phase)
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
    for _tab in seo.NAT1_TABS[_lang]:                  # Nationale 1: its table, games and calendar tabs have their own addresses
        app.add_url_rule(seo.path(_lang, "nat1", _tab), f"page_{_lang}_nat1_{_tab}", partial(_page_view, _lang, "nat1", _tab))
    app.add_url_rule(seo.path(_lang, "history", "<arg>"), f"page_{_lang}_history_season", partial(_page_view, _lang, "history"))      # /historique/2018-2019
    app.add_url_rule(seo.path(_lang, "natteam", "<arg>"), f"page_{_lang}_natteam_player", partial(_page_view, _lang, "natteam"))      # a called-up player who does not play in Tunisia
    app.add_url_rule(seo.path(_lang, "live", "<arg>"), f"page_{_lang}_live_game", partial(_page_view, _lang, "live"))      # the detail of one live game
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
        standings=[{**r, "box": counts.get(r["code"], 0)} for r in d["standings"]], status=public_status(), movement=finals.movement(force=request.args.get("move") == "1"),
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


@app.get("/api/plays")
def plays_view():
    """Play of the week: the latest week's clips (vote shares once you voted or the vote ended) and the earlier winners. ?vid= adds the caller's own vote."""
    r = jsonify(plays.view(str(request.args.get("vid", ""))[:80]))
    r.headers["Cache-Control"] = "no-store"
    return r


@app.post("/api/plays/vote")
def plays_vote():
    body = request.get_json(silent=True, force=True) or {}
    ok, why = plays.cast(request, str(body.get("week", ""))[:40], str(body.get("clip", ""))[:40], str(body.get("vid", ""))[:80])
    return jsonify(ok=ok, reason=why), (200 if ok else {"closed": 403, "network": 429, "already": 409}.get(why, 400))


@app.post("/api/push")
def push_register():
    """The app's notification choice: {token, level: all | team | none, team, lang, results, news, votes} (notify.py)."""
    ok, why = notify.register(request.get_json(silent=True, force=True) or {})
    return jsonify(ok=ok, reason=why), (200 if ok else 400)


@app.get("/photo/<pid>.jpg")
def player_photo(pid):
    """Photos uploaded from the admin panel (data/photos, outside the code so deployments never touch them)."""
    if not re.match(r"^[a-z0-9]+-\d+$", pid):
        abort(404)
    r = send_from_directory(config.DATA_DIR / "photos", f"{pid}.jpg", max_age=3600)
    return r


@app.get("/api/players")
def players():
    d = stats.build(request.args.get("season"), phase=request.args.get("phase") or None)
    return jsonify(season=d["season"], phases=d["phases"], phase=d["phase"], players=[slim(p) for p in d["players"]], leaders=stats.leaders(d["players"]))


@app.get("/api/players/<pid>")
def player(pid):
    whole = stats.build(request.args.get("season"))
    mine = next((p for p in whole["players"] if p["id"] == pid), None)
    if not mine:
        abort(404)
    played = sorted({r["phase"] for r in mine["log"] if r.get("phase")})
    phase = request.args.get("phase") if request.args.get("phase") in played else None      # a phase the player did not play shows the whole season
    d = stats.build(whole["season"], phase=phase) if phase else whole
    p = next(p for p in d["players"] if p["id"] == pid)
    fm = archive.finals_mvp(d["season"]) if archive.available(d["season"]) else None
    rank = [x["id"] for x in d["players"] if x["mvp_eligible"]]
    return jsonify(season=d["season"], phases=played, phase=phase, finals_mvp=bool(fm and fm["id"] == pid), rank=rank.index(pid) + 1 if pid in rank and not archive.available(d["season"]) else None,
                   of=len(rank), top_teams=d["top_teams"], player={**p, "splits": stats.player_splits(p["log"])}, national=natteam.for_player(pid))


@app.get("/api/games")
def games():
    d = stats.build(request.args.get("season"))
    allg = sorted([*d["games"], *d["partials"]], key=lambda g: (g["date"], g["id"]))      # one-team sheets are listed too, marked partial
    return jsonify(season=d["season"], games=[{
        "id": g["id"], "date": g["date"], "date_approx": g.get("date_approx"), "matchday": g.get("matchday"), "mvp": g["mvp"], "partial": bool(g.get("partial")),
        "teams": [{"code": t["code"], "name": t["name"], "points": t["points"], "won": t["won"]} for t in g["teams"]]}
        for g in reversed(allg)])


@app.get("/api/schedule")
def schedule():
    """Every matchday of the season in one list, for the mobile app: the results (with the box score's id when there is one, and its MVP) and the games still to play
    (with the date and time the admin set). `current` is the first matchday with a game left to play."""
    season = stats.build()["season"]
    box = {}
    for g in stats.build_all_games():
        if stats.season_of(g["date"]) == season and g.get("matchday_no"):
            box[(g["matchday_no"], frozenset(t["code"] for t in g["teams"]))] = g
    days = {}

    def add(md, home, away, hs, as_, played, date=None, time_=None):
        d = days.setdefault(md, {"matchday": md, "date": None, "games": []})
        b = box.get((md, frozenset((home, away))))
        for x in d["games"]:
            if (x["home"], x["away"]) == (home, away):
                x["time"] = x["time"] or time_
                x["date"] = x["date"] or date
                return
        d["games"].append({"home": home, "away": away, "home_score": hs, "away_score": as_, "played": played, "id": b["id"] if b else None,
                           "date": (b["date"] if b else None) or date, "time": time_, "mvp": b.get("mvp") if b else None})
    for r in stats.load_official().get("results") or []:
        add(r["matchday"], r["home"], r["away"], r["home_score"], r["away_score"], r["home_score"] is not None)
    plan = stats.planning()
    for md in plan["matchdays"]:
        days.setdefault(md["matchday"], {"matchday": md["matchday"], "date": None, "games": []})["date"] = md["date"]
        for g in md["games"]:
            add(md["matchday"], g["home"], g["away"], g["home_score"], g["away_score"], g["played"], g.get("game_date") or md["date"], g.get("time"))
    out = sorted(days.values(), key=lambda d: d["matchday"])
    for d in out:
        d["date"] = d["date"] or min((g["date"] for g in d["games"] if g["date"]), default=None)
    current = next((d["matchday"] for d in out if any(not g["played"] for g in d["games"])), out[-1]["matchday"] if out else None)
    r = jsonify(season=season, teams=plan["teams"], matchdays=out, current=current)
    r.headers["Cache-Control"] = "public, max-age=60"
    return r


@app.get("/api/games/<gid>")
def game(gid):
    g = next((g for g in stats.build_all_games() if g["id"] == gid), None)
    if not g:
        g = stats.partial_game(gid)          # a game for which only one team's sheet exists
        if not g:
            abort(404)
        return jsonify(g)
    pos = {p["id"]: p for p in stats.build(stats.season_of(g["date"]))["players"]}
    return jsonify({**g, "lineups": stats.game_lineups(g, pos), "records": records.for_game(gid)})


@app.get("/api/teams/<code>")
def team(code):
    v = stats.team_view(code.upper(), request.args.get("season"))
    if not v:
        abort(404)
    return jsonify(v)


@app.get("/api/archive/<season>")
def archive_season(season):
    """A finished season, phase by phase (archive.py): tables, series, the cup bracket, the Finals MVP."""
    v = archive.view(season)
    if not v:
        abort(404)
    return jsonify(v)


@app.get("/api/archive/<season>/teams/<code>")
def archive_team(season, code):
    v = archive.team(season, code.upper(), request.args.get("phase") or None)
    if not v:
        abort(404)
    return jsonify(v)


@app.get("/api/team-stats")
def team_stats_public():
    return jsonify(stats.team_stats(request.args.get("season")))


@app.get("/api/live")
def live():
    """Games the admin has made public while an analyst counts them (analytics.live_games): the Live page and the menu's live dot poll this."""
    games = analytics.live_games()
    games += livescore.live_games(skip={frozenset((g["home"], g["away"])) for g in games})   # scores read from the broadcast, unless an analyst already shows the game
    resp = jsonify(games=games, now=int(time.time()))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/api/livescore")
def livescore_push():
    """One reading of the broadcast's scoreboard from tools/live_reader.py (Authorization: Bearer <live-score token>). See livescore.py."""
    ip = auth.client_ip()
    if auth._locked_out(ip):
        return jsonify(error="too many failed attempts, wait a few minutes"), 429
    tok = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not livescore.verify(tok):
        with auth._lock:
            auth._fails.setdefault(ip, []).append(time.time())
        return jsonify(error="bad token"), 401
    g, err = livescore.push(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    return jsonify(game=g)


@app.post("/api/livescore/stop")
def livescore_stop():
    """The reader stopped following a game: it leaves the Live pages at once (same token as /api/livescore)."""
    ip = auth.client_ip()
    if auth._locked_out(ip):
        return jsonify(error="too many failed attempts, wait a few minutes"), 429
    tok = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not livescore.verify(tok):
        with auth._lock:
            auth._fails.setdefault(ip, []).append(time.time())
        return jsonify(error="bad token"), 401
    g, err = livescore.stop(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 404 if err == "no such game" else 400
    return jsonify(game=g)


@app.post("/api/livescore/scorer")
def livescore_scorer():
    """Who scored a basket, named from the commentator by the reader (--scorers): same token as /api/livescore. See livescore.scorer()."""
    ip = auth.client_ip()
    if auth._locked_out(ip):
        return jsonify(error="too many failed attempts, wait a few minutes"), 429
    tok = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    if not livescore.verify(tok):
        with auth._lock:
            auth._fails.setdefault(ip, []).append(time.time())
        return jsonify(error="bad token"), 401
    b, err = livescore.scorer(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 404 if err.startswith("no such") else 400
    return jsonify(basket=b)


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


@app.get("/api/nat1")
def nat1_view():
    """Nationale 1 (nat1.py): the table and the results by matchday. No stats: we only have results."""
    r = jsonify(nat1.view())
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/api/national-team")
def national_team():
    """The Tunisian national team (natteam.py): called-up players, results, next game, statistics, history."""
    r = jsonify(natteam.view())
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/api/national-team/called")
def national_team_called():
    """Ids of the players called up in the latest window: the small label shown next to their names."""
    r = jsonify(natteam.called_view())
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/api/competitions")
def competitions():
    """Which extra competitions exist (the page's switches show only those): the Cup once it has a bracket, the play-off / play-out once the ADMIN has announced them (until then the public site does not change),
    and the National One play-off once the admin has announced it."""
    fv = finals.view()
    return jsonify(archived=list(archive.SEASONS), cup=bool(cup.load()["rounds"]), finals=bool(fv["announced"]), started=bool(fv["announced"]), nat1=bool(nat1.load()["teams"]), nat1_playoff=bool(nat1.load()["playoff_on"]))


@app.get("/api/history")
def history_index():
    """Past seasons: every champion since 1955-56 and the seasons with a detail page (history.py)."""
    r = jsonify(history.index())
    r.headers["Cache-Control"] = "public, max-age=300"
    return r


# ---------------------------------------------------------------- Fantasy Pro A (hidden: 404 unless the server runs with FANTASY=1; fantasy.py)
def _fantasy_on():
    if not fantasy.enabled():
        abort(404)


@app.get("/api/fantasy/config")
def fantasy_config():
    _fantasy_on()
    return jsonify(fantasy.config_view())


@app.get("/api/fantasy/pool")
def fantasy_pool():
    _fantasy_on()
    return jsonify(players=fantasy.pool(), budget=fantasy.BUDGET)


@app.get("/api/fantasy/me")
def fantasy_me():
    _fantasy_on()
    return jsonify(fantasy.me(str(request.args.get("vid", ""))[:64]))


@app.post("/api/fantasy/team")
def fantasy_team():
    _fantasy_on()
    r = fantasy.save(request.get_json(silent=True) or {})
    return jsonify(r), (200 if r["ok"] else 400)


@app.post("/api/fantasy/league")
def fantasy_league():
    _fantasy_on()
    r = fantasy.league(request.get_json(silent=True) or {})
    return jsonify(r), (200 if r["ok"] else 400)


@app.get("/api/fantasy/ranking")
def fantasy_ranking():
    _fantasy_on()
    rows = fantasy.ranking(request.args.get("league"))
    return (jsonify(rows=rows), 200) if rows is not None else (jsonify(error="unknown league"), 404)


@app.get("/api/fantasy/player/<pid>")
def fantasy_player(pid):
    _fantasy_on()
    v = fantasy.player_view(pid)
    return (jsonify(v), 200) if v else (jsonify(error="unknown player"), 404)


@app.get("/api/fantasy/dream/<int:md>")
def fantasy_dream(md):
    _fantasy_on()
    return jsonify(md=md, team=fantasy.dream_team(md))


@app.get("/api/privacy")
def privacy_view():
    """The privacy policy (privacy.py) in the visitor's language: the page /confidentialite, /en/privacy, and the app's link."""
    import privacy
    r = jsonify(privacy.view(request.args.get("lang", "fr")))
    r.headers["Cache-Control"] = "public, max-age=3600"
    return r


@app.get("/api/records")
def records_view():
    """League records: best single-game performances (players, teams), best season averages, titles and streaks (records.py)."""
    r = jsonify(records.all_records())
    r.headers["Cache-Control"] = "public, max-age=120"
    return r


@app.get("/api/history/<season>")
def history_season(season):
    """One past season: its format, tables, series, results and the box scores the site holds."""
    v = history.view(season)
    if v is None:
        return jsonify(error="unknown season"), 404
    r = jsonify(v)
    r.headers["Cache-Control"] = "public, max-age=300"
    return r


@app.get("/api/cup")
def cup_view():
    """The Cup bracket (cup.py): rounds, ties with their clubs resolved, upsets, the champion."""
    r = jsonify(cup.view())
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/api/finals")
def finals_view():
    """The play-off and the play-out (finals.py), with the season's journey and the regular season as it stands."""
    r = jsonify(finals.view())
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/api/rank-history")
def rank_history():
    """The rank of every Pro A club after every matchday (the race chart of the Standings page)."""
    return jsonify(finals.rank_history())


@app.get("/api/social")
def social_links():
    """The club's social pages (social.py): what the footer and the home card show."""
    return jsonify(links=social.links())


@app.post("/api/follow")
def follow_club():
    """The club a visitor chose to follow (optional). Body {"team": "CA", "rid": <the browser's code>}; an empty team takes the choice back. Only a count per club is kept."""
    b = request.get_json(silent=True) or {}
    team = str(b.get("team") or "").upper()[:8]
    if team and team not in stats.load_official()["teams"]:
        return jsonify(ok=False, reason="unknown"), 422
    return jsonify(ok=traffic.follow(request, team, str(b.get("rid", ""))[:40]))


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


@app.post("/api/app/open")
def app_open():
    """The mobile app was opened (sent at most a few times a day). Anonymous: see traffic.app_open()."""
    body = request.get_json(silent=True, force=True) or {}
    try:
        traffic.app_open(request, str(body.get("vid", ""))[:80], str(body.get("platform", ""))[:10], str(body.get("version", ""))[:20])
    except Exception:           # statistics must never break the app
        pass
    return "", 204


CORS_POST = ("/api/fantasy/", "/api/predict/pick", "/api/round/vote", "/api/mvp/vote", "/api/plays/vote", "/api/push", "/api/app/open")


@app.before_request
def _clock():
    request_state.t0 = time.perf_counter()


@app.after_request
def _headers(resp):
    try:
        health.count(resp.status_code, time.perf_counter() - request_state.t0)      # requests, errors and response times for the Server tab
    except Exception:
        pass
    # The mobile app (mobile/) reads the public API; in its web preview that is another origin. Public data only: no credentials are ever allowed,
    # and the only cross-origin POSTs accepted are the app's anonymous ones (fantasy, fan votes, predictions, notification choice), keyed by the device's id.
    if request.path.startswith("/api/") and not request.path.startswith("/api/admin"):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST" if request.path.startswith(CORS_POST) else "GET"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
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
    notify.start()                     # push notifications of the app: new results, news, votes (PUSH=0 turns it off)
    health.start()                     # one machine/app health sample a minute for the admin's Server tab (HEALTH=0 turns it off)


if os.environ.get("APP_ENV") == "production":  # under gunicorn there is no __main__
    start_background()

if __name__ == "__main__":
    start_background()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5055)))
