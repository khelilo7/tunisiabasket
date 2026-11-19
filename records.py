"""League records: the best single-game performances of players and teams, the best season averages, and the all-time records of the league (titles, streaks,
unbeaten runs), so that a record broken in a game is seen on the spot.

Sources, all already on the site:
* every box score (stats.build_all_games: this season's sheets and the past seasons of assets/history/games): player and team records;
* every result without a box score (this season's official results; the tables, round-robin scores and series of assets/history/seasons): team scores and margins;
* the champions since 1955-56 (history.champions): titles and title streaks.
A record is only as complete as the data: the page says which seasons have box scores. Values a sheet cannot hold (a misread 99) are left out (PLAUSIBLE).
"""
from collections import defaultdict

import history
import stats

TOP = 10
# key, label, highest believable value in one game
PLAYER_STATS = [("pts", "Points", 70), ("reb", "Rebounds", 35), ("ast", "Assists", 25), ("stl", "Steals", 15), ("blk", "Blocks", 15),
                ("p3m", "Three-pointers made", 15), ("ftm", "Free throws made", 30), ("pir", "Efficiency (PIR)", 80)]
SEASON_STATS = [("pts", "Points per game"), ("reb", "Rebounds per game"), ("ast", "Assists per game"), ("pir", "Efficiency per game")]
SEASON_MIN_GAMES = 5


def _player_rows(games):
    for g in games:
        a, b = g["teams"]
        for t, o in ((a, b), (b, a)):
            for p in t["players"]:
                if p.get("dnp") or p.get("unnamed") or p.get("min") is None:
                    continue
                yield g, t, o, p


def _entry(g, t, o, value, **more):
    return {"value": value, "team": t["code"], "opp": o["code"], "score": f'{t["points"]}-{o["points"]}', "date": g["date"], "season": stats.season_of(g["date"]),
            "game_id": g.get("id"), "phase": g.get("phase"), **more}


def _results():
    """Every game whose score we know, once: {"season","date","a","b","as","bs","game_id"} (box scores first, then results without one)."""
    out, seen = [], set()
    for g in stats.build_all_games():
        a, b = g["teams"]
        key = (stats.season_of(g["date"]), frozenset(((a["code"], a["points"]), (b["code"], b["points"]))))
        seen.add(key)
        out.append({"season": key[0], "date": g["date"], "a": a["code"], "b": b["code"], "as": a["points"], "bs": b["points"], "game_id": g["id"], "phase": g.get("phase")})

    def add(season, a, b, sa, sb, date=None):
        if not (a and b) or sa is None or sb is None or not (0 < sa < 200 and 0 < sb < 200):
            return
        key = (season, frozenset(((a, sa), (b, sb))))
        if key not in seen:
            seen.add(key)
            out.append({"season": season, "date": date, "a": a, "b": b, "as": sa, "bs": sb, "game_id": None, "phase": None})
    o = stats.load_official()
    for r in o.get("results") or []:
        if r.get("home_score") is not None:
            add(o.get("season"), r["home"], r["away"], r["home_score"], r["away_score"])
    for s in history.season_ids():
        v = history.view(s) or {}
        for sec in v.get("sections") or []:
            for g in sec["games"]:
                h, w = g.get("home"), g.get("away")
                add(s, h.get("code") if isinstance(h, dict) else h, w.get("code") if isinstance(w, dict) else w, g.get("hs"), g.get("as"), g.get("date"))
            for ser in sec["series"]:
                for sa, sb in ser.get("games") or []:
                    add(s, ser["a"].get("code"), ser["b"].get("code"), sa, sb)
    return out


@stats._cached                      # the cache is keyed by function name: never call this "build" (stats.build)
def all_records():
    games = stats.build_all_games()
    player = []
    for key, label, cap in PLAYER_STATS:
        rows = [_entry(g, t, o, p[key], player=p["name"], pid=p["pid"]) for g, t, o, p in _player_rows(games)
                if p.get(key) is not None and 0 < p[key] <= cap]
        rows.sort(key=lambda r: (-r["value"], r["date"]))
        player.append({"key": key, "label": label, "top": rows[:TOP]})

    res = _results()
    team = []
    sides = [dict(r, team=r["a"], opp=r["b"], pf=r["as"], pa=r["bs"]) for r in res] + [dict(r, team=r["b"], opp=r["a"], pf=r["bs"], pa=r["as"]) for r in res]
    row = lambda r, v: {"value": v, "team": r["team"], "opp": r["opp"], "score": f'{r["pf"]}-{r["pa"]}', "date": r["date"], "season": r["season"], "game_id": r["game_id"]}  # noqa: E731
    team.append({"key": "team_pts", "label": "Points scored by a team", "top": sorted((row(r, r["pf"]) for r in sides), key=lambda x: -x["value"])[:TOP]})
    team.append({"key": "margin", "label": "Biggest win", "top": sorted((row(r, r["pf"] - r["pa"]) for r in sides if r["pf"] > r["pa"]), key=lambda x: -x["value"])[:TOP]})
    combined = sorted(({"value": r["as"] + r["bs"], "team": r["a"], "opp": r["b"], "score": f'{r["as"]}-{r["bs"]}', "date": r["date"], "season": r["season"], "game_id": r["game_id"]} for r in res),
                      key=lambda x: -x["value"])[:TOP]
    team.append({"key": "combined", "label": "Highest-scoring game", "top": combined})
    for key, label in (("p3m", "Three-pointers made by a team"), ("ast", "Assists by a team"), ("reb", "Rebounds by a team")):
        rows = []
        for g in games:
            a, b = g["teams"]
            for t, o in ((a, b), (b, a)):
                vals = [p.get(key) for p in t["players"] if not p.get("dnp")]
                if vals and all(v is not None for v in vals):
                    rows.append(_entry(g, t, o, sum(vals)))
        team.append({"key": "team_" + key, "label": label, "top": sorted(rows, key=lambda r: (-r["value"], r["date"]))[:TOP]})

    season = []
    seasons = sorted({stats.season_of(g["date"]) for g in games})
    for key, label in SEASON_STATS:
        rows = []
        for s in seasons:
            for p in stats.build(s)["players"]:
                if p["gp"] >= SEASON_MIN_GAMES and p.get(key) is not None:
                    rows.append({"value": p[key], "player": p["name"], "pid": p["id"], "team": p["team"], "season": s, "gp": p["gp"]})
        season.append({"key": key, "label": label, "top": sorted(rows, key=lambda r: -r["value"])[:TOP]})

    return {"player": player, "team": team, "season": season, "league": league(), "coverage": coverage(games, res)}


