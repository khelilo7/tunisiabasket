"""Backups: consistent, verified, restorable, pruned, never touching the live data."""
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
work = Path(tempfile.mkdtemp())
data, out = work / "data", work / "out"
(data / "games").mkdir(parents=True)
(data / "games" / "g1.json").write_text('{"id": "g1"}')
(data / "mvp.json").write_text('{"1": {"winner": null}}')
(data / "admin.log").write_text("x\n")
con = sqlite3.connect(data / "votes.db")
con.execute("CREATE TABLE votes(phase INTEGER, voter TEXT, net TEXT, pid TEXT, ts INTEGER, PRIMARY KEY(phase, voter))")
con.executemany("INSERT INTO votes VALUES (1, ?, 'n', 'ca-24', 1)", [(f"v{i}",) for i in range(250)])
con.commit()
con.close()
t = sqlite3.connect(data / "traffic.db")
t.execute("CREATE TABLE hits(ts INTEGER, day TEXT, visitor TEXT)")
t.executemany("INSERT INTO hits VALUES (1, '2026-11-01', ?)", [(f"h{i}",) for i in range(40)])
t.commit()
t.close()
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def run(*args):
    return subprocess.run([sys.executable, str(root / "tools" / "backup_data.py"), "--data", str(data), "--out", str(out), *args], capture_output=True, text=True,
                          env={**os.environ, "DATA_DIR": str(data)})


before = (data / "votes.db").read_bytes()
r = run()
check(r.returncode == 0 and "backup ok" in r.stdout, f"full backup runs: {r.stdout} {r.stderr}")
check("votes=250" in r.stdout and "hits=40" in r.stdout, f"row counts are reported: {r.stdout}")
check((data / "votes.db").read_bytes() == before, "the live data is untouched")
full = sorted(out.glob("data-*.tgz"))
check(len(full) == 1 and oct(full[0].stat().st_mode & 0o777) == "0o600" and oct(out.stat().st_mode & 0o777) == "0o700", "private files and folder")
with tarfile.open(full[0]) as tf:
    names = tf.getnames()
check("data/votes.db" in names and "data/traffic.db" in names and "data/games/g1.json" in names and "data/mvp.json" in names, f"everything is in the archive: {names}")

r = run("--small")
small = sorted(out.glob("small-*.tgz"))
check(r.returncode == 0 and len(small) == 1, "small backup runs")
with tarfile.open(small[0]) as tf:
    sn = tf.getnames()
check("data/votes.db" in sn and "data/traffic.db" in sn and "data/mvp.json" in sn and "data/games/g1.json" not in sn, f"small backup holds votes, visits and settings only: {sn}")

# restore goes next to the data, never over it, and the votes are all there
r = run("--restore", str(full[0]))
restored = sorted(work.glob("data-restored-*/data/votes.db"))
check(r.returncode == 0 and len(restored) == 1, f"restore: {r.stdout} {r.stderr}")
if restored:
    c = sqlite3.connect(restored[0])
    check(c.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 250 and c.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "restored votes are complete and intact")
    c.close()

# a vote arriving during the backup cannot corrupt it: back up while another connection holds a write
w = sqlite3.connect(data / "votes.db")
w.execute("BEGIN IMMEDIATE")
w.execute("INSERT INTO votes VALUES (1, 'late', 'n', 'ca-24', 2)")
r = run()
w.commit()
w.close()
check(r.returncode == 0, f"a backup during a pending write still verifies: {r.stdout} {r.stderr}")

# pruning: small after 3 days; full after 14 days except one per month
old_small = out / "small-20200101-0000.tgz"
old_small.write_bytes(b"x"); os.utime(old_small, (time.time() - 5 * 86400,) * 2)
a, b, c3 = out / "data-20250101-000000.tgz", out / "data-20250115-000000.tgz", out / "data-20261001-000000.tgz"
for f, days in ((a, 300), (b, 290), (c3, 30)):
    f.write_bytes(b"x"); os.utime(f, (time.time() - days * 86400,) * 2)
run()
check(not old_small.exists(), "old small backups are pruned")
check(a.exists() and not b.exists(), "two old backups from the same month: the oldest is kept, the other pruned")
check(c3.exists(), "the first backup of a recent older month is kept")
check(len(list(out.glob("data-2026110*.tgz"))) >= 1 or len(list(out.glob("data-*.tgz"))) >= 3, "recent full backups are kept")

# a corrupt live database is reported, not silently backed up
(data / "votes.db").write_bytes(b"not a database" * 100)
r = run()
check(r.returncode != 0, "a broken database makes the backup fail loudly")

print("backup:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
