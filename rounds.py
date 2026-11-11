"""Player of the round: the fans' vote for the best player of ONE matchday, among the players of the game of that matchday.

  * The admin opens the vote of a matchday (admin panel, MVP tab). It can only be opened once EVERY game of the matchday has its official result, and at least one game has a
    player of the game (a box score, or a one-team sheet of the winner): the candidates are those players of the game, one per game. The ballot is frozen when the vote opens
    (the admin can add the players of games whose stats arrive later; nobody is ever removed).
  * One final vote per browser, a handful per network, crawlers refused, only hashes stored: the same rules, and the same database (data/votes.db, table round_votes, which refuses
    changes and deletions), as the phase MVP vote.
  * The vote ends at its optional deadline or when the admin closes it. The winner is the admin's crown if any, else the player with most votes (a tie goes to the better PIR, then
    points); nobody if nobody voted. The result stays on the home page for WINNER_DAYS days, the winners of the earlier rounds stay on the MVP page.
Settings live in data/rounds.json: {"12": {"open", "ballot", "deadline", "winner", "note", "opened_at", "closed_at"}}.
"""
import json
import threading
import time
from datetime import datetime, timezone

import auth
import config
import mvp
import stats
import traffic

FILE = config.DATA_DIR / "rounds.json"
WINNER_DAYS = 3                 # a finished round stays on the home page this long
MAX_VOTERS_PER_NETWORK = mvp.MAX_VOTERS_PER_NETWORK
_lock = threading.Lock()


# ---------------------------------------------------------------- settings
def load() -> dict:
    try:
        raw = json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in raw.items() if str(k).isdigit() and isinstance(v, dict)}


def _write(data: dict):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(FILE)


def _deadline(st):
    try:
        return mvp.parse_deadline(st.get("deadline"))
    except ValueError:
        return None


def is_open(md: int) -> bool:
    st = load().get(str(md)) or {}
    dl = _deadline(st)
    return bool(st.get("open")) and (dl is None or datetime.now(timezone.utc) < dl)


def _closed_ts(st):
    """When the vote ended (the deadline if it ran out by itself, else the admin's click); None while open."""
    dl = _deadline(st)
    if st.get("open") and dl is not None and datetime.now(timezone.utc) >= dl:
        return int(dl.timestamp())
    return None if st.get("open") else st.get("closed_at")


# ---------------------------------------------------------------- the candidates: the players of the game of a matchday
def expected_games() -> int:
    return len(stats.load_official()["teams"]) // 2


def results_in(md: int) -> int:
    return sum(1 for r in stats.load_official()["results"] if r["matchday"] == md)


def candidates(md: int, d=None) -> list:
    d = d or stats.build()
    byid = {p["id"]: p for p in d["players"]}
    photos = stats.load_photos()
    out = []
    for g in [*d["games"], *d["partials"]]:
        m = g.get("mvp")
        if g.get("matchday_no") != md or not m or m["player_id"] not in byid:
            continue
        mine = next(t for t in g["teams"] if t["code"] == m["team"])
        opp = next(t for t in g["teams"] if t["code"] != m["team"])
        p = byid[m["player_id"]]
        out.append({"id": p["id"], "name": p["name"], "team": m["team"], "number": p["number"], "pos": p["pos"], "photo": photos.get(p["id"]),
                    "pts": m["pts"], "reb": m["reb"], "ast": m["ast"], "pir": m.get("pir"),
                    "game": {"id": g["id"], "opp": opp["code"], "score": f"{mine['points']}–{opp['points']}", "partial": bool(g.get("partial"))}})
    return out


def status(md: int, d=None) -> dict:
    """Can the vote of this matchday be opened? {matchday, results, expected, candidates, state, can_open, reason}"""
    st = load().get(str(md)) or {}
    n, exp = results_in(md), expected_games()
    cands = candidates(md, d)
    other = next((int(m) for m in load() if int(m) != md and is_open(int(m))), None)
    reason = ""
    if n < exp:
        reason = f"J{md}: {n} of {exp} results are in. The vote can only open once every game is over."
    elif not cands:
        reason = f"J{md}: no player of the game yet. Add the box score (or a sheet) of at least one game."
    elif other:
        reason = f"The vote of J{other} is still open: close it first."
    state = "open" if is_open(md) else "closed" if st else "ready" if not reason else "waiting"
    return {"matchday": md, "results": n, "expected": exp, "candidates": len(cands), "state": state, "can_open": not reason, "reason": reason}


# ---------------------------------------------------------------- admin actions
def act(op: str, md: int, deadline=None, winner=None, note=None):
    """op: open | close | refresh | crown. Returns (ok, message)."""
    with _lock:
        data = load()
        st = data.get(str(md)) or {}
        cands = candidates(md)
        ids = [c["id"] for c in cands]
        if op == "open":
            s = status(md)
            if not s["can_open"]:
                return False, s["reason"]
            try:
                dl = mvp.parse_deadline(deadline)
            except ValueError:
                return False, "The deadline must look like 2026-11-14T12:00 (Tunisian time)."
            ballot = list(st.get("ballot") or [])
            ballot += [i for i in ids if i not in ballot]                       # frozen when it opens; later openings only add
            data[str(md)] = {**st, "open": True, "ballot": ballot, "deadline": dl.astimezone(mvp.TUNIS).isoformat(timespec="minutes") if dl else None,
                             "winner": st.get("winner"), "note": (str(note or st.get("note") or ""))[:200], "opened_at": st.get("opened_at") or int(time.time()), "closed_at": None}
            msg = f"The vote for the player of J{md} is open ({len(ballot)} players)."
        elif not st:
            return False, f"The vote of J{md} was never opened."
        elif op == "close":
            data[str(md)] = {**st, "open": False, "closed_at": int(time.time())}
            msg = f"The vote of J{md} is closed."
        elif op == "refresh":
            ballot = list(st.get("ballot") or [])
            added = [i for i in ids if i not in ballot]
            data[str(md)] = {**st, "ballot": ballot + added}
            msg = f"{len(added)} player(s) added to the ballot of J{md}." if added else f"Nothing to add: the ballot of J{md} already has every player of the game."
        elif op == "crown":
            if winner and winner not in (st.get("ballot") or []):
                return False, "Only a player of the ballot can be crowned."
            data[str(md)] = {**st, "winner": winner or None}
            msg = f"Crowned: {winner}." if winner else "The crown is removed: the fans decide."
        else:
            return False, "Unknown action."
        _write(data)
    return True, msg


