"""Live scores read automatically from the broadcast's scoreboard (tools/live_reader.py, run on a computer that plays the Diwan Sport stream).

The reader only keeps the scoreboard's numbers: score, quarter, clock. Every few seconds, and at once when something changes, it POSTs them to /api/livescore with the live-score
token (data/livescore_token.json, a salted scrypt hash, or LIVESCORE_TOKEN in the environment; `python manage.py new-livescore-token`). Nothing else is ever sent or stored.

  * One file per game, data/livescore/<id>.json: {id, home, away, matchday, q, clock, score: {code: n}, quarters: {code: [per quarter]}, timeline: [{at, q, t, code: n...}],
    final, started, updated}. When the reader joins a game already started, its first score is a starting point ("base", "joined"): no basket, and no score by quarter. The id is "sb-j<matchday>-<home>-<away>" (lower case); home and away come from the calendar, whatever side the broadcast shows them on.
  * The server is the second filter after the reader: a score never goes down unless the reader says it is a correction (the table fixed it), a jump of more than 8 points
    at once is refused (except for the first reading and after 45 s without any), and a game marked final only opens again if the score or the quarter moves on (the final was called too early).
  * live_games() gives these games in the same shape as analytics.live_games() (no players, no box score: "source": "scoreboard"), so the website's and the app's Live pages
    show them; a game is live while the reader keeps sending (STALE seconds), and stays FINAL_KEEP seconds after its final buzzer. When the reader stops (the app's
    Stop, its window closed, Ctrl-C) it calls stop() for each game it followed (POST /api/livescore/stop): the game leaves the Live pages at once.
  * Who scored (tools/live_reader.py --scorers, tools/live_scorer.py): a few seconds after a basket the reader names the scorer from the commentator's words and
    POSTs it to /api/livescore/scorer (scorer()). It is kept on that basket of the timeline ("by": {team: {id, number, name, conf, sure}}): the plays show his
    name and live_games() adds up the points of every player ("scorers"). An admin can fix or confirm one (set_scorer(), the admin's Live section):
    the reader never overwrites an admin's choice.
  * events() gives notify.py what to announce: the end of each quarter (only to the phones that follow one of the two clubs), and the final score under the same key as the
    official result, so a phone gets the final once.
"""
import hmac
import json
import os
import re
import secrets
import threading
import time

import auth
import config
import stats

DIR = config.DATA_DIR / "livescore"
TOKEN_FILE = config.DATA_DIR / "livescore_token.json"
STALE = 15 * 60            # no reading for this long: the game is no longer shown live (the stream stopped, the reader was closed)
FINAL_KEEP = 45 * 60       # a finished game stays on the Live page this long
CURRENT = 4 * 3600         # a reading between two teams joins their game sent within this time (same game, even once the calendar has its result)
MAX_JUMP = 8
TIMELINE_MAX = 400
CLOCK = re.compile(r"^(\d{1,2})[:.](\d{1,2})$")
_lock = threading.Lock()


# ---------------------------------------------------------------- the reader's token
def set_token(token: str):
    config.DATA_DIR.mkdir(exist_ok=True)
    salt = secrets.token_bytes(16)
    TOKEN_FILE.write_text(json.dumps({"salt": salt.hex(), "hash": auth._hash(token, salt), "created": time.strftime("%Y-%m-%d %H:%M:%S")}))
    os.chmod(TOKEN_FILE, 0o600)


def token_configured() -> bool:
    return bool(os.environ.get("LIVESCORE_TOKEN")) or TOKEN_FILE.exists()


def verify(token: str) -> bool:
    token = (token or "").strip()
    env = os.environ.get("LIVESCORE_TOKEN")
    if env:
        return hmac.compare_digest(token.encode(), env.encode())
    if not token or not TOKEN_FILE.exists():
        return False
    d = json.loads(TOKEN_FILE.read_text())
    return hmac.compare_digest(auth._hash(token.upper(), bytes.fromhex(d["salt"])), d["hash"])


# ---------------------------------------------------------------- which game
def fixture(a, b, official=None):
    """(matchday, home, away) of the first game between a and b without a result in the calendar, or None."""
    for m in stats.planning(official)["matchdays"]:
        for g in m["games"]:
            if {g["home"], g["away"]} == {a, b} and not g["played"]:
                return m["matchday"], g["home"], g["away"]
    return None


def game_id(md, home, away):
    return f"sb-j{md}-{home}-{away}".lower() if md else f"sb-{home}-{away}-{time.strftime('%Y%m%d')}".lower()


def _path(gid):
    if not re.fullmatch(r"[a-z0-9-]{4,60}", gid):
        raise ValueError("bad id")
    return DIR / f"{gid}.json"


