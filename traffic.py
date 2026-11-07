"""Visitor statistics without cookies and without storing anything personal.

What is stored per page view: day, time, page, country (from Cloudflare's CF-IPCountry header), referring site,
device type, language, and two codes. The visitor code is a hash of IP + browser + the day + a secret key, so it
lets us count distinct visitors per day but cannot be turned back into an address, and the same person gets a different
code tomorrow. The second code is a hash of a random id the browser keeps (never derived from the address): it is what tells a
returning visitor from a new one, and it is one device/browser, not one human. IP addresses are never written to disk. Crawlers are ignored, and so is the admin.
"""
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
_lock = threading.Lock()
_ready = False


def _db():
    global _ready
    con = sqlite3.connect(DB_FILE, timeout=10)
    if not _ready:
        con.execute("""CREATE TABLE IF NOT EXISTS hits(ts INTEGER, day TEXT, page TEXT, path TEXT, country TEXT, ref TEXT, device TEXT, lang TEXT, visitor TEXT)""")
        if "rid" not in [r[1] for r in con.execute("PRAGMA table_info(hits)")]:
            con.execute("ALTER TABLE hits ADD COLUMN rid TEXT DEFAULT ''")       # returning-visitor code (added later)
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
    day = time.strftime("%Y-%m-%d")
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


def _rows(con, sql, *args):
    return [list(r) for r in con.execute(sql, args)]


def summary(days: int = 30) -> dict:
    days = max(1, min(int(days), 365))
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - (days - 1) * 86400))
    with _lock:
        con = _db()
        try:
            today = time.strftime("%Y-%m-%d")
            per_day = {d: [v, u] for d, v, u in con.execute(
                "SELECT day, COUNT(*), COUNT(DISTINCT visitor) FROM hits WHERE day>=? GROUP BY day", (since,))}
            series = []
            for i in range(days - 1, -1, -1):
                d = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
                series.append({"day": d, "views": per_day.get(d, [0, 0])[0], "visitors": per_day.get(d, [0, 0])[1]})
            tot = con.execute("SELECT COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=?", (since,)).fetchone()
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
            return {
                "days": days, "since": since,
                "views": tot[0], "visitors": tot[1],            # visitors = distinct people per day, added up over the period
                "today": {"views": per_day.get(today, [0, 0])[0], "visitors": per_day.get(today, [0, 0])[1]},
                "online": con.execute("SELECT COUNT(DISTINCT visitor) FROM hits WHERE ts>?", (time.time() - 300,)).fetchone()[0],
                "series": series,
                "countries": _rows(con, "SELECT country, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY country ORDER BY 3 DESC, 2 DESC LIMIT 30", since),
                "pages": _rows(con, "SELECT path, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY path ORDER BY 2 DESC LIMIT 25", since),
                "referrers": _rows(con, "SELECT ref, COUNT(*), COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND ref!='' GROUP BY ref ORDER BY 3 DESC, 2 DESC LIMIT 15", since),
                "devices": _rows(con, "SELECT device, COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY device ORDER BY 2 DESC", since),
                "langs": _rows(con, "SELECT lang, COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? GROUP BY lang ORDER BY 2 DESC", since),
                "hours": _rows(con, "SELECT CAST(strftime('%H', ts, 'unixepoch', 'localtime') AS INTEGER) h, COUNT(*) FROM hits WHERE day>=? GROUP BY h ORDER BY h", since),
                "direct": con.execute("SELECT COUNT(DISTINCT day||visitor) FROM hits WHERE day>=? AND ref=''", (since,)).fetchone()[0],
                "people": people,
                "country_known": con.execute("SELECT COUNT(*) FROM hits WHERE day>=? AND country!=''", (since,)).fetchone()[0] > 0,
                "cloudflare_setting": auth.TRUST_CLOUDFLARE,
            }
        finally:
            con.close()
