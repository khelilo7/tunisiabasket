"""Send the photos of this computer (data/photos) to a running site through its admin panel, so players can see and approve them.

    python tools/upload_photos.py --site https://tunisiabasket.com            asks for the admin token (typed, never shown or stored)
    python tools/upload_photos.py --site https://tunisiabasket.com --dry-run  only lists what would be sent
    python tools/upload_photos.py --site https://tunisiabasket.com --remove   takes every uploaded photo off the site again (a player said no)

Why not through git: the repository is public, so a photo committed there stays visible in its history even after it is deleted. Uploaded through
the admin panel, a photo lives only in the site's data folder (never in git, kept across deployments, included in the backups) and one click or one
`--remove` takes it down. Only the photos in data/photos are touched; nothing else on the site changes.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from _site import login  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="e.g. https://tunisiabasket.com or http://127.0.0.1:5055")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    site = a.site.rstrip("/")
    try:
        index = json.loads((config.DATA_DIR / "player_photos.json").read_text())
    except (OSError, ValueError):
        index = {}
    mine = sorted(pid for pid, url in index.items() if url.startswith("/photo/") and (config.DATA_DIR / "photos" / f"{pid}.jpg").exists())
    if not mine and not a.remove:
        sys.exit("No photos in data/photos to send. Import some first: python tools/import_photos.py")
    if a.dry_run:
        print(f"{len(mine)} photo(s) would be sent to {site}: {', '.join(mine)}")
        return
    s = login(site)
    if a.remove:
        live = s.get(f"{site}/admin/api/roster", timeout=30).json()["players"]
        gone = [p["id"] for p in live if (p.get("photo") or "").startswith("/photo/")]
        for pid in gone:
            s.post(f"{site}/admin/api/photo/delete", json={"id": pid}, timeout=30).raise_for_status()
        print(f"Removed {len(gone)} uploaded photo(s) from {site}.")
        return
    ok, bad = 0, []
    for pid in mine:
        with open(config.DATA_DIR / "photos" / f"{pid}.jpg", "rb") as f:
            r = s.post(f"{site}/admin/api/photo", data={"id": pid}, files={"image": (f"{pid}.jpg", f, "image/jpeg")}, timeout=60)
        if r.status_code == 200:
            ok += 1
        else:
            bad.append(f"{pid} ({r.status_code}: {r.json().get('error', '')})")
    print(f"Sent {ok} of {len(mine)} photo(s) to {site}." + (f" Not accepted: {'; '.join(bad)}" if bad else ""))


if __name__ == "__main__":
    main()
