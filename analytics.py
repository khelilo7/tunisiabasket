"""Analytics: a role that counts a game by hand while watching it (/analytics), and the admin's approval before anything reaches the public site.

An analyst signs in with their own token (data/analytics_token.json, a salted scrypt hash, or ANALYTICS_TOKEN in the environment). That token opens /analytics and
nothing else: it never works on /admin (a logged-in admin can use /analytics too). The analyst clicks a button per action (+1 / +2 / +3, missed shots, rebounds,
assists...) on the players the site already knows, and every click is one event saved in data/analytics/<game>.json. They can download the box score, or send the
game for approval.

Nothing an analyst enters is public. When the admin approves a game, it is published as TWO one-team sheets in data/partial_games.json (stats.py, "One-team box
scores"): the same safe path as the hand-kept sheets, so minutes, +/- and fouls drawn stay unknown (never 0), the game never enters standings, team totals, the MVP
race or the fan vote, and a real box score of the same game replaces it. A sheet is ignored until the official result of that matchday exists.
"""
import csv
import hmac
import io
import json
import os
import re
import secrets
import threading
import time

from flask import Blueprint, abort, jsonify, request, send_from_directory

import auth
import config
import stats

bp = Blueprint("analytics", __name__)
DIR = config.DATA_DIR / "analytics"
TOKEN_FILE = config.DATA_DIR / "analytics_token.json"
PARTIAL_FILE = config.DATA_DIR / "partial_games.json"
COOKIE = "proa_analyst"
SESSION_HOURS = 12
MAX_EVENTS = 6000
STATS = ("ft_m", "p2_m", "p3_m", "ft_x", "p2_x", "p3_x", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf")
POINTS = {"ft_m": 1, "p2_m": 2, "p3_m": 3}
OPEN_STATES = ("open", "rejected")           # the analyst may still count
PUBLIC = {"analytics.page", "analytics.login_route", "analytics.me"}

_sessions: dict[str, float] = {}
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


def is_analyst() -> bool:
    """A signed-in analyst, or the admin (who may do everything an analyst does)."""
    sid = request.cookies.get(COOKIE)
    if sid:
        with _lock:
            exp = _sessions.get(sid)
            if exp and exp > time.time():
                return True
            _sessions.pop(sid, None)
    return auth.is_admin()


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
    ip, token = auth.client_ip(), (request.get_json(silent=True) or {}).get("token", "")
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
        for k in [k for k, exp in _sessions.items() if exp < now]:
            del _sessions[k]
        _sessions[sid] = now + SESSION_HOURS * 3600
    auth.audit("analytics-login-ok")
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
    return jsonify(analyst=is_analyst(), configured=token_configured())


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
        r = t.setdefault(e["pid"], {})
        r[e["stat"]] = r.get(e["stat"], 0) + 1
    return t


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
            "oreb": g("oreb"), "dreb": g("dreb"), "ast": g("ast"), "stl": g("stl"), "blk": g("blk"), "tov": g("tov"), "pf": g("pf")}


def summary(game):
    s = scores(game)
    return {"id": game["id"], "home": game["home"], "away": game["away"], "matchday": game.get("matchday"), "date": game.get("date"), "status": game["status"],
            "created": game["created"], "events": len(game["events"]), "home_score": s[game["home"]], "away_score": s[game["away"]], "note": game.get("note", "")}


def _roster(codes):
    """The players the site knows for these teams, most used first."""
    rows = [p for p in stats.build()["players"] if p["team"] in codes]
    rows.sort(key=lambda p: (-(p.get("total_min") or 0), p["number"]))
    return {c: [{"id": p["id"], "name": p["name"], "number": p["number"]} for p in rows if p["team"] == c] for c in codes}


