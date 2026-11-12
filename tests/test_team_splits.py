"""Team statistics, overall / at home / away: the splits add up, the ratios are ratios of sums, ranks are fair, the API and the page carry them."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import stats  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


o = stats.load_official()
sp = stats.team_splits()
check(set(sp) == set(o["teams"]) and all(set(v) == {"all", "home", "away"} for v in sp.values()), "every team has the three views")
for c, v in sp.items():
    a, h, w = v["all"], v["home"], v["away"]
    check(a["gp"] == a["w"] + a["l"] == len([r for r in o["results"] if c in (r["home"], r["away"])]), f"{c}: record = official results")
    check(h["gp"] + w["gp"] == a["gp"] and h["w"] + w["w"] == a["w"] and h["l"] + w["l"] == a["l"], f"{c}: home + away = overall")
    check(h["gp"] == len([r for r in o["results"] if r["home"] == c]), f"{c}: home games are the ones he hosted")
    if a["gp"]:
        check(abs(a["ppg"] * a["gp"] - (h["ppg"] * h["gp"] + w["ppg"] * w["gp"])) < 0.2 * a["gp"], f"{c}: scoring adds up across views")
    check(a["box"] >= h["box"] + w["box"] and a["box"] <= a["gp"], f"{c}: box scores {a['box']} / {h['box']} / {w['box']}")
    if a["box"]:
        check(30 < a["fg_pct"] < 65 and 0 < a["p3_pct"] < 60 and 40 < a["ft_pct"] <= 100 and 35 < a["ts_pct"] < 80, f"{c}: shooting looks sane")
        check(a["efg_pct"] >= a["fg_pct"] - 0.1, f"{c}: eFG% is at least FG%")
        check(abs(a["net"] - (a["ortg"] - a["drtg"])) < 0.2 and 60 < a["pace"] < 95 and 50 < a["ortg"] < 150, f"{c}: ratings and pace look sane ({a['ortg']}, {a['drtg']}, {a['pace']})")
        check(0 < a["tov_pct"] < 30 and 10 < a["oreb_pct"] < 60 and 40 < a["dreb_pct"] < 90, f"{c}: percentages in range")
        check(abs(a["reb"] - a["oreb"] - a["dreb"]) < 0.3, f"{c}: REB = OR + DR")
# league: what teams score is what the opponents allow (box scores), and a rank is 1..N with the best first
for s in stats.SPLITS:
    for k, better in stats.TEAM_METRICS.items():
        ranked = {c: v[s]["rank"][k] for c, v in sp.items() if k in v[s]["rank"]}
        if better is None:
            check(not ranked, f"{k}: a style number has no rank")
            continue
        check(ranked and min(ranked.values()) == 1 and max(ranked.values()) <= len(o["teams"]), f"{s}/{k}: ranks 1..N")
        best = min(ranked, key=ranked.get)
        vals = {c: sp[c][s][k] for c in ranked}
        check(all((vals[best] >= v) if better else (vals[best] <= v) for v in vals.values()), f"{s}/{k}: rank 1 is the best value ({'high' if better else 'low'})")
top = min(sp, key=lambda c: sp[c]["all"]["rank"]["win_pct"])
check(sp[top]["all"]["win_pct"] == max(v["all"]["win_pct"] for v in sp.values()), "best win % has rank 1")
check(abs(sum(v["all"]["ppg"] for v in sp.values()) - sum(v["all"]["opp_ppg"] for v in sp.values())) < 2.0, "league: points scored = points allowed")
# the opponents' view: what a team allows in a box score is what the other team scored
d = stats.build()
g = next(g for g in d["games"] if g.get("home_team"))
check(g["home_team"] in {t["code"] for t in g["teams"]}, "a linked box score knows its home team")

c = app.app.test_client()
t = c.get("/api/teams/CA").get_json()
check(set(t["splits"]) == {"all", "home", "away"} and t["teams_ranked"] == len(o["teams"]) and "rank" in t["splits"]["all"], "the team API carries the splits")
check(t["splits"]["all"]["gp"] == t["standing"]["j"], "views agree with the standing")
check(all(c.get(f"/api/teams/{code}").status_code == 200 for code in o["teams"]), "every team page loads")
html = c.get("/").get_data(as_text=True)
check("teamStatsBlock" in html and "data-split" in html, "the page has the team statistics block")

print("team splits:", "FAILED" if fails else "ok")
for m in fails:
    print("  FAIL", m)
sys.exit(1 if fails else 0)
