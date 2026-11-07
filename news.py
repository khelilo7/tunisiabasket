"""The home page's news feed, built from what we already know: latest matchday results with the game MVPs, the best performance of the
matchday, matches finished on the live board, and the fans' vote while it is open. Structured data only; the page words it in French or English."""
import time

import live
import mvp
import stats


def items(limit_matchdays: int = 2) -> list:
    d = stats.build()
    o = stats.load_official()
    teams = o["teams"]
    by_pair = {}
    for g in d["games"]:
        if g.get("matchday_no"):
            by_pair[(g["matchday_no"], frozenset(t["code"] for t in g["teams"]))] = g
    out = []
    # pinned: the fans' vote
    try:
        r = mvp.race(1)
        if r["voting_open"] and r["leader"]:
            out.append({"kind": "vote", "ts": int(time.time()), "deadline_ts": r["deadline_ts"], "votes": r["total_votes"],
                        "leader": {k: r["leader"][k] for k in ("id", "name", "team", "pts", "reb", "ast", "pir")}})
    except Exception:
        pass
    # live matches that just finished
    for m in live.finals_since(7):
        out.append({"kind": "live_final", "ts": m["finished"], "match": {k: m.get(k) for k in ("id", "home", "away", "home_score", "away_score", "matchday")},
                    "home_name": teams.get(m["home"], m["home"]), "away_name": teams.get(m["away"], m["away"])})
    # official results by matchday, newest first
    days = sorted({r["matchday"] for r in o["results"]}, reverse=True)[:limit_matchdays]
    for md in days:
        results, best = [], None
        for r in sorted((x for x in o["results"] if x["matchday"] == md), key=lambda x: x["home"]):
            g = by_pair.get((md, frozenset([r["home"], r["away"]])))
            results.append({"home": r["home"], "away": r["away"], "home_name": teams.get(r["home"], r["home"]), "away_name": teams.get(r["away"], r["away"]),
                            "home_score": r["home_score"], "away_score": r["away_score"], "game_id": g["id"] if g else None,
                            "mvp": ({k: g["mvp"][k] for k in ("player_id", "name", "team", "pts", "reb", "ast", "pir")} if g and g.get("mvp") else None)})
            if g and g.get("mvp") and (best is None or g["mvp"]["pir"] > best["pir"]):
                best = {k: g["mvp"][k] for k in ("player_id", "name", "team", "pts", "reb", "ast", "pir")} | {"game_id": g["id"]}
        ts = max((g["date"] for k, g in by_pair.items() if k[0] == md), default="")
        out.append({"kind": "matchday", "matchday": md, "date": ts, "ts": md * 1000, "results": results, "best": best})
    return out
