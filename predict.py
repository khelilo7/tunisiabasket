"""Match predictions: everybody can pick the winner of every game of the NEXT matchday.

  * One pick per game and per browser, final (same rules as the MVP vote: a random id kept in the browser, only hashes stored,
    a few browsers per network, crawlers refused). Picks live in data/votes.db (table `picks`), so they are backed up with the votes
    and protected the same way: the database refuses to change or delete them.
  * The deadline is the matchday itself: picks close when the matchday's date starts (Tunisian time). Nothing to set.
  * The crowd's split is shown only to someone who has picked THAT game, as percentages: no counts, no total. The server enforces it:
    a request without a pick never receives the split.
"""
import time
from datetime import datetime, timedelta, timezone

import auth
import mvp
import stats
import traffic

MAX_PER_NETWORK = 8
SIDES = {"H": "home", "A": "away"}
TUNIS = timezone(timedelta(hours=1))
_cache = {"t": 0.0, "round": None}


def _round():
    """The next matchday with unplayed games: {matchday, date, deadline_ts, open, season, games:[{key, home, away, home_name, away_name}]} or None.
    Cached for 30 seconds: the calendar changes a few times a day at most."""
    now = time.time()
    if now - _cache["t"] < 30 and _cache["round"] is not None:
        return _cache["round"][0]
    plan = stats.planning()
    season = stats.load_official().get("season") or ""
    today = datetime.now(TUNIS).date().isoformat()
    out = None
    for m in plan["matchdays"]:
        games = [g for g in m["games"] if not g["played"]]
        day = min((g["game_date"] or m["date"] for g in games if g["game_date"] or m["date"]), default=None)      # the first game day of the matchday
        if not games or (day and day < today):
            continue                                              # played, or already past
        start = datetime.fromisoformat(day + "T00:00").replace(tzinfo=TUNIS) if day else None
        out = {"matchday": m["matchday"], "date": day, "deadline_ts": int(start.timestamp()) if start else None,
               "open": start is None or datetime.now(TUNIS) < start, "season": season,
               "games": [{"key": f"{season}|{m['matchday']}|{g['home']}-{g['away']}", "home": g["home"], "away": g["away"],
                          "home_name": plan["teams"].get(g["home"], g["home"]), "away_name": plan["teams"].get(g["away"], g["away"])} for g in games]}
        break
    _cache.update(t=now, round=(out,))
    return out


def _split(con, keys):
    out = {k: {"H": 0, "A": 0} for k in keys}
    if keys:
        q = ",".join("?" * len(keys))
        for game, side, n in con.execute(f"SELECT game, side, COUNT(*) FROM picks WHERE game IN ({q}) GROUP BY game, side", keys):
            out[game][side] = n
    return out


def view(vid: str) -> dict:
    """What a visitor may see: the games, their own picks, and the split of the games they picked (percentages only)."""
    r = _round()
    if not r:
        return {"round": None}
    mine = {}
    with mvp._lock:
        con = mvp._db()
        try:
            if mvp.VID.match(vid or ""):
                voter = mvp._hash("pick", vid)
                mine = dict(con.execute("SELECT game, side FROM picks WHERE voter=? AND game IN (%s)" % ",".join("?" * len(r["games"])),
                                        [voter] + [g["key"] for g in r["games"]]))
            split = _split(con, [k for k in mine])
        finally:
            con.close()
    games = []
    for g in r["games"]:
        row = {k: g[k] for k in ("key", "home", "away", "home_name", "away_name")}
        row["my"] = mine.get(g["key"])
        if row["my"]:                                             # the split is revealed only after picking this game
            h, a = split[g["key"]]["H"], split[g["key"]]["A"]
            tot = h + a
            row["split"] = {"H": round(100 * h / tot), "A": 100 - round(100 * h / tot)} if tot else None
        games.append(row)
    return {"round": {"matchday": r["matchday"], "date": r["date"], "deadline_ts": r["deadline_ts"], "open": r["open"], "games": games,
                      "picked": len(mine), "of": len(games)}}


def cast(request, key: str, side: str, vid: str):
    """Returns (ok, reason): ok | bot | browser | side | closed | game | already | network."""
    ua = request.headers.get("User-Agent", "")
    if not ua or traffic.BOT.search(ua):
        return False, "bot"
    if not mvp.VID.match(vid or ""):
        return False, "browser"
    if side not in SIDES:
        return False, "side"
    r = _round()
    if not r or not r["open"]:
        return False, "closed"
    if key not in {g["key"] for g in r["games"]}:
        return False, "game"
    voter, net = mvp._hash("pick", vid), mvp._hash("net", key, auth.visitor_ip())
    with mvp._lock:
        con = mvp._db()
        try:
            if con.execute("SELECT 1 FROM picks WHERE game=? AND voter=?", (key, voter)).fetchone():
                return False, "already"
            if con.execute("SELECT COUNT(*) FROM picks WHERE game=? AND net=?", (key, net)).fetchone()[0] >= MAX_PER_NETWORK:
                return False, "network"
            con.execute("INSERT INTO picks VALUES (?,?,?,?,?)", (key, voter, net, side, int(time.time())))
            con.commit()
        finally:
            con.close()
    return True, "ok"


def admin_view() -> dict:
    """For the admin only: the real counts per game of the current round, and the totals."""
    r = _round()
    with mvp._lock:
        con = mvp._db()
        try:
            split = _split(con, [g["key"] for g in r["games"]]) if r else {}
            total = con.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
            people = con.execute("SELECT COUNT(DISTINCT voter) FROM picks").fetchone()[0]
        finally:
            con.close()
    return {"round": None if not r else {"matchday": r["matchday"], "date": r["date"], "open": r["open"],
            "games": [{"home": g["home"], "away": g["away"], "home_picks": split[g["key"]]["H"], "away_picks": split[g["key"]]["A"]} for g in r["games"]]},
            "total_picks": total, "people": people}
