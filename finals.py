"""After the 22 matchdays of the regular season: the six best clubs play the PLAY-OFF, the six others the PLAY-OUT. This module holds both and the season's history around them.

The format known so far (2025-2026 rules and the FTBB's announcements; the 2026-2027 regulation is not published, so the page says so): the clubs start the second phase WITH the points of the regular season; the PLAY-OFF is a
mini-championship of the six, home and away; its first four go to the SUPER PLAY-OFF, semi-finals 1 v 4 and 2 v 3 then a final, each a best-of-five series; the PLAY-OUT is a mini-championship of the six others and the last two clubs go
down to the Nationale 1. So there are THREE groups here: "playoff" (a league), "super" (a series bracket whose sides are the play-off's ranks: "S:playoff:1") and "playout" (a league with a relegation zone).
The format of each group stays configurable (the federation may change it): a group is either:
  * a "league": the six clubs play each other in rounds, with a table; the points of the regular season can be carried over (none / half / all), or
  * a "series": a bracket of best-of-N series (quarter-finals, semi-finals, final...), a series being won by the first club to take the majority of its games.
The admin chooses per group, types the teams and the games (Admin tab "Play-off / Play-out": pasted lists, one line per game), and the site draws it.

Data in `data/finals.json`:
    {"season": "2026-2027", "demo": false, "carry": "half", "stakes": {"playoff": "...", "playout": "..."},
     "groups": {"playoff": {"format": "series", "teams": ["CA", ...], "series": [{"id": "po-sf1", "round": "Semi-final", "a": "CA", "b": "W:po-qf1", "best_of": 3,
                                                                                 "games": [{"home": "CA", "home_score": 80, "away_score": 70, "date": "2027-05-01"}]}]},
                "playout": {"format": "league", "teams": ["ESR", ...], "games": [{"round": 1, "home": "ESR", "away": "CSHS", "home_score": 70, "away_score": 66, "date": ""}]}}}
When a group has no teams yet and `preview` is on, the groups are the six best / six last of the regular season as it stands today (so the page can be seen before the season ends).
Also here: `rank_history()` (the rank of every club after every matchday, for the "race" chart) and `journey()` (where the season stands: phase 1, return leg, play-off / play-out, Cup).
"""
import json
import re
import threading

import config
import cup
import stats

FILE = config.DATA_DIR / "finals.json"
ZONE = 6                      # the six best go to the play-off, the others to the play-out
GROUPS = ("playoff", "super", "playout")
DEFAULT_FORMAT = {"playoff": "league", "super": "series", "playout": "league"}
QUALIFY, RELEGATION = 4, 2            # the first four of the play-off go to the super play-off; the last two of the play-out go down
CARRY = {"none": 0.0, "half": 0.5, "full": 1.0}
_lock = threading.Lock()


def load():
    try:
        d = json.loads(FILE.read_text())
    except (OSError, ValueError):
        d = {}
    groups = {}
    for g in GROUPS:
        x = (d.get("groups") or {}).get(g) or {}
        groups[g] = {"format": x.get("format") if x.get("format") in ("league", "series") else DEFAULT_FORMAT[g], "teams": [t for t in x.get("teams") or [] if isinstance(t, str)],
                     "games": [r for r in x.get("games") or [] if isinstance(r, dict)], "series": [r for r in x.get("series") or [] if isinstance(r, dict)]}
    return {"announced": bool(d.get("announced")), "season": str(d.get("season") or ""), "demo": bool(d.get("demo")), "preview": bool(d.get("preview")), "carry": d.get("carry") if d.get("carry") in CARRY else "full",
            "qualify": d.get("qualify") if isinstance(d.get("qualify"), int) and 1 <= d.get("qualify") <= 6 else QUALIFY,
            "relegation": d.get("relegation") if isinstance(d.get("relegation"), int) and 0 <= d.get("relegation") <= 6 else RELEGATION,
            "stakes": {g: str((d.get("stakes") or {}).get(g) or "") for g in GROUPS}, "groups": groups}


def _write(d):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    tmp.replace(FILE)


# ---------------------------------------------------------------- the regular season: history
def _table(results):
    t = {}
    for r in results:
        for c, f, a in ((r["home"], r["home_score"], r["away_score"]), (r["away"], r["away_score"], r["home_score"])):
            x = t.setdefault(c, {"w": 0, "l": 0, "pf": 0, "pa": 0})
            x["w" if f > a else "l"] += 1
            x["pf"] += f
            x["pa"] += a
    rows = sorted(t.items(), key=lambda kv: (-(2 * kv[1]["w"] + kv[1]["l"]), -(kv[1]["pf"] - kv[1]["pa"]), -kv[1]["pf"], kv[0]))
    return {c: i for i, (c, _) in enumerate(rows, 1)}


