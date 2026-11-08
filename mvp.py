"""Phase MVP: the race, the fans' vote and the winner.

A phase is 11 matchdays (phase 1 = J1-J11, phase 2 = J12-J22). For a phase:
  * the RACE ranks the candidates (qualified players of the top teams, the same pool as the season MVP) by their average
    impact over the phase's games, and draws how each candidate's average moved matchday after matchday;
  * the FANS' VOTE lets every visitor back one of three candidates: the best by stats, at most one per club. One final vote per browser; a handful per network, because mobile
    operators put many people behind one address. Only hashes are stored (no address, no browser string);
  * the phase MVP is decided by the FANS' VOTE ALONE (most votes; a tie goes to the better stats). The stats race is a separate
    ranking: it shows the best player so far and decides nothing;
  * VOTING closes at the phase's deadline (or earlier if the admin closes it). The WINNER is the player the admin crowns
    (assets/mvp_awards.json in the repo, or data/mvp.json from the admin panel, which wins); with no crown, a finished
    phase whose voting is closed goes to the player with the most votes (the stats leader if nobody voted).
"""
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from pathlib import Path

import auth
import config
import stats
import traffic

PHASE_LEN = stats.PHASE_LEN
PHASES = (1, 2)
MAX_VOTERS_PER_NETWORK = 8        # distinct browsers per network per phase (carrier-grade NAT shares addresses)
BALLOT_SIZE = 3                   # fans choose among the top N by stats; one vote each, final
RACE_LINES = 6                    # candidates drawn on the race chart
AWARDS_REPO = Path(__file__).parent / "assets" / "mvp_awards.json"
AWARDS_LIVE = config.DATA_DIR / "mvp.json"
DB_FILE = config.DATA_DIR / "votes.db"
VID = re.compile(r"^[a-f0-9]{16,64}$")
_lock = threading.Lock()
_ready = False


