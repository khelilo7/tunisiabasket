"""Shipped player photos: every file is listed, every listed file exists, each is a small square JPEG, and the ids are real players."""
import json
import sys
from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import stats  # noqa: E402

idx = {k: v for k, v in json.loads((root / "assets" / "player_photos.json").read_text()).items() if not k.startswith("_")}
files = {f.stem for f in (root / "static" / "img" / "players").glob("*.jpg")}
ids = {p["id"] for p in stats.build(keep_hidden=True)["players"]}
fails = []
if set(idx) != files:
    fails.append(f"listed vs files differ: {sorted(set(idx) ^ files)}")
for pid in files:
    f = root / "static" / "img" / "players" / f"{pid}.jpg"
    im = Image.open(f)
    if im.size[0] != im.size[1] or im.size[0] > 400 or f.stat().st_size > 120_000:
        fails.append(f"{pid}: should be a small square ({im.size}, {f.stat().st_size} bytes)")
    if pid not in ids:
        fails.append(f"{pid}: not a player of the current data")
print("photo assets:", "FAILED" if fails else f"ok ({len(files)} photos)")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
