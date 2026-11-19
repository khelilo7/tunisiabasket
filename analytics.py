"""Analytics: a role that counts a game by hand while watching it (/analytics), and the admin's approval before anything reaches the public site.

An analyst signs in with their own token (data/analytics_token.json, a salted scrypt hash, or ANALYTICS_TOKEN in the environment). That token opens /analytics and
nothing else: it never works on /admin (a logged-in admin can use /analytics too). The analyst clicks a button per action (+1 / +2 / +3, missed shots, rebounds,
assists...) on the players the site already knows, and every click is one event saved in data/analytics/<game>.json. They can download the box score, or send the
game for approval.

Every analyst signs in with a NAME as well as the token: each action is stamped with it, and two analysts with two names each get their own version of a game (the
admin sees and edits every version, and approves one). Nothing an analyst enters is public. When the admin approves a game, it is published as TWO one-team sheets in data/partial_games.json (stats.py, "One-team box
scores"): the same safe path as the hand-kept sheets, so minutes, +/- and fouls drawn stay unknown (never 0), the game never enters standings, team totals, the MVP
race or the fan vote, and a real box score of the same game replaces it. A sheet is ignored until the official result of that matchday exists.
"""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import threading
import time
import unicodedata

from flask import Blueprint, abort, jsonify, request, send_from_directory

import auth
import config
import lineups
import stats

bp = Blueprint("analytics", __name__)
DIR = config.DATA_DIR / "analytics"
TOKEN_FILE = config.DATA_DIR / "analytics_token.json"
PARTIAL_FILE = config.DATA_DIR / "partial_games.json"
COOKIE = "proa_analyst"
SESSION_HOURS = 12
MAX_EVENTS = 6000
LOG_MAX = 4000                              # entries of a game's change log
STATS = ("ft_m", "p2_m", "p3_m", "ft_x", "p2_x", "p3_x", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "fd", "tf", "inj", "ej")
# what belongs to a team, not to a player (the sheet's "Team / Coach" row): team rebounds, a team turnover, a timeout, a technical foul on the coach or the bench. Stored like a lineup:
# pid None and "team": the code.
TEAM_STATS = ("t_oreb", "t_dreb", "t_tov", "timeout", "tf_c", "tf_b")
POINTS = {"ft_m": 1, "p2_m": 2, "p3_m": 3}
# Tags on a made shot, one tap each after the basket (the team lines of a box score): in the paint (2-pointers only), second-chance points, fast-break points, points off a turnover.
TAGS = {"p2_m": ("paint", "second", "fast", "tov"), "p3_m": ("second", "fast", "tov"), "ft_m": ("second", "fast", "tov")}
TAG_KEY = {"paint": "paint", "second": "second", "fast": "fast", "tov": "tov_pts"}          # tag -> the key of the team line (team_extra.py)
TAG_LABEL = {"paint": "in the paint", "second": "second chance", "fast": "fast break", "tov": "off a turnover"}
OPEN_STATES = ("open", "rejected")           # the analyst may still count
PUBLIC = {"analytics.page", "analytics.login_route", "analytics.me"}

_sessions: dict[str, dict] = {}           # session id -> {"exp", "name", "slug"}
_lock = threading.Lock()
_file_lock = threading.Lock()


# ---------------------------------------------------------------- token and sessions (same rules as the admin's: hash on disk, lockout, HttpOnly cookie)
def set_token(token: str):
    config.DATA_DIR.mkdir(exist_ok=True)
    salt = secrets.token_bytes(16)
    TOKEN_FILE.write_text(json.dumps({"salt": salt.hex(), "hash": auth._hash(token, salt), "created": time.strftime("%Y-%m-%d %H:%M:%S")}))
    os.chmod(TOKEN_FILE, 0o600)
    with _lock:
        _sessions.clear()                      # a new token logs every analyst out


def token_configured() -> bool:
    return bool(os.environ.get("ANALYTICS_TOKEN")) or TOKEN_FILE.exists()


def _verify(token: str) -> bool:
    token = (token or "").strip()
    env = os.environ.get("ANALYTICS_TOKEN")
    if env:
        return hmac.compare_digest(token.encode(), env.encode())
    try:
        d = json.loads(TOKEN_FILE.read_text())
    except (OSError, ValueError):
        return False
    return hmac.compare_digest(auth._hash(token.upper(), bytes.fromhex(d["salt"])), d["hash"])


NAME_RE = re.compile(r"[\w .'\-]{2,30}")


def clean_name(v):
    """The analyst's name as typed (2-30 letters, digits, spaces . ' -), or None."""
    v = " ".join(str(v or "").split())
    return v if NAME_RE.fullmatch(v) and re.search(r"\w", v) else None


def name_slug(name):
    """A short ASCII key for a name, so 'Ali' and 'ali' are one analyst; a name with no latin letters (Arabic...) gets a key from its hash."""
    s = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()).strip("-")[:24]
    return s if len(s) >= 2 else "a" + hashlib.sha1(name.lower().encode()).hexdigest()[:8]


def _session():
    sid = request.cookies.get(COOKIE)
    if sid:
        with _lock:
            s = _sessions.get(sid)
            if s and s["exp"] > time.time():
                return s
            _sessions.pop(sid, None)
    return None


def is_analyst() -> bool:
    """A signed-in analyst, or the admin (who may do everything an analyst does)."""
    return bool(_session()) or auth.is_admin()


def who():
    """(name, key) of whoever is making the request: "Admin", or the analyst's name given at sign-in. Every action is stamped with it."""
    if auth.is_admin():
        return "Admin", "admin"
    s = _session()
    return (s["name"], s["slug"]) if s else (None, None)


@bp.before_request
def _guard():
    if request.endpoint in PUBLIC:
        return None
    if request.method not in ("GET", "HEAD", "OPTIONS") and not auth.same_origin_ok():
        auth.audit("csrf-blocked", request.path)
        abort(403, "Cross-site request refused.")
    if request.path.startswith("/admin/"):
        return auth.require_admin()            # approving is the admin's, never an analyst's
    if not is_analyst():
        abort(401, "Analyst login required.")


