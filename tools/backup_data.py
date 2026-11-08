"""Back up the live data safely: votes, visit statistics, games, official results, roster, admin settings.

    python tools/backup_data.py                 full backup     -> <out>/data-YYYYmmdd-HHMMSS.tgz   (kept 14 days + the first of each month for a year)
    python tools/backup_data.py --small         votes + visits  -> <out>/small-YYYYmmdd-HHMM.tgz    (the databases and settings only; kept 3 days)
    python tools/backup_data.py --restore FILE  unpack a backup into a new folder next to the data (never over the live data)

SQLite files are copied with SQLite's own backup call, so a vote that arrives while the copy runs cannot corrupt it. Every backup is
re-opened and checked (integrity check, row counts) before it counts; a backup that fails the check is deleted and the script exits with an error.
The tar keeps the layout the restore instructions in deploy/DEPLOY.md expect: one top-level folder called `data`.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

SMALL_FILES = ("votes.db", "traffic.db", "traffic.key", "mvp.json", "roster.json", "players_info.json", "positions.json", "calendar.json", "admin_token.json")
SKIP = {"admin.log.tmp"}


def snapshot(src: Path, dst: Path):
    """Consistent copy of the data folder (SQLite via its backup API, other files plainly)."""
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if p.is_dir() or p.name in SKIP or p.suffix == ".tmp" or p.name.endswith(("-journal", "-wal", "-shm")):
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".db":
            a, b = sqlite3.connect(f"file:{p}?mode=ro", uri=True), sqlite3.connect(out)
            try:
                a.backup(b)
            finally:
                b.close()
                a.close()
        else:
            shutil.copy2(p, out)


def verify(tar_path: Path, expect: dict) -> dict:
    """Open the archive, check every database and return {db name: {table: rows}}. Raises if anything is wrong."""
    seen = {}
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(tar_path) as tf:
        tf.extractall(tmp, filter="data")
        root = Path(tmp) / "data"
        for db in root.rglob("*.db"):
            con = sqlite3.connect(db)
            try:
                if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError(f"{db.name} failed the integrity check")
                tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                seen[db.name] = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
            finally:
                con.close()
    for name, tables in expect.items():
        for t, n in tables.items():
            if seen.get(name, {}).get(t, -1) < n:
                raise RuntimeError(f"{name}.{t}: the backup has fewer rows than the live database ({seen.get(name, {}).get(t)} < {n})")
    return seen


def live_counts(src: Path) -> dict:
    out = {}
    for db in src.rglob("*.db"):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            out[db.name] = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    return out


def prune(out: Path):
    """Small backups: 3 days. Full backups: everything from the last 14 days, then one per month (the oldest of the month) for a year."""
    now = time.time()
    for f in out.glob("small-*.tgz"):
        if now - f.stat().st_mtime > 3 * 86400:
            f.unlink()
    seen_months = set()
    for f in sorted(out.glob("data-*.tgz")):
        age = (now - f.stat().st_mtime) / 86400
        if age <= 14:
            continue
        month = time.strftime("%Y%m", time.localtime(f.stat().st_mtime))
        if age <= 365 and month not in seen_months:
            seen_months.add(month)
            continue
        f.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.environ.get("BACKUP_DIR") or str(config.DATA_DIR.parent / "backups"))
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--restore")
    ap.add_argument("--data", default=str(config.DATA_DIR))
    a = ap.parse_args()
    src, out = Path(a.data), Path(a.out)
    if a.restore:
        dest = src.parent / f"data-restored-{time.strftime('%Y%m%d-%H%M%S')}"
        dest.mkdir()
        with tarfile.open(a.restore) as tf:
            tf.extractall(dest, filter="data")
        print(f"Restored into {dest / 'data'} (the live data was not touched). Stop the app, move it into place, start the app.")
        return
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    stamp = time.strftime("%Y%m%d-%H%M") if a.small else time.strftime("%Y%m%d-%H%M%S")
    target = out / (f"small-{stamp}.tgz" if a.small else f"data-{stamp}.tgz")
    before = live_counts(src)
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "data"
        snap.mkdir()
        snapshot(src, snap)
        if a.small:                                                     # the databases and settings only
            for p in list(snap.rglob("*")):
                if p.is_file() and p.name not in SMALL_FILES:
                    p.unlink()
        with tarfile.open(target, "w:gz") as tf:
            tf.add(snap, arcname="data")
    os.chmod(target, 0o600)
    try:
        seen = verify(target, before)
    except Exception as e:
        target.unlink(missing_ok=True)
        sys.exit(f"BACKUP FAILED and was discarded: {e}")
    prune(out)
    rows = ", ".join(f"{db}: " + "/".join(f"{t}={n}" for t, n in t_.items()) for db, t_ in sorted(seen.items())) or "no databases yet"
    print(f"{time.strftime('%F %T')} backup ok -> {target} ({target.stat().st_size // 1024} KB; {rows})")


if __name__ == "__main__":
    main()
