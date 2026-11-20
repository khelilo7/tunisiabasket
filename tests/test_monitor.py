"""Server tab: machine/app health samples (fake /proc), hourly roll-up and retention, warnings, the anonymous app-open ping
(hash only, no address, one row per install per day, bad input refused), app/push/vote counts, and the report is admin-only."""
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
PROC = Path(tempfile.mkdtemp())
os.environ["HEALTH_PROC"] = str(PROC)
os.environ["PUSH"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import health  # noqa: E402
import monitor  # noqa: E402
import mvp  # noqa: E402
import notify  # noqa: E402
import traffic  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
ADMIN = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}


def check(cond, msg):
    if not cond:
        fails.append(msg)


def fake_proc(busy, idle, avail_kb=1_000_000, total_kb=4_000_000, swap_free_kb=1_000_000):
    (PROC / "self" / "fd").mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (PROC / "self" / "fd" / str(i)).write_text("")
    (PROC / "stat").write_text(f"cpu  {busy} 0 0 {idle} 0 0 0 0 0 0\ncpu0 1 2 3 4\n")
    (PROC / "meminfo").write_text(f"MemTotal:       {total_kb} kB\nMemFree:          100000 kB\nMemAvailable:   {avail_kb} kB\nSwapTotal:      1000000 kB\nSwapFree:       {swap_free_kb} kB\n")
    (PROC / "uptime").write_text("98765.43 12345.00\n")
    (PROC / "self" / "status").write_text("Name:\tgunicorn\nVmRSS:\t  204800 kB\nThreads:\t9\n")


c = app.app.test_client()

# ---------------------------------------------------------------- machine samples
fake_proc(1000, 9000)
health.read_now()                                         # first counters
fake_proc(1300, 9700)                                     # +300 busy, +700 idle -> 30 %
for _ in range(4):
    c.get("/api/overview")