def league():
    """Titles and streaks from the champions list, unbeaten tables from the season pages."""
    champs = history.champions()
    titles = defaultdict(list)
    for c in champs:
        titles[c["champion"]].append(c["season"])
    most = sorted(({"club": k, "code": next((c["champion_code"] for c in champs if c["champion"] == k and c.get("champion_code")), None), "value": len(v), "last": v[-1]}
                   for k, v in titles.items()), key=lambda x: (-x["value"], x["last"]))[:TOP]
    streaks, run = [], None
    for c in champs:
        if run and run["club"] == c["champion"] and int(c["season"][:4]) == int(run["to"][:4]) + 1:
            run["value"] += 1
            run["to"] = c["season"]
        else:
            run = {"club": c["champion"], "code": c.get("champion_code"), "value": 1, "from": c["season"], "to": c["season"]}
            streaks.append(run)
    streaks = sorted((s for s in streaks if s["value"] > 1), key=lambda s: (-s["value"], s["from"]))[:TOP]
    unbeaten = []
    for s in history.season_ids():
        for sec in (history.view(s) or {}).get("sections") or []:
            for r in sec["table"] or []:
                if r["l"] == 0 and r["w"] >= 8:
                    unbeaten.append({"team": r.get("code"), "club": r["name"], "value": r["w"], "season": s, "phase": sec["name"]})
    return [{"key": "titles", "label": "Most titles", "top": most}, {"key": "streak", "label": "Most titles in a row", "top": streaks},
            {"key": "unbeaten", "label": "Unbeaten through a phase", "top": sorted(unbeaten, key=lambda x: (-x["value"], x["season"]))}]


def coverage(games, res):
    box = defaultdict(int)
    for g in games:
        box[stats.season_of(g["date"])] += 1
    scores = defaultdict(int)
    for r in res:
        scores[r["season"]] += 1
    return {"box_scores": dict(sorted(box.items())), "scores": dict(sorted((k, v) for k, v in scores.items() if k)), "first_champion": (history.champions() or [{}])[0].get("season")}


def for_game(gid):
    """The records a game set or equalled when it was played: compared with every game before it (by date). [{"key","label","value","who","team","previous","previous_who","equal"}]."""
    games = stats.build_all_games()
    g = next((x for x in games if x["id"] == gid), None)
    if not g:
        return []
    before = [x for x in games if (x["date"], x["id"]) < (g["date"], g["id"])]
    if len(before) < 30:                                             # too little behind it to speak of a record
        return []
    out = []
    for key, label, cap in PLAYER_STATS:
        prev = max(((p[key], p["name"], t["code"], x["date"]) for x, t, o, p in _player_rows(before) if p.get(key) is not None and p[key] <= cap), default=None)
        if not prev:
            continue
        best = max(((p[key], p["name"], t["code"]) for x, t, o, p in _player_rows([g]) if p.get(key) is not None and p[key] <= cap), default=None)
        if best and best[0] >= prev[0] and best[0] > 0:
            out.append({"key": key, "label": label, "value": best[0], "who": best[1], "team": best[2], "previous": prev[0], "previous_who": prev[1], "previous_team": prev[2],
                        "previous_date": prev[3], "equal": best[0] == prev[0]})
    a, b = g["teams"]
    season = stats.season_of(g["date"])
    earlier = [r for r in _results() if r["game_id"] != gid and (r["season"] < season or (r["season"] == season and r["date"] and r["date"] < g["date"]))]   # every known score before it, box score or not
    prev_pts = max((max(r["as"], r["bs"]) for r in earlier), default=0)
    best = max((a, b), key=lambda t: t["points"])
    if prev_pts and best["points"] >= prev_pts:
        out.append({"key": "team_pts", "label": "Points scored by a team", "value": best["points"], "who": best["name"], "team": best["code"], "previous": prev_pts, "equal": best["points"] == prev_pts})
    prev_margin = max((abs(r["as"] - r["bs"]) for r in earlier), default=0)
    margin = abs(a["points"] - b["points"])
    if prev_margin and margin >= prev_margin:
        w = a if a["points"] > b["points"] else b
        out.append({"key": "margin", "label": "Biggest win", "value": margin, "who": w["name"], "team": w["code"], "previous": prev_margin, "equal": margin == prev_margin})
    return out
