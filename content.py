"""Editorial content managed from the admin panel: the schedule overlay (kick-off time, date, featured rank per game), news, and the optional
stats typed with a hand-entered result. Plain JSON files in the data folder (kept across deployments, included in the backups)."""
import json
import re
import threading
import time
import uuid
from datetime import date, datetime

import config
import stats

SCHEDULE_FILE = stats.SCHEDULE_FILE
NEWS_FILE = config.DATA_DIR / "news.json"
NOTES_FILE = config.DATA_DIR / "result_notes.json"
LABELS = ("official", "injury", "transfer", "result", "info", "interview")
FACEBOOK = "https://www.facebook.com/people/Tunisia-Basket/61596371069928/"
_lock = threading.Lock()
KEY = re.compile(r"^\d{1,2}:[A-Z0-9]{1,8}-[A-Z0-9]{1,8}$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
STAT_KEYS = ("pts", "reb", "ast", "stl", "blk")


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _write(path, data):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


def game_key(md, home, away):
    return f"{int(md)}:{home}-{away}"


def _iso(s):
    try:
        return date.fromisoformat(str(s)).isoformat()
    except ValueError:
        raise ValueError("The date must look like 2026-11-14.")


# ---------------------------------------------------------------- schedule: time, date and featured rank of a game
def known_game(key):
    """True when the key is a game of the calendar (so the file never collects junk)."""
    return any(g["key"] == key for m in stats.planning()["matchdays"] for g in m["games"])


def set_schedule(key, time_=None, date_=None, featured=None):
    """Empty values clear that field; a game with nothing left is removed from the file."""
    if not KEY.match(key or "") or not known_game(key):
        raise ValueError("That game is not in the calendar.")
    entry = {}
    if time_:
        if not TIME.match(str(time_)):
            raise ValueError("The time must look like 18:30.")
        entry["time"] = str(time_)
    if date_:
        entry["date"] = _iso(date_)
    if featured not in (None, ""):
        f = int(featured)
        if not 1 <= f <= 99:
            raise ValueError("The rank is a number from 1 to 99.")
        entry["featured"] = f
    with _lock:
        data = _read(SCHEDULE_FILE, {})
        if entry:
            data[key] = entry
        else:
            data.pop(key, None)
        _write(SCHEDULE_FILE, data)
    return entry


# ---------------------------------------------------------------- optional stats typed with a hand-entered result
def _num(v):
    n = int(v)
    if not 0 <= n <= 99:
        raise ValueError("Stats are numbers from 0 to 99.")
    return n


def set_notes(key, note="", players=None):
    """note: a sentence. players: [{name, team, pts, reb, ast, stl, blk}] (any stat may be empty). Nothing left -> the entry is removed."""
    if not KEY.match(key or ""):
        raise ValueError("Bad game.")
    out = []
    for p in (players or [])[:10]:
        name = str(p.get("name") or "").strip()[:60]
        if not name:
            continue
        row = {"name": name, "team": str(p.get("team") or "")[:8]}
        for k in STAT_KEYS:
            if p.get(k) not in (None, ""):
                row[k] = _num(p[k])
        out.append(row)
    entry = {k: v for k, v in (("note", str(note or "").strip()[:300]), ("players", out)) if v}
    with _lock:
        data = _read(NOTES_FILE, {})
        if entry:
            data[key] = entry
        else:
            data.pop(key, None)
        _write(NOTES_FILE, data)


def load_notes():
    return _read(NOTES_FILE, {})


# ---------------------------------------------------------------- news
def _clean_news(b):
    label = str(b.get("label") or "info")
    title, body = str(b.get("title") or "").strip(), str(b.get("body") or "").strip()
    if label not in LABELS:
        raise ValueError("Unknown label.")
    if not 1 <= len(title) <= 140:
        raise ValueError("The title is required (140 characters at most).")
    if len(body) > 2000:
        raise ValueError("The text is limited to 2000 characters.")
    return {"label": label, "title": title, "body": body, "title_en": str(b.get("title_en") or "").strip()[:140], "body_en": str(b.get("body_en") or "").strip()[:2000],
            "date": _iso(b.get("date") or datetime.now().date().isoformat()), "pinned": bool(b.get("pinned"))}


def load_news(limit=None):
    """Pinned first, then newest first."""
    items = sorted(_read(NEWS_FILE, []), key=lambda n: (bool(n.get("pinned")), n.get("date", ""), n.get("ts", 0)), reverse=True)
    return items[:limit] if limit else items


def save_news(b):
    """With an id: update that item; without: add a new one. Returns the item."""
    clean = _clean_news(b)
    with _lock:
        items = _read(NEWS_FILE, [])
        nid = str(b.get("id") or "")
        cur = next((n for n in items if n["id"] == nid), None) if nid else None
        if nid and not cur:
            raise ValueError("That news item does not exist any more.")
        if cur:
            cur.update(clean)
        else:
            cur = {"id": uuid.uuid4().hex[:8], "ts": int(time.time()), **clean}
            items.append(cur)
        _write(NEWS_FILE, items)
    return cur


def delete_news(nid):
    with _lock:
        items = _read(NEWS_FILE, [])
        keep = [n for n in items if n["id"] != str(nid)]
        _write(NEWS_FILE, keep)
        return len(items) - len(keep)


# ---------------------------------------------------------------- the latest games of the home page: box scores AND results typed by hand
def _item_from_game(g, md):
    return {"id": g["id"], "date": g["date"], "date_approx": g.get("date_approx"), "matchday": g.get("matchday"), "md": md, "mvp": g.get("mvp"), "score_note": g.get("score_note"),
            "teams": [{"code": t["code"], "name": t["name"], "points": t["points"]} for t in g["teams"]]}


def recent_results(limit=8, d=None):
    """Newest first (highest matchday, then date). A result without a box score is listed too, with its optional note and stats and no link."""
    d = d or stats.build()
    o = stats.load_official()
    cal, notes, sched, names = stats.load_calendar(), load_notes(), stats._schedule(), o["teams"]
    box = {(stats.matchday_hint(g), frozenset(t["code"] for t in g["teams"])): g for g in d["games"]}
    items, used = [], set()
    for r in o["results"]:
        g = box.get((r["matchday"], frozenset([r["home"], r["away"]])))
        if g:
            used.add(g["id"])
            items.append(_item_from_game(g, r["matchday"]))
            continue
        md, h, a = r["matchday"], r["home"], r["away"]
        s = sched.get(game_key(md, h, a)) or sched.get(game_key(md, a, h)) or {}
        n = notes.get(game_key(md, h, a)) or notes.get(game_key(md, a, h)) or {}
        items.append({"id": None, "date": s.get("date") or cal.get(md), "date_approx": False, "matchday": f"J{md}", "md": md, "mvp": None, "score_note": None, "time": s.get("time"),
                      "teams": [{"code": h, "name": names.get(h, h), "points": r["home_score"]}, {"code": a, "name": names.get(a, a), "points": r["away_score"]}],
                      "note": n.get("note"), "players": n.get("players") or []})
    items += [_item_from_game(g, stats.matchday_hint(g)) for g in d["games"] if g["id"] not in used]
    items.sort(key=lambda x: (x.get("md") or 0, x.get("date") or ""), reverse=True)
    return items[:limit]
