"""Players who will not play (injured, suspended, left the club...), set by the admin.

Stored in data/absences.json as {"players": {player id: {"note": "...", "since": "YYYY-MM-DD"}}}. The only thing the site does with it is to leave those players out of the
EXPECTED starting five (lineups.py); nothing else changes (stats, rankings, profiles). The note is for the admin only and is never shown to the public.
"""
import datetime
import json
import threading

import config

FILE = config.DATA_DIR / "absences.json"
_lock = threading.Lock()


def load() -> dict:
    """{player id: {"note", "since"}}"""
    try:
        raw = json.loads(FILE.read_text()).get("players") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return {k: {"note": str(v.get("note") or "")[:120], "since": str(v.get("since") or "")} for k, v in raw.items() if isinstance(v, dict)}


def ids() -> set:
    return set(load())


def set_absent(pid: str, absent: bool, note: str = "") -> dict:
    """Mark (absent=True, with an optional short note) or clear a player. Returns the new {id: entry}."""
    with _lock:
        cur = load()
        if absent:
            cur[pid] = {"note": str(note or "").strip()[:120], "since": cur.get(pid, {}).get("since") or datetime.date.today().isoformat()}
        else:
            cur.pop(pid, None)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"players": cur}, indent=1, ensure_ascii=False))
        tmp.replace(FILE)
        return cur
