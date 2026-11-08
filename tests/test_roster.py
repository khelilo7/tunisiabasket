"""Admin roster tools: bios, add / delete (hide) / restore, rename, transfers (with merge), team stats. Admin only, reversible, no corruption."""
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


def check(cond, msg):
    if not cond:
        fails.append(msg)


c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
post = lambda body: c.post("/admin/api/roster", json=body, headers=H)
players = lambda: {p["id"]: p for p in c.get("/api/players").get_json()["players"]}

check(c.get("/admin/api/roster").status_code == 401 and c.post("/admin/api/roster", json={"op": "hide", "id": "ca-24"}).status_code == 401, "roster tools are admin only")
check(c.get("/admin/api/team-stats").status_code == 401, "team stats are admin only")
base = players()
n0 = len(base)
r = c.get("/admin/api/roster", headers=H).get_json()
check(len(r["players"]) == n0 and r["teams"], "roster lists everybody")

# --- bio: typed values are official and clear the 'estimated' flag
pid = "jsk-7"
check(post({"op": "bio", "id": pid, "height": 195, "weight": 88, "birth": "1999-06-16"}).status_code == 200, "bio saved")
b = players()[pid]["bio"]
check(b["height"] == 195 and b["weight"] == 88 and "height" not in (b.get("approx") or []), f"bio applied, estimate flag cleared: {b}")
check(post({"op": "bio", "id": pid, "height": [190, 193]}).status_code == 200 and players()[pid]["bio"]["height"] == [190, 193], "height range")
check(post({"op": "bio", "id": pid, "weight": None}).status_code == 200 and "weight" not in players()[pid]["bio"], "empty value clears the field")
check(post({"op": "bio", "id": pid, "height": 300}).status_code == 422, "absurd height refused")
check(post({"op": "bio", "id": pid, "birth": "1850-01-01"}).status_code == 422, "absurd birth date refused")
check(post({"op": "bio", "id": "nobody-1", "height": 190}).status_code == 404, "unknown player")

# --- add a new signing (no box score yet)
check(post({"op": "add", "team": "CA", "name": "karim  ben salah", "number": 77, "pos": "SG", "height": 192, "weight": 85, "birth": "2001-02-03"}).status_code == 200, "add")
p = players().get("ca-77")
check(p and p["name"] == "Karim Ben Salah" and p["gp"] == 0 and p["pos"] == "SG" and p["bio"]["height"] == 192, f"added player visible with bio: {p and p['name']}")
check(not p["qualified"], "a new player is not ranked")
check(post({"op": "add", "team": "CA", "name": "Duplicate", "number": 77}).status_code == 409, "same team and number refused")
check(post({"op": "add", "team": "CA", "name": base["ca-24"]["name"], "number": 24}).status_code == 409, "a number used by a player with games is refused")
check(post({"op": "add", "team": "ZZZ", "name": "X", "number": 5}).status_code == 422, "unknown team refused")
for url in ("/api/players/ca-77", "/api/teams/CA", "/api/overview", "/api/players", "/api/mvp?phase=1"):
    check(c.get(url).status_code == 200, f"{url} still works with a player who has no games")
check(c.get("/joueur/ca-77-karim-ben-salah").status_code == 200, "its page renders")
check("ca-77" not in c.get("/sitemap.xml").get_data(as_text=True), "players without games are not in the sitemap")

# --- delete (hide) and restore
top = c.get("/api/mvp?phase=1").get_json()["leader"]["id"]
check(post({"op": "hide", "id": top}).status_code == 200, "hide")
check(top not in players() and c.get(f"/api/players/{top}").status_code == 404, "hidden player disappears from the site")
check(c.get("/api/mvp?phase=1").get_json()["leader"]["id"] != top, "and from the MVP race")
check(top in {p["id"] for p in c.get("/admin/api/roster", headers=H).get_json()["players"] if p["hidden"]}, "admin still sees him as deleted")
check(post({"op": "restore", "id": top}).status_code == 200 and top in players(), "restore")

# --- rename
check(post({"op": "rename", "id": "ca-77", "name": "karim bensalah"}).status_code == 200 and players()["ca-77"]["name"] == "Karim Bensalah", "rename")

