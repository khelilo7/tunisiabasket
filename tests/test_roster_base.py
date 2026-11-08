"""assets/roster.json ships with the code: same-person merges, renames and transfers apply to every copy of the site, and the admin never copies them into data/."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402
import stats  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
base = json.loads((Path(stats.ROSTER_BASE)).read_text())
pl = {p["id"]: p for p in c.get("/api/players").get_json()["players"]}
for alias, pid in base["merges"].items():
    check(alias not in pl and pid in pl, f"merge {alias} -> {pid}: one profile left")
for pid, name in base["renames"].items():
    check(pl.get(pid, {}).get("name") == name, f"{pid} is shown as {name}")
for t in base["transfers"]:
    p = pl.get(t["id"])
    check(p and p["team"] == t["to"] and t["to"] in p["teams"], f"{t['id']} is shown in {t['to']}")
check(pl["jsm-17"]["gp"] >= 3 and pl["sn-6"]["gp"] >= 3, "the merged profiles carry all the games")
# the admin's own changes stay in its own file
check(c.post("/admin/api/roster", json={"op": "rename", "id": "ca-24", "name": "Omar Abada"}, headers=H).status_code == 200, "an admin change saves")
mine = json.loads(stats.ROSTER_FILE.read_text())
check(not mine.get("merges") and not any(t["id"] in {x["id"] for x in base["transfers"]} for t in mine["transfers"]) and "jsm-17" not in mine["renames"], "shipped roster facts are not copied into data/roster.json")
check(not any(t["id"] == "usa-7" for t in c.get("/admin/api/roster", headers=H).get_json()["changes"]["transfers"]), "the admin's list of transfers shows its own only (what ships cannot be undone from there)")
print("roster base:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