c.get("/api/no-such-thing")
t0 = (int(time.time()) // 3600 - 2) * 3600               # two hours ago, on the hour
s = health.sample(now=t0 + 30)
check(s["cpu"] == 30.0, f"machine CPU % from /proc/stat deltas: {s['cpu']}")
check(s["mem_total"] == 4_000_000 * 1024 and s["mem_used"] == 3_000_000 * 1024, f"memory used = total - available: {s['mem_used']}")
check(s["swap_used"] == 0 and s["uptime"] == 98765 and s["rss"] == 204800 * 1024 and s["fds"] == 3, f"swap, uptime, app memory, open files: {s}")
check(s["disk_total"] and s["disk_used"] is not None and s["load5"] is not None, "disk and load are read")
check(s["req"] == 5 and s["r4xx"] == 1 and s["r5xx"] == 0 and s["p95"] is not None and s["p50"] is not None, f"requests counted by the after_request hook: {s}")
check(health.sample(now=t0 + 90)["req"] == 0, "the request counters start again after each sample")
health.count(503, 0.2)
health.sample(now=t0 + 3600 + 30)                         # next hour: the first hour is rolled up
con = sqlite3.connect(health.DB_FILE)
hours = con.execute("SELECT ts, req, r4xx, cpu FROM hours").fetchall()
check(len(hours) == 1 and hours[0][0] == t0 and hours[0][1] == 5 and hours[0][2] == 1, f"finished hours are rolled up, requests added up: {hours}")
con.execute("INSERT INTO minutes(ts, cpu) VALUES (?, 1)", (t0 - 20 * 86400,))
con.execute("INSERT INTO hours(ts, cpu) VALUES (?, 1)", (t0 - 500 * 86400,))
con.commit()
health.sample(now=t0 + 3600 + 90)
check(con.execute("SELECT COUNT(*) FROM minutes WHERE ts < ?", (t0 - 15 * 86400,)).fetchone()[0] == 0, "minutes older than 14 days are deleted")
check(con.execute("SELECT COUNT(*) FROM hours WHERE ts < ?", (t0 - 450 * 86400,)).fetchone()[0] == 0, "hours older than 400 days are deleted")
check(oct(os.stat(health.DB_FILE).st_mode & 0o777) == "0o600", "health.db is private")
con.close()

ser = health.series("24h", now=t0 + 3600 + 120)
check(ser["step"] == 300 and len(ser["points"]) == 2 and ser["points"][0]["req"] == 2.5, f"24 h chart: 5-minute points, requests per minute (5 then 0): {ser['points'][:2]}")
check(health.series("30d", now=t0 + 3600 + 120)["points"][0]["req"] == round(5 / 60, 2), "hourly rows: the hour's requests become a per-minute rate")
check(health.series("nonsense")["range"] == "24h", "unknown range falls back to 24 h")
check(health.series("1y", now=t0 + 3600 + 120)["points"][0]["ts"] % 86400 == 0, "1-year chart: one point per day")

# ---------------------------------------------------------------- warnings
st = {"at": time.time(), "cpus": 2, "current": {"mem_used": 96, "mem_total": 100, "disk_used": 86, "disk_total": 100, "swap_used": 0, "swap_total": 10,
                                               "load5": 7, "rss": 10},
      "day": {"errors_5xx": 0, "requests": 100, "missing_minutes": 0}}
w = {x["text"].split(" ")[0]: x["level"] for x in health.warnings(st)}
check(w.get("Memory") == "bad" and w.get("Disk") == "warn" and w.get("Load") == "bad", f"thresholds: {w}")
st["at"] = time.time() - 600
check(any(x["level"] == "bad" and "sampler" in x["text"] for x in health.warnings(st)), "an old last sample is flagged")
calm = {"at": time.time(), "cpus": 4, "current": {"mem_used": 10, "mem_total": 100, "disk_used": 10, "disk_total": 100, "load5": 0.2, "rss": 5},
        "day": {"errors_5xx": 2, "requests": 50000, "missing_minutes": 1}}
check(health.warnings(calm) == [], f"a calm server has no warning: {health.warnings(calm)}")

# a Mac (no /proc): no crash, the machine numbers are just missing
os.environ["HEALTH_PROC"] = str(PROC / "missing")
s = health.read_now()
check(s["mem_total"] is None and s["cpu"] is None and s["uptime"] is None and s["disk_total"], "without /proc the sample still works")
os.environ["HEALTH_PROC"] = str(PROC)

# ---------------------------------------------------------------- the app-open ping
PHONE = {"User-Agent": "okhttp/4.12.0"}
VID = "0123456789abcdef0123456789abcdef"


def ping(vid=VID, platform="android", version="1.0.0", ip="203.0.113.5", ua=PHONE):
    return c.post("/api/app/open", json={"vid": vid, "platform": platform, "version": version}, headers=ua, environ_overrides={"REMOTE_ADDR": ip})


r = ping()
check(r.status_code == 204 and r.headers.get("Access-Control-Allow-Origin") == "*" and "POST" in r.headers.get("Access-Control-Allow-Methods", ""), "ping answers 204 and allows the app's POST")
ping(version="1.0.1")                                      # same install, same day: still one row (latest version kept)
ping(vid="f" * 32, platform="ios", version="1.0.0", ip="198.51.100.7", ua={"User-Agent": "TunisiaBasket/1 CFNetwork/1490 Darwin/23.0.0"})
for bad in ({"vid": "nothex!" * 5}, {"vid": "abc"}, {"platform": "windows"}, {"ua": {"User-Agent": "curl/8.0"}}):
    ping(**{"vid": "e" * 32, **bad})
ping(vid="d" * 32, version="<script>")                    # odd version: kept as unknown, not stored as given
con = sqlite3.connect(traffic.DB_FILE)
rows = con.execute("SELECT day, uid, platform, version FROM app_days ORDER BY platform, version").fetchall()
dump = json.dumps(rows) + json.dumps([list(r) for r in con.execute("SELECT * FROM hits")])
con.close()
check(len(rows) == 3, f"one row per install per day, bad input refused: {rows}")
check(VID not in dump and "203.0.113.5" not in dump and "okhttp" not in dump and "<script>" not in dump, "only a hash: no raw id, no address, no browser string")
check(sorted(r[2] for r in rows) == ["android", "android", "ios"] and "1.0.1" in [r[3] for r in rows] and "" in [r[3] for r in rows], f"platform and version kept: {rows}")
check(all(len(r[1]) == 16 for r in rows), "uid is a 16-character hash")
c.post("/admin/api/login", json={"token": "TEST-TOKEN-0000-1111"}, environ_overrides={"REMOTE_ADDR": "192.0.2.50"})
ping(vid="c" * 32, ip="192.0.2.50")
c.post("/admin/api/logout")
check(traffic.app_summary()["today"] == 3, "the admin's own app is not counted")

# a network can only add so many new installs a day (a script inventing ids), existing ones still refresh
traffic.MAX_APP_IDS_PER_NETWORK_DAY = 2
ping(vid="1" * 32, ip="203.0.113.99")
ping(vid="2" * 32, ip="203.0.113.99")
ping(vid="3" * 32, ip="203.0.113.99")
check(traffic.app_summary()["today"] == 5, f"per-network cap on new installs: {traffic.app_summary()['today']}")

# yesterday's and 40-days-ago rows: DAU / WAU / MAU / installs / new
con = sqlite3.connect(traffic.DB_FILE)
con.execute("INSERT INTO app_days VALUES (?, 'olduser00000000', 'android', '0.9.0', ?)", (traffic._day(1), int(time.time()) - 86400))
con.execute("INSERT INTO app_days VALUES (?, 'olduser00000000', 'android', '0.9.0', ?)", (traffic._day(40), int(time.time()) - 40 * 86400))
con.execute("INSERT INTO app_days VALUES (?, 'gone00000000000', 'android', '0.8.0', ?)", (traffic._day(399), int(time.time()) - 401 * 86400))
con.commit()
con.close()
traffic._ready = False                                    # retention runs when the database is opened by a new process
a = traffic.app_summary(30)
check(a["today"] == 5 and a["wau"] == 6 and a["mau"] == 6 and a["installs"] == 6, f"DAU 5, WAU 6, MAU 6, installs 6 (the 401-day-old row is gone): {a}")
check(a["series"][-1]["new"] == 5 and a["series"][-2]["active"] == 1 and a["series"][-2]["new"] == 0, "new installs counted on their first day only")
check(dict(a["platforms"]) == {"android": 5, "ios": 1}, f"platforms by install: {a['platforms']}")

# ---------------------------------------------------------------- push sign-ups and votes
now = time.time()
notify._write(notify.FILE, {
    "ExponentPushToken[aaaaaaaaaaaa]": {"level": "all", "team": "", "lang": "fr", "results": True, "news": False, "votes": True, "ts": int(now)},
    "ExponentPushToken[bbbbbbbbbbbb]": {"level": "team", "team": "ESR", "lang": "en", "results": True, "news": True, "votes": True, "ts": int(now - 10 * 86400)},
    "ExponentPushToken[cccccccccccc]": {"level": "team", "team": "ESR", "lang": "fr", "results": False, "news": True, "votes": True, "ts": int(now - 60 * 86400)},
})
p = monitor.push_summary(now)
check(p["total"] == 3 and p["seen_7d"] == 1 and p["seen_30d"] == 2 and p["levels"] == {"all": 1, "team": 2}, f"push counts: {p}")
check(p["topics"] == {"results": 2, "news": 2, "votes": 3} and [list(t) for t in p["teams"]] == [["ESR", 2]], f"push topics and clubs: {p}")
with mvp._lock:
    con = mvp._db()
    con.execute("INSERT INTO round_votes VALUES (3, 'v1', 'n1', 'ca-24', ?)", (int(now),))
    con.execute("INSERT INTO round_votes VALUES (3, 'v2', 'n1', 'ca-24', ?)", (int(now - 3 * 86400),))
    con.execute("INSERT INTO picks VALUES ('g1', 'v1', 'n1', 'h', ?)", (int(now),))
    con.execute("INSERT INTO votes VALUES (1, 'v9', 'n9', 'ca-24', ?)", (int(now - 100 * 86400),))
    con.commit()
    con.close()
v = monitor.votes_summary(30)["kinds"]
check(v["round"] == {"total": 2, "today": 1, "last_7d": 2, "period": 2}, f"round votes: {v['round']}")
check(v["predictions"]["today"] == 1 and v["mvp"]["total"] == 1 and v["mvp"]["period"] == 0, f"predictions and old MVP vote: {v}")

# ---------------------------------------------------------------- the report: admin only
check(c.get("/admin/api/monitor").status_code == 401, "the Server tab's data needs the admin login")
check(c.get("/admin/api/monitor", headers={"X-Admin-Token": "WRONG-TOKEN-0000-0000"}).status_code == 401, "a wrong token is refused")
r = c.get("/admin/api/monitor?range=7d&days=30", headers=ADMIN)
m = r.get_json()
check(r.status_code == 200 and set(m) == {"health", "chart", "web", "app", "push", "votes"}, f"report sections: {list(m or {})}")
check(m["chart"]["range"] == "7d" and m["app"]["today"] == 5 and m["push"]["total"] == 3 and "warnings" in m["health"], "report content")
check(c.get("/admin/api/monitor?days=oops&range=zzz", headers=ADMIN).status_code == 200, "odd parameters fall back to the defaults")
check("/api/app/open" in app.CORS_POST, "the app may POST the ping from its web preview")

print("monitor:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
