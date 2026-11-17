"""Social pages (social.py), the optional "follow a club" choice, and the traffic numbers built on them (daily table, clubs, readable page names)."""
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
import social  # noqa: E402
import traffic  # noqa: E402

auth.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
H = {"X-Admin-Token": "TEST-TOKEN-0000-1111"}
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1"}

# 1. social pages: only configured pages show, https only
check([l["key"] for l in social.links()] == ["facebook", "youtube"], "by default the Facebook and YouTube pages are shown (assets/social.json)")
page = c.get("/").get_data(as_text=True)
check('class="soc s-facebook"' in page and 'class="soc s-youtube"' in page and 'class="soc s-instagram"' not in page, "the footer has the icons of the pages that exist and no empty ones")
check(c.post("/admin/api/social", json={"x": "javascript:alert(1)"}, headers=H).status_code == 422, "an address that is not https:// is refused")
check(c.post("/admin/api/social", json={"youtube": "http://youtube.com/@x"}, headers=H).status_code == 422, "plain http is refused")
check(c.post("/admin/api/social", json={"youtube": "https://www.youtube.com/@tunisiabasket", "instagram": "https://instagram.com/tunisiabasket", "x": "https://x.com/tunisiabasket"}, headers=H).status_code == 200, "the admin saves the addresses")
page = c.get("/").get_data(as_text=True)
check(all(f'class="soc s-{k}"' in page for k in ("facebook", "youtube", "instagram", "x")), "the four icons are in the page")
check(c.post("/admin/api/social", json={"youtube": "https://youtube.com/@y"}).status_code in (401, 403), "only the admin changes them")
check(len(c.get("/api/social").get_json()["links"]) == 4, "the site reads them from /api/social")
c.post("/admin/api/social", json={"youtube": "", "instagram": "", "x": ""}, headers=H)
check('class="soc s-youtube"' not in c.get("/").get_data(as_text=True), "emptying an address removes its icon (the admin's file wins over the shipped one)")

# 2. following a club: optional, one per browser, validated, counted per club
rid, rid2 = "a" * 32, "b" * 32
check(c.post("/api/follow", json={"team": "CA", "rid": rid}, headers=UA).get_json() == {"ok": True}, "a visitor follows a club")
check(c.post("/api/follow", json={"team": "NOPE", "rid": rid}, headers=UA).status_code == 422, "an unknown club is refused")
check(c.post("/api/follow", json={"team": "CA", "rid": "short"}, headers=UA).get_json() == {"ok": False}, "a bad browser code is ignored")
check(c.post("/api/follow", json={"team": "CA", "rid": rid2}, headers={"User-Agent": "Googlebot/2.1"}).get_json() == {"ok": False}, "crawlers are ignored")
c.post("/api/follow", json={"team": "ESG", "rid": rid}, headers=UA)                    # the same browser changes its mind: still one follower
c.post("/api/follow", json={"team": "CA", "rid": rid2}, headers=UA)
s = c.get("/admin/api/traffic?days=7", headers=H).get_json()
fol = {x["code"]: x["followers"] for x in s["clubs"]}
check(fol.get("CA") == 1 and fol.get("ESG") == 1 and s["followers"] == 2, f"one choice per browser, the latest wins: {fol}")
c.post("/api/follow", json={"team": "", "rid": rid}, headers=UA)
check(c.get("/admin/api/traffic?days=7", headers=H).get_json()["followers"] == 1, "an empty team takes the choice back")
rows = [c.post("/api/follow", json={"team": "CA", "rid": "%032x" % i}, headers=UA).get_json()["ok"] for i in range(10)]
check(rows.count(True) < 10, "one device cannot stuff the count: a few changes per day only")
check(json.dumps(s).count(rid) == 0, "the browser code itself is never stored or returned")

# 3. the numbers: Tunisian days, readable names, trend, clubs
c.post("/api/hit", json={"path": "/equipe/CA", "lang": "fr", "rid": rid}, headers=UA)
c.post("/api/hit", json={"path": "/joueur/ca-24-omar-abada", "lang": "fr", "rid": rid}, headers=UA)
s = c.get("/admin/api/traffic?days=7", headers=H).get_json()
check(len(s["series"]) == 7 and all("weekday" in d and "new" in d for d in s["series"]) and s["series"][-1]["day"] == traffic._day(), "one row per day, the last is today (Tunisia time)")
check(s["tz"].startswith("Tunisia") and "previous" in s, "the period is Tunisian time and has the previous period to compare with")
labels = {p[0]: p[3] for p in s["pages"]}
check(labels.get("team/CA") and "Africain" in labels["team/CA"], f"a team page is shown by its club name: {labels}")
ca = next(x for x in s["clubs"] if x["code"] == "CA")
check(ca["views"] >= 2 and ca["visitors"] >= 1, "club readers count its team page and its players' pages")
print("social, follow, traffic:", "FAILED" if fails else "ok")
for m_ in fails:
    print(" -", m_)
sys.exit(1 if fails else 0)
