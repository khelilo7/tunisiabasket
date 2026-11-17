"""The analyst board v2: tags on made baskets build the team lines, bench points need both fives, the likely starting five is suggested, and the team lines travel with the sheet."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"
os.environ["ANALYTICS_TOKEN"] = "TEST-ANALYST-2222-3333"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analytics  # noqa: E402
import app  # noqa: E402
import auth  # noqa: E402

auth.time.sleep = lambda s: None
analytics.time.sleep = lambda s: None
fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
c = app.app.test_client()
ip = {"REMOTE_ADDR": "198.51.100.9"}
check(c.post("/analytics/api/login", json={"token": "TEST-ANALYST-2222-3333", "name": "Board Tester"}, environ_overrides=ip).status_code == 200, "analyst signs in")

d = c.get("/analytics/api/data").get_json()
check(set(d["fives"]) >= {"CA", "ESG"} and all(len(v) <= 5 for v in d["fives"].values()) and d["fives"]["CA"], "the data carries a likely starting five per club")
check(all(i in {p["id"] for p in d["roster"]["CA"]} for i in d["fives"]["CA"]), "the suggested five are players of that club")

g = c.post("/analytics/api/games", json={"home": "CA", "away": "ESG"}).get_json()
gid = g["id"]
ca, esg = [p["id"] for p in g["players"]["CA"]], [p["id"] for p in g["players"]["ESG"]]
post = lambda op, body: c.post(f"/analytics/api/games/{gid}/{op}", json=body)
check(g["extra"]["CA"] == {"paint": 0, "second": 0, "fast": 0, "tov_pts": 0}, "a new game has empty team lines (no bench yet: the fives are not marked)")
post("lineup", {"team": "CA", "on": ca[:5]})
r = post("lineup", {"team": "ESG", "on": esg[:5]}).get_json()
check(r["extra"]["CA"]["bench"] == 0 and r["extra"]["ESG"]["bench"] == 0, "with both fives marked, bench points exist (0)")

e = lambda pid, stat, **kw: post("event", {"pid": pid, "stat": stat, **kw})
check(e(ca[0], "p2_m", tags=["paint", "fast"]).status_code == 200, "a 2-pointer with tags")
e(ca[1], "p3_m", tags=["paint", "second"])                       # paint is a 2-point tag: dropped on a three
e(ca[7], "p2_m", tags=["tov"])                                    # a bench player's basket, off a turnover
e(ca[2], "ft_m", tags=["second"])
e(ca[3], "p2_x", tags=["paint"])                                  # a miss carries no tag
r = e(esg[0], "p2_m", tags=["bogus", "paint"]).get_json()
tagged = {x["stat"] + str(x["pid"][-3:]): x.get("tags") for x in r["events"] if x["stat"] != "lineup"}
check(r["events"][-1]["tags"] == ["paint"], "an unknown tag is dropped")
x = r["extra"]
check(x["CA"] == {"paint": 2, "second": 3 + 1, "fast": 2, "tov_pts": 2, "bench": 2}, f"CA lines from the tags (and 2 bench points): {x['CA']}")
check(x["ESG"]["paint"] == 2 and x["ESG"]["bench"] == 0, f"ESG lines: {x['ESG']}")
check(all("tags" not in ev for ev in r["events"] if ev["stat"] == "p2_x"), "a missed shot has no tags")

last = next(ev for ev in r["events"] if ev["stat"] == "p2_m" and ev["pid"] == ca[0])
r = post("edit", {"n": last["n"], "tags": ["fast"]}).get_json()
check(r["extra"]["CA"]["paint"] == 0 and r["extra"]["CA"]["fast"] == 2, "editing the tags of an action updates the lines")
r = post("edit", {"n": last["n"], "stat": "p2_x"}).get_json()
check(next(ev for ev in r["events"] if ev["n"] == last["n"]).get("tags") is None, "turning it into a miss drops its tags")
csv_ = c.get(f"/analytics/api/games/{gid}/export-team.csv").get_data(as_text=True).splitlines()
check(csv_[0].startswith("team,paint") and len(csv_) == 3, f"the team lines CSV: {csv_}")
log = " ".join(l["detail"] for l in c.get(f"/analytics/api/games/{gid}").get_json()["log"])
check("in the paint" in log and "off a turnover" in log, "the change log says which tags were added")
check(any("extra" in s and s["extra"] for s in analytics._sheets({**c.get(f"/analytics/api/games/{gid}").get_json(), "matchday": 12, "date": "2026-11-11"})), "the published sheets carry the team lines")
# fouls drawn: one more action, counted per player, in the CSV and in the published sheet
r = e(ca[0], "fd").get_json()
r = e(ca[0], "fd").get_json()
head = c.get(f"/analytics/api/games/{gid}/export.csv").get_data(as_text=True).splitlines()
check(head[0].endswith(",PF,FD"), f"the box score CSV has a FD column: {head[0]}")
row = next(l for l in head[1:] if l.split(",")[2] == next(p["name"] for p in g["players"]["CA"] if p["id"] == ca[0]))
check(row.split(",")[-1] == "2", f"two fouls drawn are counted for the player: {row}")
sheet = analytics._sheets({**c.get(f"/analytics/api/games/{gid}").get_json(), "matchday": 12, "date": "2026-11-11"})
check(any(p.get("fd") == 2 for s_ in sheet for p in s_["players"]), "the published sheet carries the fouls drawn")
print("board v2:", "FAILED" if fails else "ok")
for m_ in fails:
    print(" -", m_)
sys.exit(1 if fails else 0)
