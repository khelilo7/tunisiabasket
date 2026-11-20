"""Health of the server and of the app, for the admin's Server tab. Nothing about visitors: machine numbers only.

* A thread inside the app (start(), one per process; the site runs ONE gunicorn worker) takes a sample every minute: CPU, memory, swap, disk,
  load, machine uptime, the app process (memory, threads, open files, its own CPU) and the requests it answered during that minute (count, 4xx,
  5xx, median and 95th-percentile response time, counted by an after_request hook in app.py: count()).
* Samples go to data/health.db: one row per minute kept 14 days, one row per hour (averages; requests and errors added up; p95 = the worst minute)
  kept 400 days. A gap in the minutes means the app was not running (a restart, a deploy, a crash).
* Linux numbers come from /proc (HEALTH_PROC moves it, for the tests); on a Mac, where there is no /proc, the machine CPU/memory/uptime are
  simply missing and the rest still works. Costs a few kilobytes of memory and ~5 MB of disk a year.
"""
import bisect
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import config

DB_FILE = config.DATA_DIR / "health.db"
EVERY = 60
KEEP_MINUTES_DAYS = 14
KEEP_HOURS_DAYS = 400
MAX_TIMINGS = 5000                     # response times kept per minute for the percentiles (a sorted sample; plenty for this site)
COLS = ("cpu", "app_cpu", "mem_used", "mem_total", "swap_used", "swap_total", "disk_used", "disk_total", "load1", "load5", "load15",
        "uptime", "rss", "threads", "fds", "req", "r4xx", "r5xx", "p50", "p95")
SUMMED = ("req", "r4xx", "r5xx")
STARTED = time.time()                  # when this app process started
_lock = threading.Lock()
_db_lock = threading.Lock()
_ready = False
_started = False
_req = {"n": 0, "4xx": 0, "5xx": 0, "times": []}
_prev = {}                             # the previous CPU counters, for the CPU % of the last minute


def _proc() -> Path:
    return Path(os.environ.get("HEALTH_PROC", "/proc"))


# ---------------------------------------------------------------- requests (called for every answer)
def count(status: int, seconds: float):
    with _lock:
        _req["n"] += 1
        if 400 <= status < 500:
            _req["4xx"] += 1
        elif status >= 500:
            _req["5xx"] += 1
        t = _req["times"]
        if len(t) < MAX_TIMINGS:
            bisect.insort(t, seconds)


def _take_requests():
    with _lock:
        n, e4, e5, t = _req["n"], _req["4xx"], _req["5xx"], _req["times"]
        _req.update(n=0, **{"4xx": 0, "5xx": 0}, times=[])
    pct = (lambda q: round(t[min(len(t) - 1, int(q * len(t)))] * 1000, 1)) if t else (lambda q: None)
    return {"req": n, "r4xx": e4, "r5xx": e5, "p50": pct(0.5), "p95": pct(0.95)}


# ---------------------------------------------------------------- machine
def _read(name):
    try:
        return (_proc() / name).read_text()
    except OSError:
        return None


def _meminfo():
    txt = _read("meminfo")
    if not txt:
        return {}
    kb = {}
    for line in txt.splitlines():
        k, _, v = line.partition(":")
        try:
            kb[k] = int(v.split()[0]) * 1024
        except (ValueError, IndexError):
            pass
    if "MemTotal" not in kb:
        return {}
    avail = kb.get("MemAvailable", kb.get("MemFree", 0) + kb.get("Cached", 0))
    return {"mem_total": kb["MemTotal"], "mem_used": kb["MemTotal"] - avail,
            "swap_total": kb.get("SwapTotal", 0), "swap_used": kb.get("SwapTotal", 0) - kb.get("SwapFree", 0)}


def _cpu_counters():
    txt = _read("stat")
    if not txt or not txt.startswith("cpu "):
        return None
    v = [int(x) for x in txt.splitlines()[0].split()[1:]]
    idle = v[3] + (v[4] if len(v) > 4 else 0)          # idle + iowait
    return sum(v[:8]), idle                              # user..steal (guest time is already inside user)


def _process():
    out = {"threads": threading.active_count(), "rss": None, "fds": None}
    status = _read("self/status")
    if status:
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                out["rss"] = int(line.split()[1]) * 1024
    try:
        out["fds"] = len(os.listdir(_proc() / "self" / "fd"))
    except OSError:
        pass
    return out


