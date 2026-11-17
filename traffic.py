"""Visitor statistics without cookies and without storing anything personal.

What is stored per page view: day, time, page, country (from Cloudflare's CF-IPCountry header), referring site,
device type, language, and two codes. The visitor code is a hash of IP + browser + the day + a secret key, so it
lets us count distinct visitors per day but cannot be turned back into an address, and the same person gets a different
code tomorrow. The second code is a hash of a random id the browser keeps (never derived from the address): it is what tells a
returning visitor from a new one, and it is one device/browser, not one human. IP addresses are never written to disk. Crawlers are ignored, and so is the admin.
"""
import datetime
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlparse

import auth
import config
import seo

DB_FILE = config.DATA_DIR / "traffic.db"
KEY_FILE = config.DATA_DIR / "traffic.key"
KEEP_DAYS = 400
MAX_PER_VISITOR_DAY = 600          # anything above is a script, not a person
BOT = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview|monitor|uptime|curl|wget|python|httpclient|headless|lighthouse|pingdom|scrapy|go-http", re.I)
TUNIS = datetime.timezone(datetime.timedelta(hours=1))        # Tunisia has no daylight saving time: the days of the statistics are Tunisian days, whatever the server's clock
MAX_FOLLOWS_PER_VISITOR_DAY = 6
_lock = threading.Lock()
_ready = False


def _now():
    return datetime.datetime.now(TUNIS)


def _day(offset=0):
    return (_now() - datetime.timedelta(days=offset)).strftime("%Y-%m-%d")


def _db():
    global _ready
    con = sqlite3.connect(DB_FILE, timeout=10)
    if not _ready:
        con.execute("""CREATE TABLE IF NOT EXISTS hits(ts INTEGER, day TEXT, page TEXT, path TEXT, country TEXT, ref TEXT, device TEXT, lang TEXT, visitor TEXT)""")
        if "rid" not in [r[1] for r in con.execute("PRAGMA table_info(hits)")]:
            con.execute("ALTER TABLE hits ADD COLUMN rid TEXT DEFAULT ''")       # returning-visitor code (added later)
        # the club a visitor chose to follow (optional): one row per browser code (a keyed hash, never the code itself), the latest choice wins
        con.execute("CREATE TABLE IF NOT EXISTS follows(rid TEXT PRIMARY KEY, team TEXT, ts INTEGER, day TEXT, visitor TEXT)")
        con.execute("CREATE INDEX IF NOT EXISTS hits_day ON hits(day)")
        con.execute("CREATE INDEX IF NOT EXISTS hits_rid ON hits(rid)")
        con.execute("DELETE FROM hits WHERE ts < ?", (time.time() - KEEP_DAYS * 86400,))
        con.commit()
        try:
            os.chmod(DB_FILE, 0o600)
        except OSError:
            pass
        _ready = True
    return con


def _key() -> bytes:
    if not KEY_FILE.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(secrets.token_hex(32))
        os.chmod(KEY_FILE, 0o600)
    return bytes.fromhex(KEY_FILE.read_text().strip())


def _device(ua: str) -> str:
    u = ua.lower()
    if "ipad" in u or "tablet" in u:
        return "tablet"
    return "mobile" if re.search(r"mobi|android|iphone", u) else "desktop"


def _referrer(ref: str, host: str) -> str:
    """Only the site name (never the full address); '' = direct visit or from this site."""
    try:
        h = (urlparse(ref).hostname or "").lower()
    except ValueError:
        return ""
    h = h.removeprefix("www.")
    if not h or h == host.lower().removeprefix("www."):
        return ""
    return h[:80]


RID = re.compile(r"^[a-f0-9]{32}$")