@bp.get("/analytics")
def page():
    return send_from_directory("static", "analytics.html")


@bp.post("/analytics/api/login")
def login_route():
    if not auth.same_origin_ok():
        abort(403)
    body = request.get_json(silent=True) or {}
    ip, token = auth.client_ip(), body.get("token", "")
    name = clean_name(body.get("name"))
    if not name:
        return jsonify(error="Enter your name (2 to 30 letters): every action you make is stamped with it."), 422
    wait = auth._locked_out(ip)
    if wait:
        auth.audit("analytics-login-blocked", f"locked for {wait}s")
        return jsonify(error=f"Too many wrong attempts. Try again in {wait // 60 + 1} minute(s)."), 429
    if not token_configured():
        return jsonify(error="No analytics token is set yet."), 503
    if not _verify(token):
        with auth._lock:
            auth._fails.setdefault(ip, []).append(time.time())
        time.sleep(0.6)
        auth.audit("analytics-login-failed")
        return jsonify(error="Wrong token."), 401
    sid = secrets.token_urlsafe(32)
    with _lock:
        now = time.time()
        for k in [k for k, v in _sessions.items() if v["exp"] < now]:
            del _sessions[k]
        _sessions[sid] = {"exp": now + SESSION_HOURS * 3600, "name": name, "slug": name_slug(name)}
    auth.audit("analytics-login-ok", name)
    resp = jsonify(ok=True)
    resp.set_cookie(COOKIE, sid, max_age=SESSION_HOURS * 3600, httponly=True, samesite="Strict", secure=request.is_secure, path="/")
    return resp


@bp.post("/analytics/api/logout")
def logout_route():
    with _lock:
        _sessions.pop(request.cookies.get(COOKIE), None)
    resp = jsonify(ok=True)
    resp.delete_cookie(COOKIE, path="/")
    return resp


@bp.get("/analytics/api/me")
def me():
    name, _ = who()
    return jsonify(analyst=is_analyst(), configured=token_configured(), name=name, admin=auth.is_admin())


# ---------------------------------------------------------------- games (data/analytics/<id>.json)
def _path(gid):
    if not re.fullmatch(r"[a-z0-9-]{3,60}", gid or ""):
        abort(404)
    return DIR / f"{gid}.json"


def _load(gid):
    try:
        return json.loads(_path(gid).read_text())
    except (OSError, ValueError):
        abort(404)


def _mine(g):
    _, slug = who()
    return auth.is_admin() or not g.get("analyst_slug") or g["analyst_slug"] == slug      # a game from before names existed stays open to every analyst


def _load_mine(gid):
    g = _load(gid)
    if not _mine(g):
        abort(404)                                  # somebody else's version does not exist for you
    return g


