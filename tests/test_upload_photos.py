"""tools/upload_photos.py end to end against a real local server: login, upload, the site shows the photos, --remove takes them down, wrong token is refused."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image

root = Path(__file__).resolve().parent.parent
src, dst = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())          # this computer's data, and the "production" site's data
(src / "photos").mkdir()
for pid in ("ca-24", "usm-23"):
    Image.new("RGB", (320, 320), (120, 60, 30)).save(src / "photos" / f"{pid}.jpg", "JPEG")
(src / "player_photos.json").write_text(json.dumps({"ca-24": "/photo/ca-24.jpg?v=1", "usm-23": "/photo/usm-23.jpg?v=1", "usm-1": "/img/players/usm-1.jpg"}))
s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); port = s_.getsockname()[1]; s_.close()
env = {**os.environ, "DATA_DIR": str(dst), "ADMIN_TOKEN": "TEST-TOKEN-0000-1111", "PORT": str(port), "AUTO_SYNC": "0"}
srv = subprocess.Popen([sys.executable, "app.py"], cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
fails = []
try:
    site = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            requests.get(site + "/api/players", timeout=1); break
        except requests.RequestException:
            time.sleep(0.5)
    run = lambda *a, token="TEST-TOKEN-0000-1111": subprocess.run([sys.executable, "tools/upload_photos.py", "--site", site, *a], cwd=root, capture_output=True, text=True,
                                                                  env={**os.environ, "DATA_DIR": str(src), "ADMIN_TOKEN": token})
    photos = lambda: {p["id"] for p in requests.get(site + "/api/players").json()["players"] if (p.get("photo") or "").startswith("/photo/")}
    r = run("--dry-run")
    if "2 photo(s) would be sent" not in r.stdout or photos():
        fails.append(f"dry run lists two and sends nothing: {r.stdout} {r.stderr}")
    r = run(token="WRONG")
    if r.returncode == 0 or photos():
        fails.append("a wrong token is refused and nothing is sent")
    r = run()
    if "Sent 2 of 2" not in r.stdout or photos() != {"ca-24", "usm-23"}:
        fails.append(f"two photos sent and shown by the site: {r.stdout} {r.stderr} {photos()}")
    if requests.get(f"{site}/photo/ca-24.jpg").status_code != 200:
        fails.append("the uploaded photo is served")
    r = run("--remove")
    if "Removed 2" not in r.stdout or photos():
        fails.append(f"--remove takes them down: {r.stdout} {r.stderr}")
finally:
    srv.terminate()
print("upload photos:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