def read_now() -> dict:
    """One reading of everything (CPU % is over the time since the previous reading)."""
    now = time.time()
    s = dict.fromkeys(COLS)
    s.update(_meminfo())
    try:
        du = shutil.disk_usage(config.DATA_DIR)
        s["disk_total"], s["disk_used"] = du.total, du.total - du.free
    except OSError:
        pass
    try:
        s["load1"], s["load5"], s["load15"] = (round(x, 2) for x in os.getloadavg())
    except OSError:
        pass
    up = _read("uptime")
    if up:
        s["uptime"] = int(float(up.split()[0]))
    s.update(_process())
    cpu, t = _cpu_counters(), os.times()
    app_cpu = t.user + t.system
    with _lock:
        prev = dict(_prev)
        _prev.update(cpu=cpu, app_cpu=app_cpu, at=now)
    if cpu and prev.get("cpu") and cpu[0] > prev["cpu"][0]:
        total, idle = cpu[0] - prev["cpu"][0], cpu[1] - prev["cpu"][1]
        s["cpu"] = round(100 * (total - idle) / total, 1)
    if prev.get("at") and now > prev["at"]:
        s["app_cpu"] = round(100 * (app_cpu - prev["app_cpu"]) / (now - prev["at"]) / (os.cpu_count() or 1), 1)
    return s


# ---------------------------------------------------------------- storage
def _db():
    global _ready
    con = sqlite3.connect(DB_FILE, timeout=10)
    if not _ready:
        cols = ", ".join(f"{c} NUMERIC" for c in COLS)
        for table in ("minutes", "hours"):
            con.execute(f"CREATE TABLE IF NOT EXISTS {table}(ts INTEGER PRIMARY KEY, {cols})")
        con.commit()
        try:
            os.chmod(DB_FILE, 0o600)
        except OSError:
            pass
        _ready = True
    return con


def _rollup(con, now):
    """Turn the finished hours into hourly rows, and forget what is past its keeping time."""
    last = con.execute("SELECT MAX(ts) FROM hours").fetchone()[0]
    start = (last + 3600) if last is not None else 0
    end = int(now) // 3600 * 3600                        # the current hour is not finished yet
    agg = ", ".join(f"SUM({c})" if c in SUMMED else f"MAX({c})" if c == "p95" else f"AVG({c})" for c in COLS)
    con.execute(f"INSERT OR REPLACE INTO hours(ts, {', '.join(COLS)}) SELECT ts / 3600 * 3600 h, {agg} FROM minutes WHERE ts >= ? AND ts < ? GROUP BY h",
                (start, end))
    con.execute("DELETE FROM minutes WHERE ts < ?", (now - KEEP_MINUTES_DAYS * 86400,))
    con.execute("DELETE FROM hours WHERE ts < ?", (now - KEEP_HOURS_DAYS * 86400,))