def _save(game):
    DIR.mkdir(parents=True, exist_ok=True)
    p = _path(game["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(game, ensure_ascii=False, indent=1))
    tmp.replace(p)


def tally(game):
    """{player id: {stat: count}}"""
    t = {}
    for e in game["events"]:
        if e["stat"] == "lineup" or e.get("pid") is None:
            continue                                   # who is on the court is not a statistic (see court()); a team event belongs to no player (see team_tally())
        r = t.setdefault(e["pid"], {})
        r[e["stat"]] = r.get(e["stat"], 0) + 1
    return t


def team_tally(game):
    """{team: {stat: count}} of the team events (team rebounds and turnovers, timeouts, technical fouls on the coach or the bench)."""
    out = {c: {} for c in game["players"]}
    for e in game["events"]:
        if e.get("pid") is None and e["stat"] in TEAM_STATS and e.get("team") in out:
            out[e["team"]][e["stat"]] = out[e["team"]].get(e["stat"], 0) + 1
    return out


def qlen(q):
    return 300 if q > 4 else 600                       # quarters of 10 minutes, overtimes of 5


def elapsed(q, left):
    """Seconds of game time played when quarter q has `left` seconds on the clock."""
    return sum(qlen(i) for i in range(1, q)) + qlen(q) - left


def ordered(game):
    """[(game seconds, event)] in the order things happened on the court: by the game clock when an action carries it (so a time the analyst corrects, or an action he adds
    for an earlier moment, falls in its place), the order of entry otherwise (an action without a clock follows the one before it)."""
    now, rows = 0, []
    for e in game["events"]:
        if "q" in e:
            now = elapsed(e["q"], e["t"])
        rows.append((now, e["n"], e))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(a, e) for a, _, e in rows]


def court(game):
    """Who is on the court and for how long, from the "lineup" events (the analyst's five of each team, with the game clock when he uses it).
    {"on": {team: [ids]}, "since": {team: game seconds when this five came on}, "base": {id: seconds of the stints already closed}, "pm": {id: plus/minus}, "end": game seconds at the last clock stamp
    (or the end the analyst gave when he sent the game)}. A player's time is "base" + (end - since) while he is on; plus/minus is the points scored by both teams while he was on."""
    team_of = {p["id"]: c for c, ps in game["players"].items() for p in ps}
    on, since, base, pm, now = {c: [] for c in game["players"]}, {c: None for c in game["players"]}, {}, {}, 0
    for now, e in ordered(game):
        if e["stat"] == "lineup":
            c = e["team"]
            for pid in on[c]:
                base[pid] = base.get(pid, 0) + max(0, now - (since[c] or 0))
            on[c], since[c] = list(e["on"]), now
        elif e["stat"] in POINTS and e["pid"] in team_of:
            for c in on:
                for pid in on[c]:
                    pm[pid] = pm.get(pid, 0) + (POINTS[e["stat"]] if c == team_of[e["pid"]] else -POINTS[e["stat"]])
    end = game.get("end")
    return {"on": on, "since": since, "base": base, "pm": pm, "end": elapsed(end["q"], end["t"]) if end else now,
            "used": any(e["stat"] == "lineup" for e in game["events"])}


def minutes(game):
    """{id: seconds on the court} up to the end of the count (only for a game where the analyst marked who was on the court)."""
    c = court(game)
    out = dict(c["base"])
    for code, ids in c["on"].items():
        for pid in ids:
            out[pid] = out.get(pid, 0) + max(0, c["end"] - (c["since"][code] or 0))
    return out


st_is_team = lambda e: e.get("pid") is None and e.get("stat") in TEAM_STATS


def possession(game):
    """Which team has the ball: {"team": code or None, "how": why, "manual": bool}. Deduced from the last action in game order (a made basket gives the ball to the other team, a rebound,
    a steal or a foul drawn gives it to that player's team, a turnover or a foul committed to the other team; a miss or a block leaves it loose until the rebound), unless the analyst set
    it by hand and nothing was counted after that."""
    team_of = {p["id"]: c for c, ps in game["players"].items() for p in ps}
    other = lambda c: next((x for x in game["players"] if x != c), None)
    top = max((e["n"] for e in game["events"]), default=0)
    m = game.get("ball")
    if m and m.get("team") in game["players"] and top <= m.get("n", 0):
        return {"team": m["team"], "how": "manual", "manual": True}
    team, how, prev = None, None, None
    for _, e in ordered(game):
        st, c = e["stat"], team_of.get(e.get("pid")) or (e.get("team") if st_is_team(e) else None)
        if st == "lineup" or c is None:
            continue
        if st in ("p2_m", "p3_m"):
            team, how = other(c), "basket"
        elif st == "ft_m":
            team, how = (other(c), "basket") if prev and prev[0] in ("ft_m", "ft_x") and prev[1] == c else (c, "free throws")
        elif st == "ft_x":
            team, how = (None, "miss") if prev and prev[0] in ("ft_m", "ft_x") and prev[1] == c else (c, "free throws")
        elif st in ("p2_x", "p3_x"):
            team, how = None, "miss"
        elif st == "blk":
            team, how = None, "block"
        elif st in ("oreb", "dreb", "t_oreb", "t_dreb"):
            team, how = c, "rebound"
        elif st == "stl":
            team, how = c, "steal"
        elif st in ("tov", "t_tov"):
            team, how = other(c), "turnover"
        elif st == "pf":
            team, how = other(c), "foul"
        elif st == "fd":
            team, how = c, "foul drawn"
        elif st == "ast" and not (prev and prev[0] in ("p2_m", "p3_m") and prev[1] == c):      # an assist entered after its basket must not give the ball back
            team, how = c, "assist"
        prev = (st, c)
    return {"team": team, "how": how, "manual": False}


def _view(game):
    return {**game, "court": court(game), "extra": team_extra(game), "ball": possession(game), "team_events": team_tally(game), "totals": {c: team_totals(game, c) for c in game["players"]}}


def clean_tags(stat, tags):
    """The tags this kind of action may carry, in a fixed order; anything else is dropped."""
    ok = TAGS.get(stat, ())
    return [t for t in ok if isinstance(tags, (list, tuple)) and t in tags]


def team_extra(game):
    """{team: {"paint", "second", "fast", "tov_pts", "bench"}}: the points of the tagged baskets, and the points of the players who were not in the first five the analyst marked
    (bench points need both fives; without them the key is left out). The same five numbers as a federation sheet's team lines (team_extra.py)."""
    team_of = {p["id"]: c for c, ps in game["players"].items() for p in ps}
    out = {c: {"paint": 0, "second": 0, "fast": 0, "tov_pts": 0} for c in game["players"]}
    for e in game["events"]:
        if e["stat"] in POINTS and e.get("tags") and e["pid"] in team_of:
            for t in e["tags"]:
                if t in TAG_KEY:
                    out[team_of[e["pid"]]][TAG_KEY[t]] += POINTS[e["stat"]]
    first = {}
    for _, e in ordered(game):
        if e["stat"] == "lineup" and e["team"] not in first:
            first[e["team"]] = set(e["on"])
    t = tally(game)
    for c, five in first.items():
        if len(five) == 5:
            out[c]["bench"] = sum(points_of(t.get(p["id"], {})) for p in game["players"][c] if p["id"] not in five)
    return out


def points_of(r):
    return sum(POINTS[k] * r.get(k, 0) for k in POINTS)


def scores(game):
    t = tally(game)
    return {c: sum(points_of(t.get(p["id"], {})) for p in ps) for c, ps in game["players"].items()}


def line(r):
    """One player's counted line, in the columns of a box score."""
    g = lambda k: r.get(k, 0)
    fgm, fga = g("p2_m") + g("p3_m"), g("p2_m") + g("p3_m") + g("p2_x") + g("p3_x")
    return {"pts": points_of(r), "fgm": fgm, "fga": fga, "p3m": g("p3_m"), "p3a": g("p3_m") + g("p3_x"), "ftm": g("ft_m"), "fta": g("ft_m") + g("ft_x"),
            "oreb": g("oreb"), "dreb": g("dreb"), "ast": g("ast"), "stl": g("stl"), "blk": g("blk"), "tov": g("tov"), "pf": g("pf") + g("tf"), "fd": g("fd")}         # a technical foul on a player is one of his fouls (FIBA)


def summary(game):
    s = scores(game)
    return {"id": game["id"], "home": game["home"], "away": game["away"], "matchday": game.get("matchday"), "date": game.get("date"), "status": game["status"], "old": is_old(game),
            "created": game["created"], "analyst": game.get("analyst"), "kind": game.get("kind", "live"), "base": game.get("base") or game["id"], "live": bool(game.get("live")), "events": len(game["events"]), "home_score": s[game["home"]], "away_score": s[game["away"]], "note": game.get("note", "")}


def _roster(codes):
    """The players the site knows for these teams, most used first."""
    rows = [p for p in stats.build()["players"] if p["team"] in codes]
    rows.sort(key=lambda p: (-(p.get("total_min") or 0), p["number"]))
    return {c: [{"id": p["id"], "name": p["name"], "number": p["number"]} for p in rows if p["team"] == c] for c in codes}


def is_old(game, official=None):
    """An OLD game: it was already played (it has an official result, or its date is past). Counting one is only for editing / redoing its numbers: it is never live."""
    o = official or stats.load_official()
    if any(r["matchday"] == game.get("matchday") and {r["home"], r["away"]} == {game["home"], game["away"]} for r in o["results"]):
        return True
    day = game.get("date")
    return bool(day) and day < time.strftime("%Y-%m-%d", time.gmtime(time.time() + 3600))      # Tunisia is UTC+1 all year


# ---------------------------------------------------------------- live: what the public sees of a game the ADMIN has switched on
PLAY = {"ft_m": "free throw made", "p2_m": "2-pointer made", "p3_m": "3-pointer made", "ft_x": "free throw missed", "p2_x": "2-pointer missed", "p3_x": "3-pointer missed",
        "oreb": "offensive rebound", "dreb": "defensive rebound", "ast": "assist", "stl": "steal", "blk": "block", "tov": "turnover", "pf": "foul", "fd": "foul drawn",
        "tf": "technical foul", "inj": "injured", "ej": "ejected", "t_oreb": "team offensive rebound", "t_dreb": "team defensive rebound", "t_tov": "team turnover", "timeout": "timeout",
        "tf_c": "technical foul on the coach", "tf_b": "technical foul on the bench"}


def team_totals(game, code, t=None):
    """The team's line so far, in the columns of a box score: the sum of what its players have counted (a player with nothing yet adds nothing)."""
    t = t or tally(game)
    tot = {}
    for p in game["players"][code]:
        for k, v in line(t.get(p["id"], {})).items():
            tot[k] = tot.get(k, 0) + v
    tt = team_tally(game)[code]
    tot["team_reb"], tot["team_tov"] = tt.get("t_oreb", 0) + tt.get("t_dreb", 0), tt.get("t_tov", 0)        # the "Team" row of the sheet: counted for the team, not for a player
    tot["oreb"], tot["dreb"], tot["tov"] = tot.get("oreb", 0) + tt.get("t_oreb", 0), tot.get("dreb", 0) + tt.get("t_dreb", 0), tot.get("tov", 0) + tt.get("t_tov", 0)
    tot["reb"] = tot["oreb"] + tot["dreb"]
    tot["timeouts"] = tt.get("timeout", 0)
    tot["techs"] = sum((t.get(p["id"]) or {}).get("tf", 0) for p in game["players"][code]) + tt.get("tf_c", 0) + tt.get("tf_b", 0)
    return tot


def game_flow(game):
    """How the game went, from the points in game order: {"lead": {team: biggest lead}, "run": {team: most unanswered points}, "changes": lead changes, "ties": times the score was level again}."""
    team_of = {p["id"]: c for c, ps in game["players"].items() for p in ps}
    codes = list(game["players"])
    if len(codes) != 2:
        return {"lead": {}, "run": {}, "changes": 0, "ties": 0}
    sc, lead, run, cur, last, leader, changes, ties = {c: 0 for c in codes}, {c: 0 for c in codes}, {c: 0 for c in codes}, {c: 0 for c in codes}, None, None, 0, 0
    for _, e in ordered(game):
        c = team_of.get(e.get("pid"))
        if e["stat"] not in POINTS or c is None:
            continue
        o = codes[1] if c == codes[0] else codes[0]
        sc[c] += POINTS[e["stat"]]
        cur[c] = cur[c] + POINTS[e["stat"]] if last == c else POINTS[e["stat"]]
        cur[o], last = 0, c
        run[c] = max(run[c], cur[c])
        lead[c] = max(lead[c], sc[c] - sc[o])
        now = c if sc[c] > sc[o] else o if sc[o] > sc[c] else None
        if now is None:
            ties += 1
        elif leader and now != leader:
            changes += 1
        leader = now or leader
    return {"lead": lead, "run": run, "changes": changes, "ties": ties}


def line_score(game):
    """Points per period when the analyst uses the game clock: {"periods": n, "pts": {team: [per period]}}, None otherwise (the order of entry says nothing about the quarter)."""
    if not any("q" in e for e in game["events"]):
        return None
    team_of = {p["id"]: c for c, ps in game["players"].items() for p in ps}
    rows = [(now, e) for now, e in ordered(game) if e["stat"] in POINTS and team_of.get(e.get("pid"))]
    period = lambda now: next((q for q in range(1, 9) if now <= elapsed(q, 0)), 8)
    n = max([period(now) for now, _ in rows] + [4] + [e["q"] for e in game["events"] if "q" in e])
    pts = {c: [0] * n for c in game["players"]}
    for now, e in rows:
        pts[team_of[e["pid"]]][max(1, period(now)) - 1] += POINTS[e["stat"]]
    return {"periods": n, "pts": pts}


def live_games():
    """The games being counted right now that the admin has made public ("live": true): score, game clock as of the last stamped action, the box score so far, the five on the court and
    the last plays. Nothing else of an analyst's work is ever public, and a game that was sent for approval is no longer live."""
    out = []
    if not DIR.exists():
        return out
    photos = stats.load_photos()
    names = stats.load_official()["teams"]
    for f in sorted(DIR.glob("*.json")):
        try:
            g = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if not g.get("live") or g.get("status") not in OPEN_STATES or g.get("kind") == "video" or is_old(g):
            continue
        t, c, mins, sc = tally(g), court(g), minutes(g), scores(g)
        who_ = {p["id"]: (code, p) for code, ps in g["players"].items() for p in ps}
        seq = ordered(g)
        stamp = next(({"q": e["q"], "t": e["t"]} for _, e in reversed(seq) if "q" in e), None)
        teams = {}
        for code, ps in g["players"].items():
            rows = []
            for p in ps:
                r = t.get(p["id"], {})
                on = p["id"] in c["on"][code]
                if not r and not on:
                    continue
                l = line(r)
                rows.append({"id": p["id"], "name": p["name"], "number": p["number"], "photo": photos.get(p["id"]), "on": on, **l, "reb": l["oreb"] + l["dreb"], "tf": r.get("tf", 0), "inj": bool(r.get("inj")), "ej": bool(r.get("ej")),
                             **({"sec": mins.get(p["id"], 0), "pm": c["pm"].get(p["id"], 0)} if c["used"] else {})})
            rows.sort(key=lambda x: (-x["on"], -x["pts"], x["number"]))
            teams[code] = {"code": code, "name": names.get(code, code), "score": sc[code], "players": rows, "totals": team_totals(g, code, t), "extra": team_extra(g).get(code, {})}
        plays = []
        for _, e in reversed(seq):
            if e["stat"] == "lineup":
                continue
            if st_is_team(e):                                                  # a timeout, a team rebound...: no player
                plays.append({"q": e.get("q"), "t": e.get("t"), "team": e["team"], "name": "", "number": None, "text": PLAY[e["stat"]], "pts": 0})
            elif e["pid"] in who_:
                code, p = who_[e["pid"]]
                plays.append({"q": e.get("q"), "t": e.get("t"), "team": code, "name": p["name"], "number": p["number"], "text": PLAY[e["stat"]], "pts": POINTS.get(e["stat"], 0)})
            else:
                continue
            if len(plays) >= 14:
                break
        out.append({"id": g["id"], "home": g["home"], "away": g["away"], "matchday": g.get("matchday"), "clock": stamp, "teams": teams, "plays": plays,
                    "used_court": c["used"], "ball": possession(g), "flow": game_flow(g), "quarters": line_score(g), "updated": int(f.stat().st_mtime), "since": g.get("live_since")})
    return out


@bp.get("/analytics/api/data")
def data():
    plan = stats.planning()
    photos = stats.load_photos()
    games = [summary(g) for g in (json.loads(f.read_text()) for f in sorted(DIR.glob("*.json"), reverse=True)) if _mine(g) and g.get("kind") != "video"] if DIR.exists() else []     # counting from the video is gone
    roster = {}
    for p in stats.build()["players"]:
        roster.setdefault(p["team"], []).append({"id": p["id"], "name": p["name"], "number": p["number"], "photo": photos.get(p["id"]), "min": p.get("total_min") or 0})
    for ps in roster.values():
        ps.sort(key=lambda p: (-p["min"], p["number"]))
    d = stats.build()
    fives = {c: [p["id"] for p in lineups.expected_five(d, c)] for c in roster}            # the five most likely to start (starts this season and in the last games, absences left out)
    matches = [{"key": f"{md['matchday']}:{g['home']}-{g['away']}", "matchday": md["matchday"], "date": g.get("game_date") or md.get("date"), "time": g.get("time"),
                "home": g["home"], "away": g["away"], "played": g["played"]} for md in plan["matchdays"] for g in md["games"]]
    have = {(m["matchday"], frozenset((m["home"], m["away"]))) for m in matches}
    cal = stats.load_calendar()
    for r in sorted(stats.load_official()["results"], key=lambda r: (r["matchday"], r["home"])):          # the rounds of the first phase too: any game of any round can be opened
        if (r["matchday"], frozenset((r["home"], r["away"]))) not in have:
            matches.append({"key": f"{r['matchday']}:{r['home']}-{r['away']}", "matchday": r["matchday"], "date": cal.get(r["matchday"]), "time": None, "home": r["home"], "away": r["away"], "played": True})
    matches.sort(key=lambda m: (m["matchday"], m["home"]))
    return jsonify(teams=plan["teams"], roster=roster, fives=fives, matches=matches, games=games, me=dict(zip(("name", "admin"), (who()[0], auth.is_admin()))))


@bp.post("/analytics/api/games")
def create():
    b = request.get_json(silent=True) or {}
    home, away = b.get("home"), b.get("away")
    teams = stats.load_official()["teams"]
    if home not in teams or away not in teams or home == away:
        return jsonify(error="Pick two different teams."), 422
    md = b.get("matchday") if isinstance(b.get("matchday"), int) and 1 <= b["matchday"] <= 60 else None
    name, slug = who()
    if b.get("video"):
        return jsonify(error="Counting a game from the video is no longer offered: pick the game of its round instead."), 422
    date = b.get("date")
    base = f"j{md}-{home.lower()}-{away.lower()}" if md else f"x-{home.lower()}-{away.lower()}-{time.strftime('%m%d-%H%M')}"
    # any game of any round can be opened, even one that already has a full box score (to edit or redo its numbers); an old game is simply never live
    gid = f"{base}--{slug}"                          # two analysts with two names count the same game on two separate sheets
    with _file_lock:
        if not _path(gid).exists():
            g = {"id": gid, "base": base, "kind": "live", "analyst": name, "analyst_slug": slug, "home": home, "away": away, "matchday": md,
                 "date": date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date or "")) else None,
                 "status": "open", "created": time.strftime("%Y-%m-%d %H:%M"), "players": _roster([home, away]), "events": [], "log": []}
            _log(g, name, "start", "started counting this game")
            _save(g)
            auth.audit("analytics-new-game", f"{gid} by {name}")
    return jsonify(_view(_load_mine(gid)))