# ---------------------------------------------------------------- settings (who is crowned, is voting open)
def _read(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return {}


def settings(phase: int) -> dict:
    """{'winner': player id or None, 'voting_open': bool, 'note': str}. The live file overrides the repo file, key by key."""
    out = {"winner": None, "voting_open": True, "note": "", "deadline": None, "ballot": None}
    for src in (_read(AWARDS_REPO), _read(AWARDS_LIVE)):
        out.update({k: v for k, v in (src.get(str(phase)) or {}).items() if k in out})
    return out


TUNIS = timezone(timedelta(hours=1))      # Tunisia has no daylight saving time


def parse_deadline(s):
    """'2026-11-11T12:00' (Tunisian time) or with an offset -> aware datetime, None if empty, ValueError if unreadable."""
    if not s:
        return None
    d = datetime.fromisoformat(str(s))
    return d if d.tzinfo else d.replace(tzinfo=TUNIS)


def voting_open(phase: int) -> bool:
    st = settings(phase)
    try:
        dl = parse_deadline(st["deadline"])
    except ValueError:
        dl = None
    return bool(st["voting_open"]) and (dl is None or datetime.now(timezone.utc) < dl)


_settings_lock = threading.Lock()


def save_settings(phase: int, winner, voting_open: bool, note: str = "", deadline=None):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _settings_lock:
        data = _read(AWARDS_LIVE)
        dl = parse_deadline(deadline)
        prev = data.get(str(phase), {})
        data[str(phase)] = {"winner": winner or None, "voting_open": bool(voting_open), "note": (note or "")[:200],
                            "deadline": dl.astimezone(TUNIS).isoformat(timespec="minutes") if dl else None,
                            **({"ballot": prev["ballot"]} if prev.get("ballot") else {})}       # saving the other settings never unfreezes the ballot
        AWARDS_LIVE.write_text(json.dumps(data, indent=1))


def set_ballot(phase: int, ids):
    """Freeze the ballot: exactly these players can be voted for from now on (changing it later is an explicit admin action)."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _settings_lock:
        data = _read(AWARDS_LIVE)
        data.setdefault(str(phase), {})["ballot"] = list(ids)
        AWARDS_LIVE.write_text(json.dumps(data, indent=1))


# ---------------------------------------------------------------- votes
def _db():
    global _ready
    con = sqlite3.connect(DB_FILE, timeout=10)
    if not _ready:
        con.execute("CREATE TABLE IF NOT EXISTS votes(phase INTEGER, voter TEXT, net TEXT, pid TEXT, ts INTEGER, PRIMARY KEY(phase, voter))")
        con.execute("CREATE TABLE IF NOT EXISTS picks(game TEXT, voter TEXT, net TEXT, side TEXT, ts INTEGER, PRIMARY KEY(game, voter))")   # match predictions (predict.py)
        for t in ("votes", "picks"):        # a vote is final: the database itself refuses to change or delete one, whatever code or command tries
            for ev in ("UPDATE", "DELETE"):
                con.execute(f"CREATE TRIGGER IF NOT EXISTS {t}_no_{ev.lower()} BEFORE {ev} ON {t} BEGIN SELECT RAISE(ABORT, 'votes are final and cannot be changed or deleted'); END")
        con.commit()
        try:
            os.chmod(DB_FILE, 0o600)
        except OSError:
            pass
        _ready = True
    return con


def _hash(label: str, *parts) -> str:
    return hmac.new(traffic._key(), "|".join([label, *map(str, parts)]).encode(), hashlib.sha256).hexdigest()[:24]


def tally(phase: int) -> dict:
    with _lock:
        con = _db()
        try:
            return dict(con.execute("SELECT pid, COUNT(*) FROM votes WHERE phase=? GROUP BY pid", (phase,)))
        finally:
            con.close()


def my_vote(phase: int, vid: str):
    if not VID.match(vid or ""):
        return None
    with _lock:
        con = _db()
        try:
            r = con.execute("SELECT pid FROM votes WHERE phase=? AND voter=?", (phase, _hash("vid", phase, vid))).fetchone()
            return r[0] if r else None
        finally:
            con.close()


def cast(request, phase: int, pid: str, vid: str):
    """Returns (ok, reason). reason: ok | closed | candidate | browser | bot | network | already. A vote is final."""
    ua = request.headers.get("User-Agent", "")
    if not ua or traffic.BOT.search(ua):
        return False, "bot"
    if not VID.match(vid or ""):
        return False, "browser"
    if not voting_open(phase):
        return False, "closed"
    rows = candidates(phase)
    if pid not in _frozen(phase, rows, True):                  # the first vote freezes the ballot as it is shown at that moment
        return False, "candidate"
    voter, net = _hash("vid", phase, vid), _hash("net", phase, auth.visitor_ip())
    with _lock:
        con = _db()
        try:
            if con.execute("SELECT 1 FROM votes WHERE phase=? AND voter=?", (phase, voter)).fetchone():
                return False, "already"
            if con.execute("SELECT COUNT(*) FROM votes WHERE phase=? AND net=?", (phase, net)).fetchone()[0] >= MAX_VOTERS_PER_NETWORK:
                return False, "network"
            con.execute("INSERT INTO votes VALUES (?,?,?,?,?)", (phase, voter, net, pid, int(time.time())))
            con.commit()
        finally:
            con.close()
    return True, "ok"


def admin_votes(phase: int) -> dict:
    with _lock:
        con = _db()
        try:
            return {"total": con.execute("SELECT COUNT(*) FROM votes WHERE phase=?", (phase,)).fetchone()[0],
                    "networks": con.execute("SELECT COUNT(DISTINCT net) FROM votes WHERE phase=?", (phase,)).fetchone()[0],
                    "per_day": [list(r) for r in con.execute(
                        "SELECT strftime('%Y-%m-%d', ts, 'unixepoch', 'localtime'), COUNT(*) FROM votes WHERE phase=? GROUP BY 1 ORDER BY 1", (phase,))]}
        finally:
            con.close()


# ---------------------------------------------------------------- the race
def _md(g):
    return stats.matchday_hint(g)


def _phase_range(phase):
    return (phase - 1) * PHASE_LEN + 1, phase * PHASE_LEN


def _race_data(phase: int, keep=()):
    """(rows, matchdays, complete) where rows = candidates with phase-only averages, best impact first.
    `keep` = players frozen on the ballot: they stay in the rows even if they no longer meet the qualification rules."""
    d = stats.build()
    lo, hi = _phase_range(phase)
    gid = {g["id"]: _md(g) for g in d["games"]}
    in_phase = {i for i, m in gid.items() if m and lo <= m <= hi}
    box = Counter(t["code"] for g in d["games"] if g["id"] in in_phase for t in g["teams"])
    played = {r["code"]: min(PHASE_LEN, max(0, r["j"] - (phase - 1) * PHASE_LEN)) for r in d["standings"]}
    top = set(d["top_teams"])
    rows = []
    photos = stats.load_photos()
    for p in d["players"]:
        log = [r for r in p["log"] if r["game_id"] in in_phase]
        if not log:
            continue
        avail = sum(max(box[c], played.get(c, 0)) for c in p["teams"])
        need = max(1, math.ceil(stats.QUALIFY_SHARE * avail))
        n = len(log)
        mins = sum(r["min"] for r in log) / n
        if (n < need or mins < stats.MIN_MINUTES_FOR_RANKING or (top and p["team"] not in top)) and p["id"] not in keep:
            continue
        avg = lambda k: round(sum(r[k] for r in log) / n, 1)
        by_md = defaultdict(list)
        for r in log:
            by_md[gid[r["game_id"]]].append(r["impact"])
        rows.append({"id": p["id"], "name": p["name"], "team": p["team"], "number": p["number"], "pos": p["pos"], "gp": n, "need": need, "photo": photos.get(p["id"]),
                     "pts": avg("pts"), "reb": avg("reb"), "ast": avg("ast"), "stl": avg("stl"), "blk": avg("blk"), "pir": avg("pir"),
                     "impact": avg("impact"), "mvp_games": sum(r["is_mvp"] for r in log), "wins": sum(r["won"] for r in log),
                     "_by_md": dict(by_md)})
    rows.sort(key=lambda r: (r["impact"], r["pts"]), reverse=True)
    matchdays = sorted({m for m in gid.values() if m and lo <= m <= hi})
    complete = bool(d["standings"]) and all(r["j"] >= phase * PHASE_LEN for r in d["standings"])
    return rows, matchdays, complete


def candidates(phase: int):
    return _race_data(phase, keep=settings(phase)["ballot"] or ())[0]


def pick_ballot(rows):
    """The ids fans can vote for: walking down the stats ranking (best first), the best player of each team until BALLOT_SIZE, so the three
    names come from three different clubs. Never chosen by votes. With fewer clubs than seats, the best remaining players fill the rest."""
    out, teams = [], set()
    for r in rows:
        if r["team"] not in teams:
            out.append(r["id"])
            teams.add(r["team"])
        if len(out) == BALLOT_SIZE:
            return out
    return out + [r["id"] for r in rows if r["id"] not in out][:BALLOT_SIZE - len(out)]


def _frozen(phase: int, rows, votes_exist: bool):
    """The ballot as fans see it. Frozen (settings) once set. Not yet set: it follows the stats, and freezes by itself as soon as the first vote
    exists, to exactly what visitors are seeing then (a site that already has votes when this code arrives keeps its ballot untouched)."""
    st = settings(phase)["ballot"]
    ids = {r["id"] for r in rows}
    if st:
        out = [r["id"] for r in rows if r["id"] in st]                       # stats order; a frozen player stays even if he stops qualifying
        return out + [i for i in pick_ballot(rows) if i not in out][:BALLOT_SIZE - len(out)] if len(out) < BALLOT_SIZE else out
    out = pick_ballot(rows)
    if votes_exist and len(out) == BALLOT_SIZE and all(i in ids for i in out):
        set_ballot(phase, out)
    return out


def ballot(phase: int):
    rows = candidates(phase)
    return _frozen(phase, rows, bool(tally(phase)))


def race(phase: int = 1) -> dict:
    """Two separate things: the STATS race (every candidate ranked by average impact, rank/series/chart) and the FANS' vote
    (votes and share per candidate). The phase MVP is decided by the votes alone."""
    if phase not in PHASES:
        raise ValueError("phase")
    rows, matchdays, complete = _race_data(phase, keep=settings(phase)["ballot"] or ())       # best average impact first
    votes = tally(phase)
    ballot_ids = _frozen(phase, rows, bool(votes))
    total = sum(votes.get(r["id"], 0) for r in rows)
    best_impact = max((r["impact"] for r in rows), default=0) or 1
    for i, r in enumerate(rows, 1):
        r["rank"] = i                                     # rank in the stats race
        r["votes"] = votes.get(r["id"], 0)
        r["vote_share"] = round(100 * r["votes"] / total, 1) if total else 0
        r["stats_score"] = round(100 * max(r["impact"], 0) / best_impact, 1)
        acc, series = [], []
        for m in matchdays:
            acc += r["_by_md"].get(m, [])
            series.append(round(sum(acc) / len(acc), 1) if acc else None)
        r["series"] = series
        del r["_by_md"]
    # the fans' favourite: most votes, a tie goes to the better stats; nobody if nobody voted
    vote_leader = max((r for r in rows if r["votes"]), key=lambda r: (r["votes"], r["impact"]), default=None)
    st = settings(phase)
    is_open = voting_open(phase)
    try:
        dl = parse_deadline(st["deadline"])
    except ValueError:
        dl = None
    winner = next((r for r in rows if r["id"] == st["winner"]), None)       # a crown set by the admin always wins
    if winner is None and not is_open and complete and rows:
        winner = vote_leader or rows[0]                                      # voting is over: the fans decide (no votes at all: the stats leader)
    # the list shown to visitors: the ballot first (one player per club), by votes then stats; then everybody else by votes (if any) then stats
    for i, r in enumerate(sorted(rows, key=lambda r: (r["id"] in ballot_ids, r["votes"], r["impact"], r["pts"]), reverse=True), 1):
        r["vote_rank"] = i
    current = winner or vote_leader or (rows[0] if rows else None)
    current_by = "winner" if winner else "votes" if vote_leader else "stats"
    return {"phase": phase, "matchdays": matchdays, "complete": complete, "voting_open": is_open, "note": st["note"],
            "deadline": dl.isoformat() if dl else None, "deadline_ts": int(dl.timestamp()) if dl else None,
            "total_votes": total, "decided_by": "fans",
            "winner": winner, "leader": rows[0] if rows else None, "vote_leader": vote_leader,
            "current": current, "current_by": current_by,         # the MVP right now: crowned, else most votes, else (no votes yet) the stats leader
            "ballot": ballot_ids, "ballot_frozen": bool(settings(phase)["ballot"]), "suggested_ballot": pick_ballot(rows), "candidates": rows, "chart": [r["id"] for r in rows[:RACE_LINES]]}