def rank_history():
    """{"matchdays": [1..N], "teams": {code: {"name", "ranks": [rank after matchday 1, 2, ...]}}}: how every club climbed or fell during the regular season."""
    o = stats.load_official()
    mds = sorted({r["matchday"] for r in o["results"]})
    teams = {c: {"name": n, "ranks": []} for c, n in o["teams"].items()}
    for md in mds:
        ranks = _table([r for r in o["results"] if r["matchday"] <= md])
        for c, t in teams.items():
            t["ranks"].append(ranks.get(c))
    return {"matchdays": mds, "teams": teams}


MOVE_DAYS = 1          # the rise / fall of the standings stays visible this many days after the round's last game


def movement(today=None, force=False):
    """Who went up and who went down after the last COMPLETE matchday (every game of the round has its result), for ONE day after its last game: {"matchday", "date", "until", "moves": {code: places gained
    (+1 = up one, -2 = down two, 0 = same)}}; None when there is nothing to show (no complete round, no date for it, or the day has passed). `force` shows the last round whatever the date (to look at it)."""
    import datetime
    o = stats.load_official()
    per = {}
    for r in o["results"]:
        per[r["matchday"]] = per.get(r["matchday"], 0) + 1
    need = len(o["teams"]) // 2
    full = sorted(m for m, n in per.items() if n >= need)
    if len(full) < 1 or full[-1] < 2:
        return None
    m = full[-1]
    pair = {frozenset((r["home"], r["away"])) for r in o["results"] if r["matchday"] == m}
    dates = [g["date"] for g in stats.build_all_games() if stats.matchday_hint(g) == m and frozenset(t["code"] for t in g["teams"]) in pair and not g.get("date_approx")]
    dates = dates or [stats.load_calendar().get(m)]
    date = max((x for x in dates if x), default=None)
    if not date:
        return None
    today = today or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))).date()
    until = datetime.date.fromisoformat(date) + datetime.timedelta(days=MOVE_DAYS)
    if not force and today > until:
        return None
    now, before = _table([r for r in o["results"] if r["matchday"] <= m]), _table([r for r in o["results"] if r["matchday"] <= m - 1])
    return {"matchday": m, "date": date, "until": until.isoformat(), "moves": {c: before[c] - now[c] for c in now if c in before}}


def journey():
    """The season as a ribbon: phase 1 (J1-J11), the return leg (J12-J22), the play-off / play-out, the Cup. Each step is done / current / next, with a short fact."""
    o = stats.load_official()
    done_md = max((r["matchday"] for r in o["results"]), default=0)
    p = stats.PHASE_LEN
    steps = [{"key": "phase1", "to": "standings", "from": 1, "until": p}, {"key": "phase2", "to": "standings", "from": p + 1, "until": 2 * p}]
    for s in steps:
        s["state"] = "done" if done_md >= s["until"] else "current" if done_md >= s["from"] - 1 else "next"
        s["played"] = max(0, min(done_md, s["until"]) - s["from"] + 1)
        s["total"] = s["until"] - s["from"] + 1
    f = load()
    fin = any(g["games"] or g["series"] for g in f["groups"].values())
    steps.append({"key": "finals", "to": "finals", "state": "current" if fin else "next", "played": 0, "total": 0, "demo": f["demo"]})
    c = cup.view()
    steps.append({"key": "cup", "to": "cup", "state": "done" if c["champion"] else "current" if c["games"] else "next", "played": c["games"], "total": sum(len(r["ties"]) for r in c["rounds"]), "demo": c["demo"]})
    return steps


# ---------------------------------------------------------------- the two groups
def _regular_standings():
    """The regular season as it stands: [{"code", "name", "rank", "pts", "diff", "j", "w", "l"}]"""
    return stats.official_standings(stats.load_official())


def _group_teams(d, g, standings):
    names = {r["code"]: r for r in standings}
    teams = d["groups"][g]["teams"]
    if not teams and d["preview"]:                                  # before the season is over: the groups as the table stands
        teams = [r["code"] for r in (standings[:ZONE] if g == "playoff" else standings[ZONE:])]
    return [{"code": c, "name": names.get(c, {}).get("name", c), "start_rank": names.get(c, {}).get("rank"), "start_pts": names.get(c, {}).get("pts", 0), "start_diff": names.get(c, {}).get("diff", 0)} for c in teams]