@bp.get("/analytics/api/games/<gid>")
def get_game(gid):
    return jsonify(_view(_load_mine(gid)))


@bp.delete("/analytics/api/games/<gid>")
def delete_game(gid):
    with _file_lock:
        g = _load_mine(gid)
        if g["status"] == "published":
            return jsonify(error="This game is published: ask the admin to unpublish it first."), 409
        _path(gid).unlink(missing_ok=True)
    auth.audit("analytics-delete-game", gid)
    return jsonify(ok=True)


def _stamp(e, b):
    """The game clock is an extra: quarter and seconds left, only when the analyst uses it."""
    if isinstance(b.get("q"), int) and 1 <= b["q"] <= 8 and isinstance(b.get("t"), int) and 0 <= b["t"] <= 3600:
        e["q"], e["t"] = b["q"], b["t"]


def _log(g, by, op, detail):
    """Who did what: one line per change, kept with the game (the admin reads it in the Analytics tab)."""
    g.setdefault("log", []).append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "by": by or "?", "op": op, "detail": detail})
    del g["log"][:-LOG_MAX]


def _clock(e):
    return f" ({'OT' + str(e['q'] - 4) if e['q'] > 4 else 'Q' + str(e['q'])} {e['t'] // 60}:{e['t'] % 60:02d})" if "q" in e else ""