def record(request, path: str, ref: str = "", lang: str = "", rid: str = ""):
    """Store one page view. Returns True if it was counted."""
    ua = request.headers.get("User-Agent", "")
    if not ua or BOT.search(ua) or auth.is_admin():
        return False
    parsed = seo.parse_path(path)
    if not parsed:
        return False                                   # only real pages of the site, nothing else
    plang, page, arg = parsed
    day = _day()
    visitor = hmac.new(_key(), f"{day}|{auth.visitor_ip()}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
    # Returning-visitor code: a random id the browser keeps, stored only as a keyed hash. Unlike `visitor` it does not change daily,
    # which is what lets us tell a new person from one who comes back. No id (storage blocked, old page) = not counted as new/returning.
    rid_hash = hmac.new(_key(), f"ret|{rid}".encode(), hashlib.sha256).hexdigest()[:16] if RID.match(rid or "") else ""
    # Cloudflare adds the visitor's country; if it is not in front of the site there is no header and no country.
    c = (request.headers.get("CF-IPCountry") or "").strip().upper()
    country = c if re.fullmatch(r"[A-Z]{2}", c) and c not in ("XX", "T1") else ""
    with _lock:
        con = _db()
        try:
            n = con.execute("SELECT COUNT(*) FROM hits WHERE day=? AND visitor=?", (day, visitor)).fetchone()[0]
            if n >= MAX_PER_VISITOR_DAY:
                return False
            con.execute("INSERT INTO hits(ts,day,page,path,country,ref,device,lang,visitor,rid) VALUES (?,?,?,?,?,?,?,?,?,?)", (
                int(time.time()), day, page, f"{page}/{arg}" if arg else page, country, _referrer(ref, request.host), _device(ua),
                plang, visitor, rid_hash))
            con.commit()
        finally:
            con.close()
    return True


def follow(request, team: str, rid: str):
    """Remember the club a visitor follows (optional, chosen by the visitor): returns True if it was stored. `team` must already be checked against the official team list.
    Like page views: no cookie, no address, a keyed hash of the browser's random code, bots and the admin ignored, a few changes per day at most."""
    ua = request.headers.get("User-Agent", "")
    if not ua or BOT.search(ua) or auth.is_admin() or not RID.match(rid or ""):
        return False
    day = _day()
    visitor = hmac.new(_key(), f"{day}|{auth.visitor_ip()}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
    rid_hash = hmac.new(_key(), f"ret|{rid}".encode(), hashlib.sha256).hexdigest()[:16]
    with _lock:
        con = _db()
        try:
            if con.execute("SELECT COUNT(*) FROM follows WHERE day=? AND visitor=?", (day, visitor)).fetchone()[0] >= MAX_FOLLOWS_PER_VISITOR_DAY:
                return False
            if team:
                con.execute("INSERT OR REPLACE INTO follows(rid, team, ts, day, visitor) VALUES (?,?,?,?,?)", (rid_hash, team, int(time.time()), day, visitor))
            else:
                con.execute("DELETE FROM follows WHERE rid=?", (rid_hash,))          # "no club": the visitor took his choice back
            con.commit()
        finally:
            con.close()
    return True


def _rows(con, sql, *args):
    return [list(r) for r in con.execute(sql, args)]


def _labels(paths):
    """{path: readable name} for the most viewed pages: a player id becomes his name, a game its two teams, a team its name."""
    out = {}
    try:
        import stats
        d = stats.build()
        names = {p["id"]: p["name"] for p in d["players"]}
        teams = stats.load_official()["teams"]
        games = {g["id"]: g for g in [*d["games"], *d["partials"]]}
    except Exception:
        return out
    for path in paths:
        page, _, arg = path.partition("/")
        if page == "player":
            pid = re.match(r"^([a-z0-9]+-\d+)", arg)
            if pid and pid.group(1) in names:
                out[path] = names[pid.group(1)].title()
        elif page == "team" and arg.upper() in teams:
            out[path] = teams[arg.upper()]
        elif page == "game" and arg in games:
            g = games[arg]
            out[path] = " – ".join(t["code"] for t in g["teams"]) + (f" ({g['matchday']})" if g.get("matchday") else "")
    return out


def _clubs(con, since):
    """Activity per club: followers (people who chose it), and the people and views of its team page and of its players' pages in the period."""
    try:
        import stats
        names = stats.load_official()["teams"]
    except Exception:
        names = {}
    views = {}
    for path, n, u in con.execute("SELECT path, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND (page='team' OR page='player') GROUP BY path", (since,)):
        page, _, arg = path.partition("/")
        code = arg.upper() if page == "team" else (re.match(r"^([a-z]+)-\d", arg) or [None, ""])[1].upper()
        if code in names:
            v = views.setdefault(code, [0, 0])
            v[0] += n
            v[1] += u
    fol = dict(con.execute("SELECT team, COUNT(*) FROM follows GROUP BY team"))
    new = dict(con.execute("SELECT team, COUNT(*) FROM follows WHERE day>=? GROUP BY team", (since,)))
    rows = [{"code": c, "name": names[c], "followers": fol.get(c, 0), "new_followers": new.get(c, 0), "views": views.get(c, [0, 0])[0], "visitors": views.get(c, [0, 0])[1]} for c in names]
    rows.sort(key=lambda r: (-r["followers"], -r["views"], r["code"]))
    return rows


def summary(days: int = 30) -> dict:
    days = max(1, min(int(days), 365))
    since = _day(days - 1)
    prev_since = _day(2 * days - 1)
    with _lock:
        con = _db()
        try:
            today = _day()
            per_day = {d: [v, u] for d, v, u in con.execute(
                "SELECT day, COUNT(*), COUNT(DISTINCT visitor) FROM hits WHERE day>=? GROUP BY day", (since,))}
            series = []
            for i in range(days - 1, -1, -1):
                d = _day(i)
                v, u = per_day.get(d, [0, 0])
                series.append({"day": d, "weekday": datetime.date.fromisoformat(d).weekday(), "views": v, "visitors": u})
            tot = con.execute("SELECT COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=?", (since,)).fetchone()
            before = con.execute("SELECT COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND day<?", (prev_since, since)).fetchone()
            # new vs returning people (by the browser's own code): new = first ever visit inside the period and only one day of visits;
            # returning = seen on 2+ different days (before or during the period)
            new_by_day = dict(con.execute("SELECT fd, COUNT(*) FROM (SELECT MIN(day) fd FROM hits WHERE rid!='' GROUP BY rid) WHERE fd>=? GROUP BY fd", (since,)))
            for s in series:
                s["new"] = new_by_day.get(s["day"], 0)
            ppl = con.execute("SELECT MIN(day), COUNT(DISTINCT CASE WHEN day>=? THEN day END) FROM hits WHERE rid!='' GROUP BY rid HAVING MAX(day)>=?", (since, since)).fetchall()
            returning = sum(1 for fd, n in ppl if fd < since or n >= 2)
            freq = {"1": 0, "2-3": 0, "4-7": 0, "8+": 0}
            for fd, n in ppl:
                freq["1" if n <= 1 else "2-3" if n <= 3 else "4-7" if n <= 7 else "8+"] += 1
            people = {"total": len(ppl), "returning": returning, "new": len(ppl) - returning, "frequency": freq,
                      "unidentified": con.execute("SELECT COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND rid=''", (since,)).fetchone()[0]}
            pages = _rows(con, "SELECT path, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY path ORDER BY 2 DESC LIMIT 25", since)
            labels = _labels([p[0] for p in pages])
            return {
                "days": days, "since": since, "tz": "Tunisia time (UTC+1)",
                "views": tot[0], "visitors": tot[1],            # visitors = distinct people per day, added up over the period
                "previous": {"views": before[0], "visitors": before[1]},          # the same number of days just before, to see the trend
                "today": {"views": per_day.get(today, [0, 0])[0], "visitors": per_day.get(today, [0, 0])[1]},
                "online": con.execute("SELECT COUNT(DISTINCT visitor) FROM hits WHERE ts>?", (time.time() - 300,)).fetchone()[0],
                "series": series,
                "countries": _rows(con, "SELECT country, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY country ORDER BY 3 DESC, 2 DESC LIMIT 30", since),
                "pages": [[p[0], p[1], p[2], labels.get(p[0], "")] for p in pages],
                "referrers": _rows(con, "SELECT ref, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND ref!='' GROUP BY ref ORDER BY 3 DESC, 2 DESC LIMIT 15", since),
                "devices": _rows(con, "SELECT device, COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY device ORDER BY 2 DESC", since),
                "langs": _rows(con, "SELECT lang, COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY lang ORDER BY 2 DESC", since),
                "hours": _rows(con, "SELECT CAST(strftime('%H', ts, 'unixepoch', '+1 hours') AS INTEGER) h, COUNT(*) FROM hits WHERE day>=? GROUP BY h ORDER BY h", since),
                "direct": con.execute("SELECT COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND ref=''", (since,)).fetchone()[0],
                "people": people,
                "clubs": _clubs(con, since),
                "followers": con.execute("SELECT COUNT(*) FROM follows").fetchone()[0],
                "country_known": con.execute("SELECT COUNT(*) FROM hits WHERE day>=? AND country!=''", (since,)).fetchone()[0] > 0,
                "cloudflare_setting": auth.TRUST_CLOUDFLARE,
            }
        finally:
            con.close()