def _load(gid):
    try:
        return json.loads(_path(gid).read_text())
    except (OSError, ValueError):
        return None


def _save(g):
    DIR.mkdir(parents=True, exist_ok=True)
    p = _path(g["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(g, ensure_ascii=False))
    tmp.replace(p)


def _clock_secs(v):
    m = CLOCK.match(str(v or "").strip())
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if "." in str(v) and len(m.group(2)) == 1:                                # "45.3" in the last minute: seconds and tenths
        return a
    return a * 60 + b                                                         # "01:09", or "00.48" (the colon read as a dot)


# ---------------------------------------------------------------- a reading from the scoreboard
def _which(left, right, md, official):
    """(matchday, home, away) of the game between left and right: the matchday the reader gives, or the calendar's next game between them."""
    if md:
        md = int(md)
        f = next(((g["home"], g["away"]) for m in stats.planning(official)["matchdays"] if m["matchday"] == md for g in m["games"] if {g["home"], g["away"]} == {left, right}), None)
        home, away = f or (left, right)
        return md, home, away
    g = _current(left, right)
    if g:                                                                     # the game already on Live: its final makes the calendar call it played, and
        return g["matchday"], g["home"], g["away"]                            # the readings after the buzzer must not start a second game
    f = fixture(left, right, official)
    return f if f else (None, left, right)


def _current(left, right, now=None):
    """The game between left and right that the reader sent in the last CURRENT seconds (the latest one), or None."""
    now = int(now or time.time())
    mine = [g for g in _all() if {g["home"], g["away"]} == {left, right} and now - g["updated"] < CURRENT]
    return max(mine, key=lambda g: g["updated"], default=None)


def stop(body: dict, now=None):
    """The reader stopped following a game (Stop in the app, its window closed, Ctrl-C): {"teams": [left, right], "matchday": optional}, or a game removed by hand
    ("Remove a game" in the app): {"id": game id}. The game leaves the Live pages at once; it comes back when the reader sees the game move on (a basket, a new
    quarter, the clock running), not for a window still showing the final score. Returns (game summary, None) or (None, error)."""
    now = int(now or time.time())
    if body.get("id"):                                                        # a game picked from the Live list ("Remove a game" in the app)
        try:
            gid = str(body["id"])
            _path(gid)
        except ValueError:
            return None, "no such game"
    else:
        official = stats.load_official()
        try:
            left, right = [str(x).upper().strip() for x in body["teams"]]
        except (KeyError, TypeError, ValueError):
            return None, "teams or id are required"
        if left not in official["teams"] or right not in official["teams"] or left == right:
            return None, f"unknown teams {left}-{right}"
        gid = game_id(*_which(left, right, body.get("matchday"), official))
    with _lock:
        g = _load(gid)
        if not g:
            return None, "no such game"
        g["stopped"] = now
        _save(g)
    return summary(g), None


def push(body: dict, now=None):
    """One reading: {"teams": [left code, right code], "score": [left, right], "q": 1-4 / 5+ for overtime, "clock": "MM:SS" or "SS.t", "matchday": optional,
    "final": bool, "fix": bool (a correction: the score may go down)}. Returns (game summary, None) or (None, error)."""
    now = int(now or time.time())
    official = stats.load_official()
    known = official["teams"]
    try:
        left, right = [str(x).upper().strip() for x in body["teams"]]
        sl, sr = [int(x) for x in body["score"]]
        q = int(body.get("q") or 1)
    except (KeyError, TypeError, ValueError):
        return None, "teams, score and q are required"
    if left not in known or right not in known or left == right:
        return None, f"unknown teams {left}-{right}"
    if not (0 <= sl < 250 and 0 <= sr < 250 and 1 <= q <= 9):
        return None, "score or quarter out of range"
    md, home, away = _which(left, right, body.get("matchday"), official)
    score = {left: sl, right: sr}
    gid = game_id(md, home, away)
    t = _clock_secs(body.get("clock"))
    with _lock:
        g = _load(gid) or {"id": gid, "home": home, "away": away, "matchday": md, "q": 1, "clock": None, "score": {home: 0, away: 0},
                           "quarters": {home: [0, 0, 0, 0], away: [0, 0, 0, 0]}, "timeline": [], "final": False, "started": now, "updated": now, "ended": []}
        old = g["score"]
        moved = score[home] != old[home] or score[away] != old[away] or q > g["q"]
        if g.get("stopped"):                                                      # taken off Live (Stop, or Remove a game): back only when the game moves on,
            if moved or (not g["final"] and t is not None and g["clock"] is not None and t != g["clock"]):   # not for a window still showing the end
                g.pop("stopped")
            else:
                g["updated"] = now
                if t is not None and not g["final"]:
                    g["clock"] = t                                                # so the next reading can tell whether the clock runs
                _save(g)
                return summary(g), None
        if g["final"] and not body.get("fix"):
            if score[home] > old[home] or score[away] > old[away] or q > g["q"]:
                g["final"] = False                                                # the game went on (a final called too early): it is live again
                g.pop("final_at", None)
            else:
                g["updated"] = now
                _save(g)
                return summary(g), None
        dh, da = score[home] - old[home], score[away] - old[away]
        if body.get("fix") and (dh < -5 or da < -5):                             # a table correction is a few points: a bigger drop is a misread
            return None, f"a correction of more than 5 points is refused ({old[home]}-{old[away]} -> {score[home]}-{score[away]})"
        if not body.get("fix") and (dh < 0 or da < 0):
            return None, f"the score cannot go down ({old[home]}-{old[away]} -> {score[home]}-{score[away]}) unless it is a correction"
        gap = not g["timeline"] or now - g["updated"] > 45                         # the first reading, or nothing read for a while: any score is possible
        if not body.get("fix") and not gap and (dh > MAX_JUMP or da > MAX_JUMP):
            return None, f"jump too big ({old[home]}-{old[away]} -> {score[home]}-{score[away]})"
        if q < g["q"] and not body.get("fix"):
            q = g["q"]                                                            # a misread quarter never goes back
        if q > g["q"]:
            g["ended"] = sorted(set(g.get("ended", [])) | set(range(g["q"], q)))  # the quarters before this one are over
        for code in (home, away):
            while len(g["quarters"][code]) < q:
                g["quarters"][code].append(0)
        if not g["timeline"]:                                                     # the first reading is the starting point: 0-0, or a game the reader joined late (not a basket)
            g["joined"] = bool(score[home] or score[away])
            g["timeline"].append({"at": now, "q": q, "t": t, home: score[home], away: score[away], "base": True})
        elif dh or da:                                                            # the points (or a correction) go to the quarter being played
            g["quarters"][home][q - 1] += dh
            g["quarters"][away][q - 1] += da
            g["timeline"].append({"at": now, "q": q, "t": t, home: score[home], away: score[away], **({"fix": True} if body.get("fix") else {})})
            g["timeline"] = g["timeline"][-TIMELINE_MAX:]
        g["score"], g["q"], g["updated"] = {home: score[home], away: score[away]}, q, now
        if t is not None:
            g["clock"] = t
        if body.get("final"):
            g["final"] = True
            g["final_at"] = now
            g["ended"] = sorted(set(g.get("ended", [])) | set(range(1, q + 1)))
        _save(g)
    return summary(g), None


def _basket(g, left, right, score):
    """Index in g's timeline of the reading where the score became score (left, right as the broadcast shows them), or None."""
    want = {left: score[0], right: score[1]}
    for i in range(len(g["timeline"]) - 1, -1, -1):
        e = g["timeline"][i]
        if not e.get("base") and not e.get("fix") and e.get(left) == want[left] and e.get(right) == want[right]:
            return i
    return None


def scorer(body: dict, now=None):
    """Who scored a basket, from the reader: {"teams": [left, right], "score": [left, right] after the basket, "team": code, "pts": 1-3,
    "player": {"id", "number", "name"} or null (nobody named), "conf": 0.5-1, "sure": bool, "matchday": optional}. Returns (basket, None) or (None, error)."""
    official = stats.load_official()
    try:
        left, right = [str(x).upper().strip() for x in body["teams"]]
        sl, sr = [int(x) for x in body["score"]]
        team, pts = str(body["team"]).upper(), int(body["pts"])
    except (KeyError, TypeError, ValueError):
        return None, "teams, score, team and pts are required"
    if left not in official["teams"] or right not in official["teams"] or team not in (left, right) or not 1 <= pts <= 3:
        return None, "unknown teams or points"
    p = body.get("player")
    if p is not None and not (isinstance(p, dict) and str(p.get("name") or "").strip()):
        return None, "player needs a name"
    gid = game_id(*_which(left, right, body.get("matchday"), official))
    with _lock:
        g = _load(gid)
        if not g:
            return None, "no such game"
        i = _basket(g, left, right, (sl, sr))
        if i is None:
            return None, "no such basket"
        e = g["timeline"][i]
        by = e.setdefault("by", {})
        if (by.get(team) or {}).get("admin"):                                    # an admin already said who it was
            return {"index": i, **by[team]}, None
        by[team] = {"id": str(p.get("id") or "")[:40] or None, "number": p.get("number"), "name": str(p["name"])[:60],
                    "conf": round(float(body.get("conf") or 0), 2), "sure": bool(body.get("sure"))} if p else {"id": None, "number": None, "name": None, "conf": 0, "sure": False}
        _save(g)
    return {"index": i, **by[team]}, None


def set_scorer(gid, index, team, player):
    """The admin's choice for one basket: player {"id", "number", "name"}, or None (nobody / unknown). Returns (basket, None) or (None, error)."""
    try:
        _path(gid)
    except ValueError:
        return None, "no such game"
    with _lock:
        g = _load(gid)
        if not g:
            return None, "no such game"
        if not (isinstance(index, int) and 0 <= index < len(g["timeline"])) or team not in (g["home"], g["away"]):
            return None, "no such basket"
        e = g["timeline"][index]
        e.setdefault("by", {})[team] = ({"id": player.get("id"), "number": player.get("number"), "name": str(player.get("name") or "")[:60] or None}
                                        if player else {"id": None, "number": None, "name": None}) | {"admin": True, "sure": True}
        _save(g)
    return {"index": index, **e["by"][team]}, None


def _baskets(g):
    """[(timeline index, reading, team, points)] of every basket of g, oldest first."""
    h, a = g["home"], g["away"]
    out, last = [], (0, 0)
    for i, e in enumerate(g["timeline"]):
        if not e.get("base") and not e.get("fix"):
            for code, d in ((h, e[h] - last[0]), (a, e[a] - last[1])):
                if d > 0:
                    out.append((i, e, code, d))
        last = (e[h], e[a])
    return out


def scorers(g):
    """{team: [{id, number, name, pts}] best first}, and the points nobody was named for: {team: pts}."""
    pts, unknown = {g["home"]: {}, g["away"]: {}}, {g["home"]: 0, g["away"]: 0}
    for _, e, code, d in _baskets(g):
        b = (e.get("by") or {}).get(code) or {}
        if b.get("name"):
            key = b.get("id") or f"{b.get('number')}|{b['name']}"
            p = pts[code].setdefault(key, {"id": b.get("id"), "number": b.get("number"), "name": b["name"], "pts": 0})
            p["pts"] += d
        else:
            unknown[code] += d
    return {c: sorted(v.values(), key=lambda p: -p["pts"]) for c, v in pts.items()}, unknown


def review(days=3, now=None):
    """The admin's Live section: the games read from the broadcast in the last days, with every basket and who the reader named."""
    now = int(now or time.time())
    out = []
    for g in sorted(_all(), key=lambda g: -g["updated"]):
        if now - g["updated"] > days * 86400:
            continue
        rows = [{"index": i, "q": e["q"], "t": e.get("t"), "team": code, "pts": d, "score": f"{e[g['home']]}-{e[g['away']]}", "by": (e.get("by") or {}).get(code)}
                for i, e, code, d in _baskets(g)]
        out.append({"id": g["id"], "home": g["home"], "away": g["away"], "matchday": g["matchday"], "score": g["score"], "final": g["final"],
                    "updated": g["updated"], "baskets": rows[::-1],
                    "to_check": sum(1 for r in rows if not (r["by"] or {}).get("sure"))})
    return out


def summary(g):
    return {"id": g["id"], "home": g["home"], "away": g["away"], "matchday": g["matchday"], "q": g["q"], "clock": g["clock"], "score": g["score"], "final": g["final"]}


def _all():
    if not DIR.exists():
        return []
    out = []
    for f in sorted(DIR.glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    return out


def _showing(g, now):
    if g.get("stopped"):                                                          # the reader stopped following it
        return False
    if g["final"]:
        return now - g.get("final_at", g["updated"]) < FINAL_KEEP
    return now - g["updated"] < STALE


# ---------------------------------------------------------------- what the Live pages get
def _flow(g):
    """Biggest lead, longest run, lead changes and ties, from the score changes."""
    h, a = g["home"], g["away"]
    lead, run, changes, ties, leader, last, cur = {h: 0, a: 0}, {h: 0, a: 0}, 0, 0, None, (0, 0), {h: 0, a: 0}
    for e in g["timeline"]:
        if e.get("fix") or e.get("base"):
            last = (e[h], e[a])
            leader = h if e[h] > e[a] else a if e[a] > e[h] else leader
            continue
        dh, da = e[h] - last[0], e[a] - last[1]
        for code, d, other in ((h, dh, a), (a, da, h)):
            if d > 0:
                cur[code] += d
                cur[other] = 0
                run[code] = max(run[code], cur[code])
        last = (e[h], e[a])
        diff = e[h] - e[a]
        lead[h], lead[a] = max(lead[h], diff), max(lead[a], -diff)
        now_leader = h if diff > 0 else a if diff < 0 else None
        if now_leader is None and leader is not None:
            ties += 1
        if now_leader and leader and now_leader != leader:
            changes += 1
        if now_leader:
            leader = now_leader
    return {"lead": lead, "run": run, "changes": changes, "ties": ties}


def _plays(g):
    """The score changes, newest first, as plays of the play-by-play list (a team, the points, no player)."""
    h, a = g["home"], g["away"]
    out, last = [], (0, 0)
    for e in g["timeline"]:
        if e.get("base"):
            pass
        elif e.get("fix"):
            out.append({"q": e["q"], "t": e.get("t") or 0, "team": h, "name": "", "number": None, "text": "score corrected", "pts": 0})
        else:
            for code, d in ((h, e[h] - last[0]), (a, e[a] - last[1])):
                if d > 0:
                    b = (e.get("by") or {}).get(code) or {}                  # the scorer the commentator named (--scorers), if any
                    out.append({"q": e["q"], "t": e.get("t") or 0, "team": code, "name": b.get("name") or "", "number": b.get("number"), "id": b.get("id"),
                                "text": {1: "free throw made", 2: "2-pointer made", 3: "3-pointer made"}.get(d, f"{d} points"), "pts": d})
        last = (e[h], e[a])
    return out[::-1][:30]


def live_games(skip=(), now=None):
    """The scoreboard games to show, in analytics.live_games()'s shape. `skip`: matchups ({home, away} frozensets) an analyst already shows live."""
    now = int(now or time.time())
    names = stats.load_official()["teams"]
    out = []
    for g in _all():
        if not _showing(g, now) or frozenset((g["home"], g["away"])) in skip:
            continue
        n = max(4, g["q"], *(len(v) for v in g["quarters"].values()))
        named, unknown = scorers(g)
        teams = {c: {"code": c, "name": names.get(c, c), "score": g["score"][c], "players": [], "totals": {}, "extra": {}} for c in (g["home"], g["away"])}
        out.append({"id": g["id"], "home": g["home"], "away": g["away"], "matchday": g["matchday"], "source": "scoreboard", "final": g["final"],
                    "clock": {"q": g["q"], "t": g["clock"] or 0} if g["clock"] is not None or g["q"] else None, "teams": teams, "plays": _plays(g),
                    "used_court": False, "ball": None, "flow": _flow(g),
                    "quarters": None if g.get("joined") else {"periods": n, "pts": {c: (g["quarters"][c] + [0] * n)[:n] for c in (g["home"], g["away"])}},
                    "updated": g["updated"], "since": g["started"],
                    "scorers": {"by_team": named, "unknown": unknown} if any(named.values()) else None})
    return out


# ---------------------------------------------------------------- what notify.py announces
def events(season=""):
    """{key: (topic, teams, {lang: (title, body)}, path)} for the quarters that ended and the final scores of the games read from the broadcast."""
    names = stats.load_official()["teams"]
    ev = {}
    for g in _all():
        h, a = g["home"], g["away"]
        for q in g.get("ended", []):
            if g["final"] and q == max(g["ended"]):
                continue
            # the score at the end of quarter q: the last reading of that quarter (or before it)
            last = next((e for e in reversed(g["timeline"]) if e["q"] <= q), None)
            if not last:
                continue
            sh, sa = last[h], last[a]
            per = f"Q{q}" if q <= 4 else f"OT{q - 4}"
            ev[f"live:{g['id']}|q{q}"] = ("quarter", (h, a), {"fr": (f"{h} {sh} – {sa} {a}", f"Fin du {per} · {names.get(h, h)} – {names.get(a, a)} en direct"),
                                                              "en": (f"{h} {sh} – {sa} {a}", f"End of {per} · {names.get(h, h)} – {names.get(a, a)} live")}, "/live")
        if g["final"]:
            sh, sa = g["score"][h], g["score"][a]
            win = h if sh > sa else a
            key = f"result:{season}|{g['matchday']}|{h}-{a}" if g["matchday"] else f"live:{g['id']}|final"
            ev[key] = ("results", (h, a), {"fr": (f"{h} {sh} – {sa} {a}", f"Score final · Pro A{' · J' + str(g['matchday']) if g['matchday'] else ''} · Victoire de {names.get(win, win)}"),
                                           "en": (f"{h} {sh} – {sa} {a}", f"Final · Pro A{' · Round ' + str(g['matchday']) if g['matchday'] else ''} · {names.get(win, win)} win")}, "/scores")
    return ev