def describe(g, e):
    names = {p["id"]: p["name"] for ps in g["players"].values() for p in ps}
    if e["stat"] == "lineup":
        return f"five of {e['team']}: " + (", ".join(names.get(i, i) for i in e["on"]) or "nobody") + _clock(e)
    if e.get("pid") is None:
        return f"{e.get('team')} · {PLAY.get(e['stat'], e['stat'])}" + _clock(e)
    tags = (" (" + ", ".join(TAG_LABEL[t] for t in e["tags"]) + ")") if e.get("tags") else ""
    return f"{names.get(e['pid'], e['pid'])} · {PLAY.get(e['stat'], e['stat'])}{tags}" + _clock(e)


def _can_edit(g):
    return g["status"] in OPEN_STATES or (auth.is_admin() and g["status"] == "submitted")


def _next_n(g):
    return max((e["n"] for e in g["events"]), default=0) + 1


@bp.post("/analytics/api/games/<gid>/<op>")
def change(gid, op):
    if op not in ("event", "team", "lineup", "edit", "undo", "remove", "submit", "reopen", "ball"):
        abort(404)
    b = request.get_json(silent=True) or {}
    name, _ = who()
    with _file_lock:
        g = _load_mine(gid)
        if op == "reopen":
            if g["status"] != "submitted":
                return jsonify(error="Only a game waiting for approval can be reopened."), 409
            g["status"] = "open"
            _log(g, name, "reopen", "took the game back to edit it")
        elif not _can_edit(g):
            return jsonify(error=f"This game is {g['status']}: it can no longer be changed." + (" Ask the admin to unpublish it first." if g["status"] == "published" else "")), 409
        elif op == "event":
            known = {p["id"] for ps in g["players"].values() for p in ps}
            if b.get("stat") not in STATS or b.get("pid") not in known:
                return jsonify(error="Unknown player or action."), 422
            if len(g["events"]) >= MAX_EVENTS:
                return jsonify(error="Too many actions in one game."), 422
            e = {"n": _next_n(g), "pid": b["pid"], "stat": b["stat"], "at": time.strftime("%H:%M:%S"), "by": name}
            tags = clean_tags(b["stat"], b.get("tags"))
            if tags:
                e["tags"] = tags
            _stamp(e, b)
            g["events"].append(e)
            _log(g, name, "add", "added " + describe(g, e))
        elif op == "team":                                     # a team event: team rebound / turnover, timeout, technical foul on the coach or the bench
            if b.get("stat") not in TEAM_STATS or b.get("team") not in g["players"]:
                return jsonify(error="Unknown team or action."), 422
            if len(g["events"]) >= MAX_EVENTS:
                return jsonify(error="Too many actions in one game."), 422
            e = {"n": _next_n(g), "pid": None, "stat": b["stat"], "team": b["team"], "at": time.strftime("%H:%M:%S"), "by": name}
            _stamp(e, b)
            g["events"].append(e)
            _log(g, name, "add", "added " + describe(g, e))
        elif op == "ball":                                     # optional: the analyst says which team has the ball (null = back to the deduction from the last action)
            code = b.get("team")
            if code is not None and code not in g["players"]:
                return jsonify(error="Pick one of the two teams."), 422
            if code is None:
                g.pop("ball", None)
            else:
                g["ball"] = {"team": code, "n": max((e["n"] for e in g["events"]), default=0), "by": name, "at": time.strftime("%H:%M:%S")}
            _log(g, name, "ball", f"set the ball to {code}" if code else "took the ball back to the automatic guess")
        elif op == "lineup":
            code, ids = b.get("team"), b.get("on")
            known = {p["id"] for p in g["players"].get(code, [])}
            if code not in g["players"] or not isinstance(ids, list) or len(ids) > 5 or len(set(ids)) != len(ids) or any(i not in known for i in ids):
                return jsonify(error="Pick up to five players of this team."), 422
            if len(g["events"]) >= MAX_EVENTS:
                return jsonify(error="Too many actions in one game."), 422
            e = {"n": _next_n(g), "pid": None, "stat": "lineup", "team": code, "on": ids, "at": time.strftime("%H:%M:%S"), "by": name}
            _stamp(e, b)
            g["events"].append(e)
            _log(g, name, "lineup", "set the " + describe(g, e))
        elif op == "edit":
            e = next((x for x in g["events"] if x["n"] == b.get("n")), None)
            if not e:
                return jsonify(error="That action does not exist any more."), 422
            before = describe(g, e)
            if e["stat"] == "lineup":
                ids = b.get("on", e["on"])
                known = {p["id"] for p in g["players"].get(e["team"], [])}
                if not isinstance(ids, list) or len(ids) > 5 or len(set(ids)) != len(ids) or any(i not in known for i in ids):
                    return jsonify(error="Pick up to five players of this team."), 422
                e["on"] = ids
            elif e.get("pid") is None:                           # a team event: its action and its team
                stat, team = b.get("stat", e["stat"]), b.get("team", e.get("team"))
                if stat not in TEAM_STATS or team not in g["players"]:
                    return jsonify(error="Unknown team or action."), 422
                e["stat"], e["team"] = stat, team
            else:
                pid, stat = b.get("pid", e["pid"]), b.get("stat", e["stat"])
                if stat not in STATS or pid not in {p["id"] for ps in g["players"].values() for p in ps}:
                    return jsonify(error="Unknown player or action."), 422
                e["pid"], e["stat"] = pid, stat
            if "tags" in b or e.get("tags"):
                tags = clean_tags(e["stat"], b.get("tags", e.get("tags")))
                if tags:
                    e["tags"] = tags
                else:
                    e.pop("tags", None)
            if "clock" in b:                                   # {"q": 2, "t": 392} puts it at that moment; null takes the clock off
                if b["clock"] is None:
                    e.pop("q", None), e.pop("t", None)
                else:
                    probe = {}
                    _stamp(probe, b["clock"] if isinstance(b["clock"], dict) else {})
                    if not probe:
                        return jsonify(error="The time is a quarter (1-8) and seconds left (0-3600)."), 422
                    e["q"], e["t"] = probe["q"], probe["t"]
            e["edited_by"], e["edited_at"] = name, time.strftime("%Y-%m-%d %H:%M:%S")
            _log(g, name, "edit", f"changed {before}  →  {describe(g, e)}")
        elif op == "undo":
            if g["events"]:
                last = max(g["events"], key=lambda x: x["n"])
                g["events"].remove(last)
                _log(g, name, "undo", "undid " + describe(g, last))
        elif op == "remove":
            gone = next((x for x in g["events"] if x["n"] == b.get("n")), None)
            if gone:
                g["events"] = [x for x in g["events"] if x is not gone]
                _log(g, name, "remove", "removed " + describe(g, gone))
        elif op == "submit":
            md, date = b.get("matchday"), str(b.get("date") or "")
            if not isinstance(md, int) or not 1 <= md <= 60 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                return jsonify(error="Enter the matchday number and the date of the game."), 422
            if not g["events"]:
                return jsonify(error="Nothing counted yet."), 422
            g.update(status="submitted", matchday=md, date=date, submitted=time.strftime("%Y-%m-%d %H:%M"), note="")
            probe = {}
            _stamp(probe, b)
            if probe:
                g["end"] = {"q": probe["q"], "t": probe["t"]}        # where the game clock stood when he sent it: the time on the court is counted up to there
            _log(g, name, "submit", f"sent the game for approval (J{md}, {date})")
            auth.audit("analytics-submit", f"{gid} by {name}")
        _save(g)
    return jsonify(_view(g))


