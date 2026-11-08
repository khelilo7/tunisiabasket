"""tools/import_photos.py: matches files to players by id or name, crops to a square JPEG, writes data/photos and the index, skips what it cannot match."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parent.parent
data, inbox = tempfile.mkdtemp(), Path(tempfile.mkdtemp())
env = {**os.environ, "DATA_DIR": data}
Image.new("RGB", (600, 900), (200, 100, 50)).save(inbox / "ca-24.jpg")
Image.new("RGB", (500, 400), (10, 100, 50)).save(inbox / "Firas LAHYANI.png")
Image.new("RGB", (100, 100)).save(inbox / "nobody-99.jpg")
(inbox / "notes.txt").write_text("not an image")
r = subprocess.run([sys.executable, str(root / "tools" / "import_photos.py"), str(inbox)], capture_output=True, text=True, env=env, cwd=root)
fails = []
idx = json.loads((Path(data) / "player_photos.json").read_text()) if (Path(data) / "player_photos.json").exists() else {}
if r.returncode != 0 or "2 photo(s) imported" not in r.stdout:
    fails.append(f"two photos imported: {r.stdout} {r.stderr}")
if set(idx) != {"ca-24", "usm-23"}:
    fails.append(f"index lists the matched players only: {idx}")
for pid in ("ca-24", "usm-23"):
    f = Path(data) / "photos" / f"{pid}.jpg"
    if not f.exists() or Image.open(f).size != (320, 320):
        fails.append(f"{pid}: 320x320 square JPEG saved")
if "SKIPPED nobody-99.jpg" not in r.stdout:
    fails.append("unknown file reported and skipped")
print("import photos:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