@bp.get("/analytics/api/data")
def data():
    plan = stats.planning()
    photos = stats.load_photos()
    games = [summary(json.loads(f.read_text())) for f in sorted(DIR.glob("*.json"), reverse=True)] if DIR.exists() else []
    roster = {}
    for p in stats.build()["players"]:
        roster.setdefault(p["team"], []).append({"id": p["id"], "name": p["name"], "number": p["number"], "photo": photos.get(p["id"]), "min": p.get("total_min") or 0})
    for ps in roster.values():
        ps.sort(key=lambda p: (-p["min"], p["number"]))
    matches = [{"key": f"{md['matchday']}:{g['home']}-{g['away']}", "matchday": md["matchday"], "date": g.get("game_date") or md.get("date"), "time": g.get("time"),
                "home": g["home"], "away": g["away"], "played": g["played"]} for md in plan["matchdays"] for g in md["games"]]
    return jsonify(teams=plan["teams"], roster=roster, matches=matches, games=games)


@bp.post("/analytics/api/games")
def create():
    b = request.get_json(silent=True) or {}
    home, away = b.get("home"), b.get("away")
    teams = stats.load_official()["teams"]
    if home not in teams or away not in teams or home == away:
        return jsonify(error="Pick two different teams."), 422
    md = b.get("matchday") if isinstance(b.get("matchday"), int) and 1 <= b["matchday"] <= 60 else None
    gid = f"j{md}-{home.lower()}-{away.lower()}" if md else f"x-{home.lower()}-{away.lower()}-{time.strftime('%m%d-%H%M')}"
    with _file_lock:
        if not _path(gid).exists():
            _save({"id": gid, "home": home, "away": away, "matchday": md, "date": b.get("date") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(b.get("date") or "")) else None,
                   "status": "open", "created": time.strftime("%Y-%m-%d %H:%M"), "players": _roster([home, away]), "events": []})
            auth.audit("analytics-new-game", gid)
    return jsonify(_load(gid))


@bp.get("/analytics/api/games/<gid>")
def get_game(gid):
    return jsonify(_load(gid))


@bp.delete("/analytics/api/games/<gid>")
def delete_game(gid):
    with _file_lock:
        g = _load(gid)
        if g["status"] == "published":
            return jsonify(error="This game is published: ask the admin to unpublish it first."), 409
        _path(gid).unlink(missing_ok=True)
    auth.audit("analytics-delete-game", gid)
    return jsonify(ok=True)


@bp.post("/analytics/api/games/<gid>/<op>")
def change(gid, op):
    if op not in ("event", "undo", "remove", "submit", "reopen"):
        abort(404)
    b = request.get_json(silent=True) or {}
    with _file_lock:
        g = _load(gid)
        if op == "reopen":
            if g["status"] != "submitted":
                return jsonify(error="Only a game waiting for approval can be reopened."), 409
            g["status"] = "open"
        elif g["status"] not in OPEN_STATES:
            return jsonify(error=f"This game is {g['status']}: it can no longer be changed."), 409
        elif op == "event":
            known = {p["id"] for ps in g["players"].values() for p in ps}
            if b.get("stat") not in STATS or b.get("pid") not in known:
                return jsonify(error="Unknown player or action."), 422
            if len(g["events"]) >= MAX_EVENTS:
                return jsonify(error="Too many actions in one game."), 422
            g["events"].append({"n": g["events"][-1]["n"] + 1 if g["events"] else 1, "pid": b["pid"], "stat": b["stat"], "at": time.strftime("%H:%M:%S")})
        elif op == "undo":
            if g["events"]:
                g["events"].pop()
        elif op == "remove":
            g["events"] = [e for e in g["events"] if e["n"] != b.get("n")]
        elif op == "submit":
            md, date = b.get("matchday"), str(b.get("date") or "")
            if not isinstance(md, int) or not 1 <= md <= 60 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                return jsonify(error="Enter the matchday number and the date of the game."), 422
            if not g["events"]:
                return jsonify(error="Nothing counted yet."), 422
            g.update(status="submitted", matchday=md, date=date, submitted=time.strftime("%Y-%m-%d %H:%M"), note="")
            auth.audit("analytics-submit", gid)
        _save(g)
    return jsonify(g)


