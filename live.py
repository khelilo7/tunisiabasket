"""Live matches: a small board the admin (or, later, a licensed data feed) updates during a game.

data/live.json = {"matches": [{id, home, away, status: scheduled|live|final, home_score, away_score, period, clock, matchday,
                               started, updated, finished, updates: [{ts, text}]}]}
Visitors only read it (GET /api/live). A finished match stays on the board for FINAL_HOURS, then it is only a news item.
Whoever updates the board - the admin's Live tab today, a feed adapter tomorrow - goes through apply(), so the rules live here.
"""
import json
import threading
import time
import uuid

import config
import stats

LIVE_FILE = config.DATA_DIR / "live.json"
FINAL_HOURS = 36
KEEP_DAYS = 60
PERIODS = ("1", "2", "3", "4", "OT")
_lock = threading.Lock()


def _load() -> dict:
    try:
        raw = json.loads(LIVE_FILE.read_text())
    except (OSError, ValueError):
        raw = {}
    return {"matches": list(raw.get("matches") or [])}


def _save(d: dict):
    cut = time.time() - KEEP_DAYS * 86400
    d["matches"] = [m for m in d["matches"] if (m.get("finished") or m.get("updated") or time.time()) > cut]
    tmp = LIVE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    tmp.replace(LIVE_FILE)


def _public(m: dict) -> dict:
    return {k: m.get(k) for k in ("id", "home", "away", "status", "home_score", "away_score", "period", "clock", "matchday", "started", "updated", "finished", "updates")}


def board(now=None) -> dict:
    """What visitors see: matches in play, and matches finished in the last FINAL_HOURS."""
    now = now or time.time()
    teams = stats.load_official()["teams"]
    out = {"live": [], "final": [], "scheduled": [], "now": int(now)}
    for m in _load()["matches"]:
        m = {**m, "home_name": teams.get(m["home"], m["home"]), "away_name": teams.get(m["away"], m["away"])}
        if m["status"] == "live":
            out["live"].append(m)
        elif m["status"] == "final" and now - (m.get("finished") or 0) < FINAL_HOURS * 3600:
            out["final"].append(m)
        elif m["status"] == "scheduled":
            out["scheduled"].append(m)
    out["live"].sort(key=lambda m: m.get("started") or 0)
    out["final"].sort(key=lambda m: m.get("finished") or 0, reverse=True)
    out["scheduled"].sort(key=lambda m: m.get("start_ts") or 0)
    return out


def all_matches() -> list:
    teams = stats.load_official()["teams"]
    return [{**m, "home_name": teams.get(m["home"], m["home"]), "away_name": teams.get(m["away"], m["away"])}
            for m in sorted(_load()["matches"], key=lambda m: -(m.get("updated") or 0))]


def finals_since(days: int = 7) -> list:
    cut = time.time() - days * 86400
    return [m for m in _load()["matches"] if m["status"] == "final" and (m.get("finished") or 0) > cut]


def _note(m, text="", kind="note", **args):
    """kind 'note' = the admin's own words; other kinds (tipoff, end_period, final) are worded by the page in the visitor's language."""
    m.setdefault("updates", []).insert(0, {"ts": int(time.time()), "kind": kind, "text": text[:240], **args})
    del m["updates"][60:]


def apply(op: str, body: dict) -> dict:
    """Create / update / finish / delete a match. Returns the match (or {} for delete). Raises ValueError with a readable message."""
    teams = stats.load_official()["teams"]
    now = int(time.time())
    with _lock:
        d = _load()
        by = {m["id"]: m for m in d["matches"]}
        if op == "create":
            home, away = str(body.get("home") or "").upper(), str(body.get("away") or "").upper()
            if home not in teams or away not in teams or home == away:
                raise ValueError("Choose two different teams.")
            if any(m["status"] == "live" and {m["home"], m["away"]} == {home, away} for m in d["matches"]):
                raise ValueError("This match is already live.")
            m = {"id": uuid.uuid4().hex[:10], "home": home, "away": away, "status": "live" if body.get("start") else "scheduled", "home_score": 0, "away_score": 0,
                 "period": "1", "clock": "10:00", "matchday": str(body.get("matchday") or "")[:8], "updated": now, "updates": []}
            if m["status"] == "live":
                m["started"] = now
                _note(m, "Tip-off", "tipoff")
            d["matches"].append(m)
        else:
            m = by.get(str(body.get("id") or ""))
            if not m:
                raise ValueError("Unknown match.")
            if op == "delete":
                d["matches"].remove(m)
                _save(d)
                return {}
            if op == "start":
                m.update(status="live", started=now)
                _note(m, "Tip-off", "tipoff")
            elif op == "update":
                if m["status"] == "final":
                    raise ValueError("The match is over. Reopen it to change the score.")
                if "period" in body:
                    p = str(body["period"])
                    if p not in PERIODS:
                        raise ValueError("Period must be 1, 2, 3, 4 or OT.")
                    if p != m.get("period"):
                        _note(m, f"End of period {m['period']}", "end_period", period=m["period"], home_score=m["home_score"], away_score=m["away_score"])   # score as it stood BEFORE this update
                    m["period"] = p
                for k in ("home_score", "away_score"):
                    if k in body:
                        v = int(body[k])
                        if not 0 <= v <= 250:
                            raise ValueError("Score out of range.")
                        m[k] = v
                if "clock" in body:
                    c = str(body["clock"]).strip()[:6]
                    m["clock"] = c
                if body.get("note"):
                    _note(m, str(body["note"]))
                if m["status"] == "scheduled":
                    m.update(status="live", started=now)
            elif op == "finish":
                m.update(status="final", finished=now, clock="00:00")
                _note(m, f"Final {m['home_score']}–{m['away_score']}", "final", home_score=m["home_score"], away_score=m["away_score"])
            elif op == "reopen":
                m.update(status="live", finished=None)
            else:
                raise ValueError("Unknown operation.")
            m["updated"] = now
        _save(d)
        return m