def sample(now=None) -> dict:
    """Take and store one sample (the requests counted since the previous one go with it)."""
    now = now or time.time()
    s = {**read_now(), **_take_requests()}
    with _db_lock:
        con = _db()
        try:
            con.execute(f"INSERT OR REPLACE INTO minutes(ts, {', '.join(COLS)}) VALUES (?{', ?' * len(COLS)})", (int(now) // 60 * 60, *(s[c] for c in COLS)))
            _rollup(con, now)
            con.commit()
        finally:
            con.close()
    return s


def _loop():
    read_now()                                           # first CPU counters, so the first stored minute already has a CPU %
    while True:
        time.sleep(EVERY - time.time() % EVERY + 1)      # just after each full minute
        try:
            sample()
        except Exception:                                # monitoring must never take the site down
            pass


def start():
    """Start the sampler once (HEALTH=0 turns it off)."""
    global _started
    if _started or os.environ.get("HEALTH", "1") != "1":
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="health").start()


# ---------------------------------------------------------------- report
RANGES = {  # name: (table, seconds back, seconds per point on the chart)
    "1h": ("minutes", 3600, 60),
    "24h": ("minutes", 86400, 300),
    "7d": ("minutes", 7 * 86400, 1800),
    "30d": ("hours", 30 * 86400, 6 * 3600),
    "1y": ("hours", 365 * 86400, 86400),
}


def series(rng: str = "24h", now=None) -> dict:
    """Points for the charts. Requests and errors are per minute (averaged, so a point still filling up is not a dip)."""
    table, back, step = RANGES.get(rng, RANGES["24h"])
    now = now or time.time()
    per_min = "" if table == "minutes" else " / 60.0"     # hourly rows hold the hour's total
    agg = ", ".join(f"AVG({c}){per_min}" if c in SUMMED else f"MAX({c})" if c == "p95" else f"AVG({c})" for c in COLS)
    with _db_lock:
        con = _db()
        try:
            rows = con.execute(f"SELECT ts / {step} * {step} b, {agg} FROM {table} WHERE ts >= ? GROUP BY b ORDER BY b", (now - back,)).fetchall()
        finally:
            con.close()
    points = [{"ts": r[0], **{c: (round(v, 2) if isinstance(v, float) else v) for c, v in zip(COLS, r[1:])}} for r in rows]
    return {"range": rng if rng in RANGES else "24h", "step": step, "since": int(now - back), "points": points}


def status(now=None) -> dict:
    """The latest sample, the last 24 hours in short, and warnings (level 'warn' or 'bad')."""
    now = now or time.time()
    with _db_lock:
        con = _db()
        try:
            last = con.execute(f"SELECT ts, {', '.join(COLS)} FROM minutes ORDER BY ts DESC LIMIT 1").fetchone()
            day = con.execute("SELECT COUNT(*), MIN(ts), SUM(req), SUM(r5xx), SUM(r4xx), MAX(cpu), MAX(mem_used), MAX(p95) FROM minutes WHERE ts >= ?", (now - 86400,)).fetchone()
        finally:
            con.close()
    cur = dict(zip(COLS, last[1:])) if last else {}
    live = read_now() if not last else {}                # nothing stored yet (first minute after a start): show a live reading
    for k, v in live.items():
        if cur.get(k) is None:
            cur[k] = v
    n, first, req, e5, e4, cpu_max, mem_max, p95_max = day
    expected = int((now - max(first or now, now - 86400)) // 60)
    out = {
        "at": last[0] if last else None, "now": int(now), "current": cur, "cpus": os.cpu_count(),
        "app_uptime": int(now - STARTED), "pid": os.getpid(),
        "day": {"requests": req or 0, "errors_5xx": e5 or 0, "errors_4xx": e4 or 0, "cpu_max": cpu_max, "mem_max": mem_max, "p95_max": p95_max,
                "minutes": n, "missing_minutes": max(0, expected - n)},
    }
    out["warnings"] = warnings(out, now)
    return out


def warnings(st: dict, now=None) -> list:
    now = now or time.time()
    c, w = st["current"], []

    def add(level, text):
        w.append({"level": level, "text": text})

    def pct(a, b):
        return 100 * a / b if a is not None and b else None

    if st["at"] is None:
        add("warn", "No sample stored yet: the first one comes a minute after the app starts.")
    elif now - st["at"] > 3 * EVERY:
        add("bad", f"The last sample is {int((now - st['at']) // 60)} minutes old: the sampler stopped, or the app was restarted just now.")
    for name, used, total in (("Memory", c.get("mem_used"), c.get("mem_total")), ("Disk", c.get("disk_used"), c.get("disk_total"))):
        p = pct(used, total)
        if p is not None and p >= 95:
            add("bad", f"{name} is {p:.0f}% full.")
        elif p is not None and p >= 85:
            add("warn", f"{name} is {p:.0f}% full.")
    p = pct(c.get("swap_used"), c.get("swap_total"))
    if p is not None and p >= 50:
        add("warn", f"Swap is {p:.0f}% used: the machine is short of memory.")
    cpus = st.get("cpus") or 1
    if c.get("load5") is not None and c["load5"] >= 3 * cpus:
        add("bad", f"Load {c['load5']} (5 min) for {cpus} CPUs: the machine is overloaded.")
    elif c.get("load5") is not None and c["load5"] >= 1.5 * cpus:
        add("warn", f"Load {c['load5']} (5 min) for {cpus} CPUs: busy.")
    p = pct(c.get("rss"), c.get("mem_total"))
    if p is not None and p >= 40:
        add("warn", f"The app uses {p:.0f}% of the memory.")
    d = st["day"]
    if d["errors_5xx"] >= 5 and d["errors_5xx"] >= 0.01 * max(1, d["requests"]):
        add("bad" if d["errors_5xx"] >= 0.05 * max(1, d["requests"]) else "warn", f"{d['errors_5xx']} server errors (5xx) in the last 24 hours.")
    if d["missing_minutes"] >= 10:
        add("warn", f"{d['missing_minutes']} minutes without a sample in the last 24 hours (restarts, deploys or the app down).")
    return w