# ---------------------------------------------------------------- votes
def tally(md: int) -> dict:
    with mvp._lock:
        con = mvp._db()
        try:
            return dict(con.execute("SELECT pid, COUNT(*) FROM round_votes WHERE round=? GROUP BY pid", (md,)))
        finally:
            con.close()


def my_vote(md: int, vid: str):
    if not mvp.VID.match(vid or ""):
        return None
    with mvp._lock:
        con = mvp._db()
        try:
            r = con.execute("SELECT pid FROM round_votes WHERE round=? AND voter=?", (md, mvp._hash("rvid", md, vid))).fetchone()
            return r[0] if r else None
        finally:
            con.close()


def cast(request, md: int, pid: str, vid: str):
    """(ok, reason): ok | bot | browser | closed | candidate | already | network. A vote is final."""
    ua = request.headers.get("User-Agent", "")
    if not ua or traffic.BOT.search(ua):
        return False, "bot"
    if not mvp.VID.match(vid or ""):
        return False, "browser"
    if not is_open(md):
        return False, "closed"
    if pid not in ((load().get(str(md)) or {}).get("ballot") or []):
        return False, "candidate"
    voter, net = mvp._hash("rvid", md, vid), mvp._hash("rnet", md, auth.visitor_ip())
    with mvp._lock:
        con = mvp._db()
        try:
            if con.execute("SELECT 1 FROM round_votes WHERE round=? AND voter=?", (md, voter)).fetchone():
                return False, "already"
            if con.execute("SELECT COUNT(*) FROM round_votes WHERE round=? AND net=?", (md, net)).fetchone()[0] >= MAX_VOTERS_PER_NETWORK:
                return False, "network"
            con.execute("INSERT INTO round_votes VALUES (?,?,?,?,?)", (md, voter, net, pid, int(time.time())))
            con.commit()
        finally:
            con.close()
    return True, "ok"


# ---------------------------------------------------------------- what visitors see
def _ranked(md: int, st: dict, d=None) -> list:
    """The ballot with votes and shares, most votes first (a tie: better PIR, then points)."""
    cands = {c["id"]: c for c in candidates(md, d)}
    votes = tally(md)
    rows = [{**cands[i], "votes": votes.get(i, 0)} for i in (st.get("ballot") or []) if i in cands]
    total = sum(r["votes"] for r in rows)
    for r in rows:
        r["vote_share"] = round(100 * r["votes"] / total, 1) if total else 0
    rows.sort(key=lambda r: (r["votes"], r["pir"] if r["pir"] is not None else -999, r["pts"]), reverse=True)
    return rows


def _winner(st: dict, rows: list):
    if st.get("winner"):
        w = next((r for r in rows if r["id"] == st["winner"]), None)
        if w:
            return w
    if _closed_ts(st) is None:
        return None
    return next((r for r in rows if r["votes"]), None)


def view(vid: str = "") -> dict:
    """The round the site shows (the open one, else the last one that ended less than WINNER_DAYS ago), and the winners of the earlier rounds."""
    data = load()
    d = stats.build()
    mds = sorted((int(m) for m in data), reverse=True)
    cur = next((m for m in mds if is_open(m)), None)
    if cur is None:
        cur = next((m for m in mds if (_closed_ts(data[str(m)]) or 0) > time.time() - WINNER_DAYS * 86400), None)
    out = {"round": None, "history": []}
    for m in mds:
        if m == cur:
            continue
        st = data[str(m)]
        w = _winner(st, _ranked(m, st, d))
        if w:
            out["history"].append({"round": m, "winner": {k: w[k] for k in ("id", "name", "team", "number", "photo", "votes", "vote_share")}, "game": w["game"]})
    out["history"] = out["history"][:8]
    if cur is None:
        return out
    st = data[str(cur)]
    rows = _ranked(cur, st, d)
    dl = _deadline(st)
    win = _winner(st, rows)
    out.update(round=cur, open=is_open(cur), deadline_ts=int(dl.timestamp()) if dl else None, note=st.get("note") or "", total_votes=sum(r["votes"] for r in rows),
               candidates=rows, winner=win, my_vote=my_vote(cur, vid))
    return out


def admin_view() -> dict:
    """Every matchday with results (latest first): can its vote be opened, and the state of the votes already opened."""
    data = load()
    d = stats.build()
    mds = sorted({r["matchday"] for r in stats.load_official()["results"]} | {int(m) for m in data}, reverse=True)[:8]
    out = []
    for m in mds:
        s = status(m, d)
        st = data.get(str(m)) or {}
        rows = _ranked(m, st, d) if st else []
        s.update(votes=sum(r["votes"] for r in rows), ballot=[{k: r[k] for k in ("id", "name", "team", "votes", "vote_share")} for r in rows], winner=st.get("winner"),
                 leader=(_winner(st, rows) or {}).get("id"), deadline=st.get("deadline"), note=st.get("note") or "", possible=[{k: c[k] for k in ("id", "name", "team")} for c in candidates(m, d)])
        out.append(s)
    return {"rounds": out}