@bp.get("/analytics/api/games/<gid>/export.csv")
def export_csv(gid):
    g = _load(gid)
    t = tally(g)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["team", "number", "player", "PTS", "FGM", "FGA", "3PM", "3PA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF"])
    for code, ps in g["players"].items():
        for p in ps:
            if p["id"] in t:
                l = line(t[p["id"]])
                w.writerow([code, p["number"], p["name"], l["pts"], l["fgm"], l["fga"], l["p3m"], l["p3a"], l["ftm"], l["fta"], l["oreb"], l["dreb"], l["oreb"] + l["dreb"],
                            l["ast"], l["stl"], l["blk"], l["tov"], l["pf"]])
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": f'attachment; filename="{gid}.csv"'}


# ---------------------------------------------------------------- the admin's side: review, approve, reject, unpublish
def _sheet_id(gid, code):
    return f"live-{gid}-{code.lower()}"


def _official_result(g):
    return next((r for r in stats.load_official()["results"] if r["matchday"] == g.get("matchday") and {r["home"], r["away"]} == {g["home"], g["away"]}), None)


def _sheets(g):
    """The two one-team sheets of stats.py's partial games for this game."""
    t, out = tally(g), []
    for code in (g["home"], g["away"]):
        players = [{"number": p["number"], "name": p["name"], **line(t[p["id"]])} for p in g["players"][code] if p["id"] in t]
        if players:
            out.append({"id": _sheet_id(g["id"], code), "matchday": g["matchday"], "home": g["home"], "away": g["away"], "recorded": code, "date": g["date"],
                        "competition": "CHAMPIONNAT PRO A", "source": "Live count by an analyst on tunisiabasket.com, approved by the admin",
                        "note": "Counted by hand while watching the game: minutes, +/- and fouls drawn are not known, and a stat may be missed.", "players": players})
    return out


def _partial_write(g, sheets):
    with _file_lock:
        try:
            doc = json.loads(PARTIAL_FILE.read_text())
        except (OSError, ValueError):
            doc = {}
        keep = [s for s in doc.get("games") or [] if not str(s.get("id", "")).startswith(f"live-{g['id']}-")]
        doc["games"] = keep + sheets
        tmp = PARTIAL_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        tmp.replace(PARTIAL_FILE)


@bp.get("/admin/api/analytics")
def admin_list():
    rows = []
    for f in sorted(DIR.glob("*.json"), reverse=True) if DIR.exists() else []:
        g = json.loads(f.read_text())
        if g["status"] == "open":
            continue                            # still being counted
        r, t, s = _official_result(g), tally(g), scores(g)
        rows.append({**summary(g), "official": {"home": r["home"], "away": r["away"], "home_score": r["home_score"], "away_score": r["away_score"]} if r else None,
                     "same_score": bool(r) and {r["home"]: r["home_score"], r["away"]: r["away_score"]} == s,
                     "box": {c: [{"name": p["name"], "number": p["number"], **line(t[p["id"]])} for p in ps if p["id"] in t] for c, ps in g["players"].items()}})
    return jsonify(games=rows)


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
    _partial_write(g, sheets)
    with _file_lock:
        _save(g)
    auth.audit("analytics-approve", gid)
    shown = _official_result(g) is not None
    return jsonify(ok=True, message=("Published: it is on the site now." if shown else
                   f"Approved, but it will only appear once the official result of J{md} {g['home']}-{g['away']} is entered (Games tab)."))


@bp.post("/admin/api/analytics/<gid>/reject")
def admin_reject(gid):
    g = _load(gid)
    if g["status"] != "submitted":
        return jsonify(error="Only a game waiting for approval can be sent back."), 409
    g.update(status="rejected", note=str((request.get_json(silent=True) or {}).get("note") or "")[:300])
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
    with _file_lock:
        _save(g)
    auth.audit("analytics-unpublish", gid)
    return jsonify(ok=True, message="Removed from the site; it waits for approval again.")