# --- transfer, no games yet for the new team: shown in the new team at once
g24 = players()["ca-24"]
check(post({"op": "transfer", "id": "ca-24", "to": "JSK", "number": 88, "date": "2026-11-08", "note": "loan"}).status_code == 200, "transfer")
t = players()["ca-24"]
check(t["team"] == "JSK" and t["number"] == 88 and t["teams"] == ["CA", "JSK"] and t["gp"] == g24["gp"], f"moved to JSK, history kept: {t['team']} {t['teams']}")
check(t["transfers"][0]["to"] == "JSK" and t["transfers"][0]["note"] == "loan", "transfer is shown on the profile")
check(any(x["id"] == "ca-24" for x in c.get("/api/teams/JSK").get_json()["players"]), "he is on the JSK roster")
check(post({"op": "transfer", "id": "ca-24", "to": "JSK"}).status_code == 422, "cannot transfer to the same team")
check(post({"op": "undo_transfer", "index": 0}).status_code == 200 and players()["ca-24"]["team"] == "CA", "undo")

# --- transfer onto a number that already has games: needs 'same person', then the two profiles merge
other = next(p for p in players().values() if p["team"] == "USM" and p["gp"] >= 3)
before = g24["gp"] + other["gp"]
r = post({"op": "transfer", "id": "ca-24", "to": "USM", "number": other["number"]})
check(r.status_code == 409, "an existing player with games is never merged silently")
check(post({"op": "transfer", "id": "ca-24", "to": "USM", "number": other["number"], "same_person": True}).status_code == 200, "merge confirmed")
m = players()
check(other["id"] not in m and m["ca-24"]["gp"] == before and m["ca-24"]["team"] == "USM", f"profiles merged: gp {m['ca-24']['gp']} vs {before}")
check(c.get("/api/overview").status_code == 200 and c.get("/api/mvp?phase=1").status_code == 200, "site works after a merge")
post({"op": "undo_transfer", "index": 0})
check(other["id"] in players() and players()["ca-24"]["gp"] == g24["gp"], "undo restores both profiles")

# --- team stats
ts = c.get("/admin/api/team-stats", headers=H).get_json()
check(len(ts["teams"]) == 12 and all(k in ts["teams"][0] for k in ("ppg", "opp_ppg", "fg_pct", "reb", "ast", "stl", "blk", "tov", "w", "l", "rank")), "team stats rows")
ca = next(x for x in ts["teams"] if x["code"] == "CA")
check(ca["w"] + ca["l"] == ca["gp"] and 50 < ca["ppg"] < 130 and 20 < ca["fg_pct"] < 70, f"team stats look sane: {ca}")

# --- photos: admin upload, public file, every player carries the field, removal
import io  # noqa: E402
jpg = b"\xff\xd8\xff\xe0" + b"0" * 500
up = lambda pid, data: c.post("/admin/api/photo", data={"id": pid, "image": (io.BytesIO(data), "a.jpg")}, headers=H)
check(c.post("/admin/api/photo", data={"id": "ca-8"}).status_code == 401, "photo upload is admin only")
check(all("photo" in x for x in players().values()), "every player has a photo field (None = silhouette)")
check(up("ca-8", b"not an image").status_code == 422 and up("nobody-9", jpg).status_code == 422 and up("ca-8", jpg + b"0" * 500000).status_code == 422, "bad / unknown / oversized photo refused")
check(up("ca-8", jpg).status_code == 200, "photo uploaded")
ph = players()["ca-8"]["photo"]
check(ph and ph.startswith("/photo/ca-8.jpg"), f"photo attached to the player: {ph}")
check(c.get("/photo/ca-8.jpg").data == jpg and c.get("/photo/..%2fx.jpg").status_code == 404 and c.get("/photo/zz-1.jpg").status_code == 404, "photo served, nothing else")
check(c.post("/admin/api/photo/delete", json={"id": "ca-8"}, headers=H).status_code == 200 and players()["ca-8"]["photo"] is None, "photo removed")

# --- the admin pages and scripts exist
for p in ("/admin-roster.js", "/admin-images.js"):
    check(c.get(p).status_code == 200, f"{p} served")
check(stats.ROSTER_FILE.exists(), "changes persist in data/roster.json")

print("roster:", "FAILED" if fails else "ok")
for m_ in fails:
    print("  FAIL", m_)
sys.exit(1 if fails else 0)