@bp.get("/analytics/api/games/<gid>/export.csv")
def export_csv(gid):
    g = _load_mine(gid)
    t = tally(g)
    out = io.StringIO()
    w = csv.writer(out)
    c, mins = court(g), minutes(g)
    w.writerow(["team", "number", "player", *(["MIN", "+/-"] if c["used"] else []), "PTS", "FGM", "FGA", "3PM", "3PA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "FD"])
    for code, ps in g["players"].items():
        for p in ps:
            if p["id"] in t or mins.get(p["id"]):
                l = line(t.get(p["id"], {}))
                w.writerow([code, p["number"], p["name"], *([f"{mins.get(p['id'], 0) // 60}:{mins.get(p['id'], 0) % 60:02d}", c["pm"].get(p["id"], 0)] if c["used"] else []),
                            l["pts"], l["fgm"], l["fga"], l["p3m"], l["p3a"], l["ftm"], l["fta"], l["oreb"], l["dreb"], l["oreb"] + l["dreb"],
                            l["ast"], l["stl"], l["blk"], l["tov"], l["pf"], l["fd"]])
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": f'attachment; filename="{gid}.csv"'}


@bp.get("/analytics/api/games/<gid>/export-team.csv")
def export_team_csv(gid):
    """The team lines the analyst tagged: team, points in the paint, second chance, fast break, off turnovers, bench (empty when not counted)."""
    g = _load_mine(gid)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["team", "paint", "second_chance", "fast_break", "points_off_turnovers", "bench"])
    for code, x in team_extra(g).items():
        w.writerow([code, x["paint"], x["second"], x["fast"], x["tov_pts"], x.get("bench", "")])
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": f'attachment; filename="{gid}-team.csv"'}


# ---------------------------------------------------------------- the admin's side: review, approve, reject, unpublish
def _sheet_id(gid, code):
    return f"live-{gid}-{code.lower()}"


def _official_result(g):
    return next((r for r in stats.load_official()["results"] if r["matchday"] == g.get("matchday") and {r["home"], r["away"]} == {g["home"], g["away"]}), None)


def _sheets(g):
    """The two one-team sheets of stats.py's partial games for this game."""
    t, out, c, mins, ex = tally(g), [], court(g), minutes(g), team_extra(g)
    for code in (g["home"], g["away"]):
        players = [{"number": p["number"], "name": p["name"], **line(t[p["id"]]), **({"min": round(mins.get(p["id"], 0) / 60, 2), "pm": c["pm"].get(p["id"], 0)} if c["used"] else {})}
                   for p in g["players"][code] if p["id"] in t]
        if players:
            out.append({"id": _sheet_id(g["id"], code), "matchday": g["matchday"], "home": g["home"], "away": g["away"], "recorded": code, "date": g["date"],
                        "extra": ex[code], "competition": "CHAMPIONNAT PRO A", "source": f"Live count by {g.get('analyst') or 'an analyst'} on tunisiabasket.com, approved by the admin",
                        "note": "Counted by hand while watching the game: fouls drawn are not known, and a stat may be missed." + (" Minutes and +/- come from the five the analyst marked on the court (the site does not use them yet)." if c["used"] else " Minutes and +/- are not known."), "players": players})
    return out


def _partial_write(g, sheets):
    with _file_lock:
        try:
            doc = json.loads(PARTIAL_FILE.read_text())
        except (OSError, ValueError):
            doc = {}
        mine = {_sheet_id(g["id"], g["home"]), _sheet_id(g["id"], g["away"])}
        keep = [s for s in doc.get("games") or [] if s.get("id") not in mine]            # exactly this game's two sheets: another version of the same game keeps its own
        doc["games"] = keep + sheets
        tmp = PARTIAL_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        tmp.replace(PARTIAL_FILE)


@bp.post("/admin/api/analytics/<gid>/live")
def admin_live(gid):
    """Body {"on": true|false}: show this game, while it is being counted, on the public Live page (or stop showing it)."""
    g = _load(gid)
    if g.get("kind") == "video" or is_old(g):
        return jsonify(error="An old game (already played) cannot be live: it can only be edited."), 409
    if g["status"] not in OPEN_STATES:
        return jsonify(error="Only a game that is being counted can be live."), 409
    on = bool((request.get_json(silent=True) or {}).get("on"))
    with _file_lock:
        g["live"] = on
        if on:
            g["live_since"] = int(time.time())
            for f in DIR.glob("*.json"):                       # one version of a game on the Live page: the others of the same game go off
                o = json.loads(f.read_text())
                if o["id"] != g["id"] and o.get("live") and {o["home"], o["away"]} == {g["home"], g["away"]} and o.get("matchday") == g.get("matchday"):
                    o["live"] = False
                    _save(o)
        _save(g)
    auth.audit("analytics-live", f"{gid} {'on' if on else 'off'}")
    return jsonify(ok=True, message="Live: the public can follow this game now." if on else "No longer live.")


@bp.get("/admin/api/analytics")
def admin_list():
    counting, official = [], stats.load_official()
    for f in sorted(DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True) if DIR.exists() else []:      # the game worked on last comes first
        g = json.loads(f.read_text())
        if g.get("kind") == "video" and g["status"] != "published":
            continue                            # counting from the video is gone
        if g["status"] in OPEN_STATES:
            s, old = scores(g), is_old(g, official)
            # an old game is never public, whatever flag an earlier version left on it: it is only shown as live when the public really sees it
            counting.append({**summary(g), "live": bool(g.get("live")) and not old, "old": old, "updated": int(f.stat().st_mtime), "score": f"{g['home']} {s[g['home']]} – {s[g['away']]} {g['away']}"})
    rows = []
    for f in sorted(DIR.glob("*.json"), reverse=True) if DIR.exists() else []:
        g = json.loads(f.read_text())
        if g["status"] == "open":
            continue                            # still being counted
        r, t, s = _official_result(g), tally(g), scores(g)
        rows.append({**summary(g), "official": {"home": r["home"], "away": r["away"], "home_score": r["home_score"], "away_score": r["away_score"]} if r else None,
                     "same_score": bool(r) and {r["home"]: r["home_score"], r["away"]: r["away_score"]} == s,
                     "box": {c: [{"name": p["name"], "number": p["number"], **line(t[p["id"]])} for p in ps if p["id"] in t] for c, ps in g["players"].items()},
                     "log": g.get("log", [])[-300:], "editable": g["status"] in ("submitted", "open", "rejected")})
    return jsonify(games=rows, counting=counting)


@bp.post("/admin/api/analytics/<gid>/delete")
def admin_delete(gid):
    """Throw away a game that is still being counted (an old test, a game started by mistake). A published one is unpublished first."""
    with _file_lock:
        g = _load(gid)
        if g["status"] == "published":
            return jsonify(error="This game is published: remove it from the site first."), 409
        _path(gid).unlink(missing_ok=True)
    auth.audit("analytics-delete-game", f"{gid} (admin)")
    return jsonify(ok=True, message="Game deleted.")


@bp.post("/admin/api/analytics/<gid>/approve")
def admin_approve(gid):
    b = request.get_json(silent=True) or {}
    g = _load(gid)
    if g["status"] not in ("submitted", "published"):
        return jsonify(error="Only a game sent for approval can be approved."), 409
    md, date = b.get("matchday", g.get("matchday")), str(b.get("date") or g.get("date") or "")
    if not isinstance(md, int) or not 1 <= md <= 60 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return jsonify(error="Matchday and date are needed."), 422
    g.update(matchday=md, date=date, status="published", note="")
    sheets = _sheets(g)
    if not sheets:
        return jsonify(error="Nothing to publish."), 422
    replaced = []
    for f in sorted(DIR.glob("*.json")):                       # one version of a game on the site at a time: another published version of it steps down
        o = json.loads(f.read_text())
        if o["id"] != g["id"] and o["status"] == "published" and {o["home"], o["away"]} == {g["home"], g["away"]} and o.get("matchday") == md:
            _partial_write(o, [])
            o["status"] = "submitted"
            _log(o, "Admin", "unpublish", f"replaced on the site by the version of {g.get('analyst') or 'another analyst'}")
            with _file_lock:
                _save(o)
            replaced.append(o.get("analyst") or o["id"])
    _partial_write(g, sheets)
    _log(g, "Admin", "approve", f"approved and published (J{md}, {date})")
    with _file_lock:
        _save(g)
    auth.audit("analytics-approve", f"{gid} ({g.get('analyst') or 'no name'})")
    shown = _official_result(g) is not None
    return jsonify(ok=True, message=("Published: it is on the site now." if shown else
                   f"Approved, but it will only appear once the official result of J{md} {g['home']}-{g['away']} is entered (Games tab).") +
                   (f" The version of {', '.join(replaced)} is no longer on the site (one version per game)." if replaced else ""))


@bp.post("/admin/api/analytics/<gid>/reject")
def admin_reject(gid):
    g = _load(gid)
    if g["status"] != "submitted":
        return jsonify(error="Only a game waiting for approval can be sent back."), 409
    g.update(status="rejected", note=str((request.get_json(silent=True) or {}).get("note") or "")[:300])
    _log(g, "Admin", "reject", "sent back: " + (g["note"] or "no reason given"))
    with _file_lock:
        _save(g)
    auth.audit("analytics-reject", gid)
    return jsonify(ok=True, message="Sent back to the analyst.")


@bp.post("/admin/api/analytics/<gid>/unpublish")
def admin_unpublish(gid):
    g = _load(gid)
    if g["status"] != "published":
        return jsonify(error="This game is not published."), 409
    _partial_write(g, [])
    g["status"] = "submitted"
    _log(g, "Admin", "unpublish", "removed from the site")
    with _file_lock:
        _save(g)
    auth.audit("analytics-unpublish", gid)
    return jsonify(ok=True, message="Removed from the site; it waits for approval again.")