def _league(d, g, teams):
    f = CARRY[d["carry"]]
    n = len(teams)
    expected = n * (n - 1)                                          # home and away
    rows = {t["code"]: {**t, "carry": int(round(t["start_pts"] * f)), "j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0} for t in teams}
    rounds = {}
    for r in d["groups"][g]["games"]:
        played = r.get("home_score") is not None and r.get("away_score") is not None
        rounds.setdefault(int(r.get("round") or 1), []).append({"home": r["home"], "away": r["away"], "home_score": r.get("home_score"), "away_score": r.get("away_score"), "date": r.get("date") or "", "played": played})
        if played:
            for c, a, b in ((r["home"], r["home_score"], r["away_score"]), (r["away"], r["away_score"], r["home_score"])):
                if c in rows:
                    x = rows[c]
                    x["j"] += 1
                    x["w" if a > b else "l"] += 1
                    x["pf"] += a
                    x["pa"] += b
    out = list(rows.values())
    for x in out:
        x["diff"] = x["pf"] - x["pa"]
        x["pts"] = x["carry"] + 2 * x["w"] + x["l"]
    out.sort(key=lambda x: (-x["pts"], -x["diff"], x["start_rank"] or 99, x["code"]))
    played = sum(1 for rr in rounds.values() for x in rr if x["played"])
    done = bool(expected) and played >= expected
    for i, x in enumerate(out, 1):
        x["rank"] = i
        x["move"] = (x["start_rank"] - x["rank"] - (0 if g == "playoff" else ZONE)) if x["start_rank"] else 0     # places gained since the regular season (inside the group)
        # what the rank is worth: the first `qualify` of the play-off go to the super play-off, the last `relegation` of the play-out go down ("final" once every game is played)
        x["zone"] = "up" if g == "playoff" and i <= d["qualify"] else "down" if g == "playout" and d["relegation"] and i > n - d["relegation"] else ""
        x["final"] = done
    return {"table": out, "expected": expected, "played": played, "done": done, "rounds": [{"round": k, "games": sorted(v, key=lambda r: r["home"])} for k, v in sorted(rounds.items())]}


def _series(d, g, teams, seeds=None, seeds_final=False):
    """`seeds`: {"playoff": {1: code, 2: code, ...}}: the sides written "S:playoff:1" (first of the play-off...); they are provisional until `seeds_final` (the play-off is over)."""
    info = {t["code"]: t for t in teams}
    seeds = seeds or {}
    won, series, rounds = {}, {}, []
    for s in d["groups"][g]["series"]:
        series[s["id"]] = s

    def resolve(ref):
        if isinstance(ref, str) and ref.startswith("W:"):
            return won.get(ref[2:])
        if isinstance(ref, str) and ref.startswith("S:"):
            _, grp, rk = (ref.split(":") + ["", ""])[:3]
            return (seeds.get(grp) or {}).get(int(rk) if rk.isdigit() else 0)
        return ref or None

    order, label, count = [], {}, {}
    for s in d["groups"][g]["series"]:                              # "Quarter-finals #2": how an unresolved side is named
        count[s.get("round")] = count.get(s.get("round"), 0) + 1
        label[s["id"]] = f"{s.get('round') or ''} #{count[s.get('round')]}"
    for s in d["groups"][g]["series"]:
        a, b = resolve(s.get("a")), resolve(s.get("b"))
        need = int(s.get("best_of") or 3) // 2 + 1
        wins = {a: 0, b: 0}
        games = []
        for x in s.get("games") or []:
            played = x.get("home_score") is not None and x.get("away_score") is not None
            home = x.get("home") or a
            away = b if home == a else a
            if played and home in wins and away in wins:
                wins[home if x["home_score"] > x["away_score"] else away] += 1
            games.append({"home": home, "away": away, "home_score": x.get("home_score"), "away_score": x.get("away_score"), "date": x.get("date") or "", "played": played})
        winner = next((c for c in (a, b) if c and wins.get(c, 0) >= need), None)
        if winner:
            won[s["id"]] = winner
        seed_ref = lambda ref: str(ref).startswith("S:")
        side = lambda ref, c: ({"code": c, "name": info.get(c, {}).get("name", c), "seed": info.get(c, {}).get("start_rank"), "wins": wins.get(c, 0), "provisional": seed_ref(ref) and not seeds_final} if c else {"from": ref[2:] if str(ref).startswith("W:") else "", "label": label.get(str(ref)[2:], "") if str(ref).startswith("W:") else ""})
        order.append({"id": s["id"], "round": s.get("round") or "", "best_of": int(s.get("best_of") or 3), "need": need, "a": side(s.get("a"), a), "b": side(s.get("b"), b), "games": games, "winner": winner,
                      "done": bool(winner), "live": any(x["played"] for x in games) and not winner})
    for s in order:
        if not rounds or rounds[-1]["name"] != s["round"]:
            rounds.append({"name": s["round"], "series": []})
        rounds[-1]["series"].append(s)
    final = rounds[-1]["series"][-1] if rounds else None
    champion = ({"code": final["winner"], "name": info.get(final["winner"], {}).get("name", final["winner"])} if final and final["winner"] else None)
    return {"rounds": rounds, "champion": champion}


def view():
    d = load()
    standings = _regular_standings()
    out = {"season": d["season"], "demo": d["demo"], "preview": d["preview"], "carry": d["carry"], "zone": ZONE, "groups": {}, "journey": journey(), "regular": standings}
    seeds, seeds_final = {}, False
    for g in ("playoff", "playout", "super"):                        # the super play-off needs the play-off's table
        if g == "super":
            top = (out["groups"]["playoff"].get("table") or [])[:d["qualify"]]
            teams = [{"code": t["code"], "name": t["name"], "start_rank": t["rank"], "start_pts": t["pts"], "start_diff": t["diff"]} for t in top]
            seeds, seeds_final = {"playoff": {t["rank"]: t["code"] for t in top}}, bool(out["groups"]["playoff"].get("done"))
        else:
            teams = _group_teams(d, g, standings)
        grp = {"key": g, "format": d["groups"][g]["format"], "teams": teams, "stakes": d["stakes"][g], "started": bool(d["groups"][g]["games"] or any(s.get("games") for s in d["groups"][g]["series"]))}
        grp.update(_series(d, g, teams, seeds, seeds_final) if grp["format"] == "series" else _league(d, g, teams))
        out["groups"][g] = grp
    out["groups"] = {g: out["groups"][g] for g in GROUPS}
    out["qualify"], out["relegation"] = d["qualify"], d["relegation"]
    # `announced` is the ADMIN's decision (the button "the play-off and the play-out start"): until then NOTHING changes on the public site (no tab, no replaced standings); from then the finals take the
    # place of the championship standings. `played_any` only says that a game has been typed (information for the admin).
    out["announced"] = d["announced"]
    out["played_any"] = any(grp.get("played") or any(x["played"] for rd in grp.get("rounds", []) for s in rd.get("series", []) for x in s.get("games", [])) for grp in out["groups"].values())
    out["active"] = bool(d["preview"] or any(d["groups"][g]["teams"] or d["groups"][g]["games"] or d["groups"][g]["series"] for g in GROUPS))
    return out


# ---------------------------------------------------------------- admin
def _save(mutate):
    with _lock:
        d = load()
        mutate(d)
        _write(d)


def configure(season=None, carry=None, preview=None, stakes=None, formats=None, qualify=None, relegation=None, announced=None):
    def m(d):
        if announced is not None:
            d["announced"] = bool(announced)
        if season is not None:
            if season and not re.fullmatch(r"\d{4}-\d{4}", str(season)):
                raise ValueError("the season is written like 2026-2027")
            d["season"] = str(season)
        if carry is not None:
            if carry not in CARRY:
                raise ValueError("carry-over is none, half or full")
            d["carry"] = carry
        if preview is not None:
            d["preview"] = bool(preview)
        if qualify is not None:
            d["qualify"] = max(1, min(6, int(qualify)))
        if relegation is not None:
            d["relegation"] = max(0, min(6, int(relegation)))
        for g, t in (stakes or {}).items():
            if g in GROUPS:
                d["stakes"][g] = " ".join(str(t).split())[:140]
        for g, f in (formats or {}).items():
            if g in GROUPS and f in ("league", "series"):
                d["groups"][g]["format"] = f
    _save(m)


SUPER_SCAFFOLD = ("SERIES, sf1, Semi-finals, S:playoff:1, S:playoff:4, 5\nSERIES, sf2, Semi-finals, S:playoff:2, S:playoff:3, 5\nSERIES, final, Championship final, W:sf1, W:sf2, 5")


def scaffold_super():
    """The super play-off as announced: semi-finals 1st v 4th and 2nd v 3rd of the play-off, then a final, every series a best of five (the better ranked club hosts games 1, 2 and 5)."""
    _save(lambda d: d["groups"]["super"].update(format="series"))
    return put_series("super", SUPER_SCAFFOLD)


def set_teams(group, codes):
    if group == "super":
        raise ValueError("the super play-off takes the first four of the play-off by itself")
    names = {r["code"] for r in _regular_standings()}
    codes = [str(c).strip().upper() for c in codes if str(c).strip()]
    bad = [c for c in codes if c not in names]
    if group not in GROUPS or bad or len(set(codes)) != len(codes):
        raise ValueError("unknown group or club" + (f": {', '.join(bad)}" if bad else ""))
    _save(lambda d: d["groups"][group].update(teams=codes))


def put_league_games(group, text):
    """`round, HOME, AWAY[, home score, away score[, date]]` per line; the same pairing in the same round is replaced. All or nothing."""
    rows = []
    for i, line in enumerate(str(text or "").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        if len(p) < 3:
            raise ValueError(f"line {i}: write round, HOME, AWAY, home score, away score")
        try:
            r = {"round": int(p[0].lstrip("Jj")), "home": p[1].upper(), "away": p[2].upper()}
            if len(p) >= 5 and p[3] != "":
                r["home_score"], r["away_score"] = int(p[3]), int(p[4])
                if r["home_score"] == r["away_score"]:
                    raise ValueError("equal scores")
            if len(p) > 5 and p[5]:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p[5]):
                    raise ValueError("the date is YYYY-MM-DD")
                r["date"] = p[5]
        except ValueError as e:
            raise ValueError(f"line {i}: {e}") from None
        rows.append(r)

    def m(d):
        known = {t for t in d["groups"][group]["teams"]} or {r["code"] for r in _regular_standings()}
        for i, r in enumerate(rows, 1):
            if r["home"] not in known or r["away"] not in known or r["home"] == r["away"]:
                raise ValueError(f"line {i}: {r['home']} - {r['away']} are not two clubs of this group")
        keep = [x for x in d["groups"][group]["games"] if not any(x["round"] == r["round"] and {x["home"], x["away"]} == {r["home"], r["away"]} for r in rows)]
        d["groups"][group]["games"] = sorted(keep + rows, key=lambda x: (x["round"], x["home"]))
    if group not in GROUPS:
        raise ValueError("unknown group")
    _save(m)
    return len(rows)


def _ref(x):
    """A side of a series: a club code (upper case), W:<series id> (the winner of that series), or S:<group>:<rank> (the club ranked so in that group, e.g. S:playoff:1)."""
    x = x.strip()
    if x[:2].upper() == "W:":
        return "W:" + x[2:]
    if x[:2].upper() == "S:":
        parts = x.split(":")
        return "S:" + (parts[1].lower() if len(parts) > 1 else "") + ":" + (parts[2] if len(parts) > 2 else "")
    return x.upper()


def put_series(group, text):
    """Lines: `SERIES id, round name, A, B, best of` (A and B are club codes or W:<series id>) then `GAME id, HOME, home score, away score[, date]`. The series are replaced by the list given
    (their games are kept when the id stays); games are added to their series. All or nothing."""
    if group not in GROUPS:
        raise ValueError("unknown group")
    sers, games = [], []
    for i, line in enumerate(str(text or "").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        kind = p[0].upper()
        try:
            if kind == "SERIES" and len(p) >= 5:
                sers.append({"id": p[1], "round": p[2], "a": _ref(p[3]), "b": _ref(p[4]), "best_of": int(p[5]) if len(p) > 5 and p[5] else 3})
            elif kind == "GAME" and len(p) >= 5:
                g = {"id": p[1], "home": p[2].upper(), "home_score": int(p[3]), "away_score": int(p[4])}
                if g["home_score"] == g["away_score"]:
                    raise ValueError("equal scores")
                if len(p) > 5 and p[5]:
                    g["date"] = p[5]
                games.append(g)
            else:
                raise ValueError("start with SERIES or GAME")
        except ValueError as e:
            raise ValueError(f"line {i}: {e}") from None

    def m(d):
        grp = d["groups"][group]
        old = {s["id"]: s for s in grp["series"]}
        new = [{**s, "games": (old.get(s["id"]) or {}).get("games", [])} if s["id"] in old else {**s, "games": []} for s in sers] if sers else grp["series"]
        by = {s["id"]: s for s in new}
        listed = {}
        for x in games:
            if x["id"] not in by:
                raise ValueError(f"game of an unknown series {x['id']}")
            listed.setdefault(x["id"], []).append({k: v for k, v in x.items() if k != "id"})
        for sid, gs in listed.items():                       # the games written for a series replace its games (sending the same text twice changes nothing)
            by[sid]["games"] = gs
        grp["series"] = new
    _save(m)
    return len(sers), len(games)


def clear_group(group):
    if group not in GROUPS:
        raise ValueError("unknown group")
    _save(lambda d: d["groups"][group].update(games=[], series=[], teams=[]))
