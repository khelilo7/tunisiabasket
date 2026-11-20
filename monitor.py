"""The admin's Server tab in one answer (GET /admin/api/monitor): the machine and the app (health.py), the website (traffic.py),
the mobile app's users (traffic.app_summary), push notification sign-ups (notify.py's data/push.json) and fan activity (votes and
predictions in data/votes.db). Read-only: it only counts what is already stored. Admin login required (admin.py's blueprint)."""
import time
from collections import Counter

import health
import mvp
import notify
import traffic

VOTE_TABLES = {"mvp": "votes", "round": "round_votes", "play": "play_votes", "predictions": "picks"}


def push_summary(now=None) -> dict:
    """Phones registered for notifications. Each app refreshes its registration when it opens, so 'seen in 7/30 days' ~ phones still in use."""
    now = now or time.time()
    subs = notify._read(notify.FILE, {})
    vals = list(subs.values())
    topics = {t: sum(1 for s in vals if s.get(t, True)) for t in notify.TOPICS}
    teams = Counter(s.get("team") for s in vals if s.get("level") == "team" and s.get("team"))
    return {
        "total": len(vals),
        "seen_7d": sum(1 for s in vals if now - (s.get("ts") or 0) <= 7 * 86400),
        "seen_30d": sum(1 for s in vals if now - (s.get("ts") or 0) <= 30 * 86400),
        "levels": dict(Counter(s.get("level") for s in vals)),
        "langs": dict(Counter(s.get("lang") or "fr" for s in vals)),
        "topics": topics,
        "teams": teams.most_common(),
    }


def votes_summary(days: int = 30) -> dict:
    """Votes and predictions: totals, today, last 7 days and per day (Tunisian days). Votes from the app and from the website are counted together."""
    days = max(1, min(int(days), 365))
    since = traffic._day(days - 1)
    day_sql = "strftime('%Y-%m-%d', ts, 'unixepoch', '+1 hours')"
    out, per_day = {}, {}
    with mvp._lock:
        con = mvp._db()
        try:
            for kind, table in VOTE_TABLES.items():
                total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                rows = dict(con.execute(f"SELECT {day_sql} d, COUNT(*) FROM {table} WHERE {day_sql} >= ? GROUP BY d", (since,)))
                per_day[kind] = rows
                out[kind] = {"total": total, "today": rows.get(traffic._day(), 0),
                             "last_7d": sum(n for d, n in rows.items() if d >= traffic._day(6)), "period": sum(rows.values())}
        finally:
            con.close()
    series = [{"day": d, **{k: per_day[k].get(d, 0) for k in VOTE_TABLES}} for d in (traffic._day(i) for i in range(days - 1, -1, -1))]
    return {"days": days, "kinds": out, "series": series}


def view(rng: str = "24h", days=30) -> dict:
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 30
    return {
        "health": health.status(),
        "chart": health.series(rng),
        "web": traffic.web_summary(days),
        "app": traffic.app_summary(days),
        "push": push_summary(),
        "votes": votes_summary(days),
    }
