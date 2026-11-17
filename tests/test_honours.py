"""Club honours (assets/honours.json): a small mention on the team page; every club of the league is listed, years are sane, the page API carries them."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import honours  # noqa: E402
import stats  # noqa: E402

fails = []
check = lambda cond, msg: fails.append(msg) if not cond else None
d = honours.load()
teams = set(stats.load_official()["teams"])
check(teams <= set(d["clubs"]), f"every club of the league is listed (even with no title): missing {teams - set(d['clubs'])}")
check(all(isinstance(y, int) and 1956 <= y <= 2026 for c in d["clubs"].values() for k in ("league", "cup", "africa", "bal", "africa_final", "bal_final", "arab", "arab_final", "maghreb", "maghreb_final") for y in c.get(k, [])), "years are plausible")
check(all(c.get(k, []) == sorted(set(c.get(k, []))) for c in d["clubs"].values() for k in ("league", "cup")), "years are sorted, no repeat")
for k in ("league", "cup"):                                    # one champion per season, across all the clubs we list
    seen = [y for c in d["clubs"].values() for y in c.get(k, [])]
    check(len(seen) == len(set(seen)), f"two clubs share a {k} title in the same season")
check(all(u.startswith("https://") for u in d["sources"].values()) and {"league", "cup", "africa", "bal"} <= set(d["sources"]), "every list names its source")
h = honours.for_club("USM")
check(h["league"]["n"] == 10 and h["league"]["last"] == "2025-26" and h["bal"] == ["2022"] and h["cup"]["n"] == 6, f"a club's mention: {h and h['league']}")
check(honours.for_club("ESS")["africa"] == ["2011"] and honours.for_club("ESS")["africa_final"] == ["2008", "2013"], "the African Champions Cup, won and lost in the final, is a side note")
check(honours.for_club("ESR")["africa_final"] == ["2014", "2017"] and honours.for_club("USM")["bal_final"] == ["2021"], "runners-up of the African Cup and the BAL are listed")
check(all(c.get(k, []) == sorted(set(c.get(k, []))) and not set(c.get(k, [])) & set(c.get(k.replace("_final", ""), [])) for c in d["clubs"].values() for k in ("africa_final", "bal_final", "arab_final", "maghreb_final")), "a club is not both winner and runner-up of the same year")
check({"arab", "maghreb"} <= set(d["sources"]), "the Arab and Maghreb lists name their source")
check(honours.for_club("JSK")["maghreb"] == ["2003"] and honours.for_club("JSK")["arab_final"] == ["2012"], "JSK: Maghreb winner 2003, Arab Cup finalist 2012")
check(honours.for_club("ESS")["arab"] == ["2015", "2016"] and honours.for_club("SN")["arab"] == ["1997"] and honours.for_club("SN")["arab_final"] == ["1993"] and honours.for_club("ESG")["arab_final"] == ["1988", "1992"], "Arab Cup winners and finalists")
check(all("fourth" not in str(v).lower() and "third" not in str(v).lower() for v in d["clubs"].values()), "no third or fourth place is listed")
check(honours.for_club("CSS") is None and honours.for_club("ZZZ") is None, "no title, no mention")
t = app.app.test_client().get("/api/teams/USM").get_json()
check(t["honours"]["cup"]["n"] == 6 and t["honours"]["sources"], "the team page API carries the honours")
print("honours:", "FAILED" if fails else "ok")
for m in fails:
    print(" -", m)
sys.exit(1 if fails else 0)
