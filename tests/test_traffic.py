"""Traffic statistics: counts real visitors, ignores crawlers/admin/odd paths, stores nothing personal, admin-only report."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
os.environ["TRUST_CLOUDFLARE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import config  # noqa: E402

auth.time.sleep = lambda s: None
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
DESK = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def hit(path, ua=PHONE, ip="203.0.113.5", country="TN", ref=""):
    return c.post("/api/hit", json={"path": path, "ref": ref, "lang": "fr"},
                  headers={"User-Agent": ua, "CF-IPCountry": country}, environ_overrides={"REMOTE_ADDR": ip})


check(hit("/", ref="https://www.google.com/search?q=basket").status_code == 204, "beacon answers 204")
hit("/joueur/ca-24-omar-abada")
hit("/", ua=DESK, ip="198.51.100.9", country="FR", ref="https://facebook.com/x")
hit("/", ua="Googlebot/2.1 (+http://www.google.com/bot.html)", ip="66.249.66.1")      # crawler: ignored
hit("/admin", ip="203.0.113.77")                                                       # not a site page: ignored
hit("/nonsense/page", ip="203.0.113.78")                                               # unknown page: ignored

# the report is for the admin only
check(c.get("/admin/api/traffic").status_code == 401, "traffic report must need the admin login")
r = c.get("/admin/api/traffic?days=7", headers={"X-Admin-Token": "TEST-TOKEN-0000-1111"})
check(r.status_code == 200, "admin can read the report")
t = r.get_json()
check(t["views"] == 3, f"3 real page views expected, got {t['views']}")
check(t["visitors"] == 2, f"2 distinct visitors expected, got {t['visitors']}")
check({x[0] for x in t["countries"]} == {"TN", "FR"}, "countries from Cloudflare header")
check({x[0] for x in t["referrers"]} == {"google.com", "facebook.com"}, f"referrers by site name only: {t['referrers']}")
check(dict(t["devices"]) == {"mobile": 1, "desktop": 1}, f"devices {t['devices']}")
check(t["today"]["views"] == 3 and len(t["series"]) == 7, "daily series")

# an admin's own browsing is not counted
c.post("/admin/api/login", json={"token": "TEST-TOKEN-0000-1111"}, environ_overrides={"REMOTE_ADDR": "192.0.2.50"})
hit("/", ip="192.0.2.50")
check(c.get("/admin/api/traffic").get_json()["views"] == 3, "admin visits must not be counted")

# nothing personal on disk
con = sqlite3.connect(config.DATA_DIR / "traffic.db")
dump = " ".join(str(v) for row in con.execute("SELECT * FROM hits") for v in row)
con.close()
check("203.0.113.5" not in dump and "iPhone" not in dump and "Mozilla" not in dump, "no IP address or browser string may be stored")
check(oct((config.DATA_DIR / "traffic.db").stat().st_mode & 0o777) == "0o600", "traffic.db must be private (600)")

# bad input never breaks the site
check(c.post("/api/hit", data="not json", headers={"User-Agent": PHONE}).status_code == 204, "garbage body is harmless")

print("traffic:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
