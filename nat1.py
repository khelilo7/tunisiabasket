"""Nationale 1 (National One), the second league below the Pro A: teams, results and the table, nothing else.

We have no box scores for it, so the site only shows what a result gives: who played whom, the score, the standings. The admin types the teams and the results (Admin tab "Nationale 1",
one by one or a pasted list) and they live in `data/nat1.json`, kept across deployments and in the backups:

    {"season": "2026-2027", "teams": {"ESM": "ES Marsa", ...}, "results": [{"matchday": 3, "home": "ESM", "away": "EOS", "home_score": 78, "away_score": 71, "date": "2026-10-04"}],
     "fixtures": [{"matchday": 5, "home": "BS", "away": "EZS", "date": "2026-11-21", "projected": false}],
     "playoff": {"games": {"qf1": [{"home": "EZS", "home_score": 80, "away_score": 70, "date": "2027-04-25"}]}},
     "official": {"published": "2026-11-15", "source": "FTBB", "rows": [{"code": "EZS", "j": 4, "w": 4, "l": 0, "diff": 97, "pts": 8}]}}

`fixtures` is the calendar (a game with no result yet is shown as "to come", or "score missing" once its day has passed). `official` is the federation's own table at one date: when it is there it is
the BASE of the table (we may not have every score, and the FTBB's numbers win over ours), and every result typed after it moves the table on from it. To know which results the FTBB table already
counts, it keeps `basis`, the results we had when it was pasted: table = FTBB rows + (the results now) - (the basis). So a new result adds a game, a corrected score corrects it and a removed
result takes it away, exactly like the computed table. Without an FTBB table the table is computed from the results.

Players come later, "as we go": a player is a name on a team, so the day somebody sends a sheet for a Nationale 1 game it can be added without changing this file's shape.
Same table rules as the Pro A: 2 points for a win, 1 for a loss; a better goal difference breaks a tie in points.
"""
import datetime
import json
import re
import threading

import config
import ranking

FILE = config.DATA_DIR / "nat1.json"
CODE = re.compile(r"^[A-Z0-9]{2,8}$")
TIME = re.compile(r"^([01]?\d|2[0-3])\s*[:hH]\s*([0-5]\d)$")          # 18:30, 18h30, 8:00


def clean_time(v):
    """"HH:MM" from what is typed (18:30, 18h30, 8:00), "" when nothing is typed, ValueError when it is not an hour."""
    v = str(v or "").strip()
    if not v:
        return ""
    m = TIME.match(v)
    if not m:
        raise ValueError("the time is HH:MM, for example 18:30")
    return f"{int(m.group(1)):02d}:{m.group(2)}"
_lock = threading.Lock()
# How a club comes up to the Pro A (FTBB, "Formule du championnat de Tunisie Nationale 1 seniors garçons", season 2025-2026; the regulation of 2026-2027 is not published yet, so `confirmed` stays False and
# the page says so): 22 matchdays, then the first `playoff` clubs play quarter-finals and semi-finals, each a best-of-three (the first game and a possible decider at the better ranked club); the
# TWO semi-final winners go up to the Pro A and play the final in ONE game on neutral ground for the title; the others play the Coupe de la Ligue.
FORMAT = {"playoff": 8, "promoted": 2, "season": "2025-2026", "confirmed": False, "source": "https://www.ftbb.org.tn/wp-content/uploads/2025/11/formule-NATIONALE-1.pdf"}


def load():
    try:
        d = json.loads(FILE.read_text())
    except (OSError, ValueError):
        d = {}
    return {"season": str(d.get("season") or ""), "teams": {k: v for k, v in (d.get("teams") or {}).items() if isinstance(v, str)},
            "results": [r for r in d.get("results") or [] if isinstance(r, dict)], "fixtures": [r for r in d.get("fixtures") or [] if isinstance(r, dict)],
            "official": _official(d),
            "playoff_on": bool(d.get("playoff_on")),
            "playoff": {k: [g for g in v if isinstance(g, dict)] for k, v in ((d.get("playoff") or {}).get("games") or {}).items() if isinstance(v, list)}}


def _key(r):
    return (r["matchday"], frozenset((r["home"], r["away"])))


def _official(d):
    """The FTBB table as stored, with its `basis` (the results it already counts). A table pasted before the basis existed (data of 2026-11) counts the results played on or before its date."""
    off = d.get("official")
    if not isinstance(off, dict) or not off.get("rows"):
        return None
    off = dict(off)
    if not isinstance(off.get("basis"), list):
        pub = str(off.get("published") or "")
        off["basis"] = [_slim(r) for r in d.get("results") or [] if isinstance(r, dict) and (not pub or not r.get("date") or r["date"] <= pub)]
    off["basis"] = [r for r in off["basis"] if isinstance(r, dict)]
    return off


def _slim(r):
    return {k: r[k] for k in ("matchday", "home", "away", "home_score", "away_score")}


def since_official(d):
    """The results that are not counted by the FTBB table as it was pasted: new games and corrected scores (a removed game is not listed, it is just taken away)."""
    off = d.get("official")
    if not off:
        return []
    basis = {_key(r): r for r in off["basis"]}
    return [r for r in d["results"] if _slim(r) != basis.get(_key(r))]


def _write(d):
    d = {**d, "playoff": {"games": d.get("playoff") or {}}}              # the play-off games are stored under {"playoff": {"games": {series id: [games]}}}
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    tmp.replace(FILE)


def season_default():
    t = datetime.date.today()
    y = t.year if t.month >= 8 else t.year - 1
    return f"{y}-{y + 1}"


def _tally(teams, results, sign=1, into=None):
    """Add (sign 1) or take away (sign -1) the games of `results` to the rows of `teams`."""
    t = into if into is not None else {c: {"code": c, "name": n, "j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0} for c, n in teams.items()}
    for r in results:
        for c, f, a in ((r["home"], r["home_score"], r["away_score"]), (r["away"], r["away_score"], r["home_score"])):
            if c in t:
                x = t[c]
                x["j"] += sign
                x["w" if f > a else "l"] += sign
                x["pf"] += sign * f
                x["pa"] += sign * a
    return t


def standings(d=None):
    d = d or load()
    games = [r for r in d["results"] if r["home"] in d["teams"] and r["away"] in d["teams"]]
    off = d.get("official")
    if off:
        rows = []
        for i, r in enumerate(off["rows"], 1):
            rows.append({"code": r["code"], "name": d["teams"].get(r["code"], r["code"]), "rank": i, "j": r["j"], "w": r["w"], "l": r["l"], "pf": None, "pa": None, "diff": r["diff"], "pts": r["pts"]})
        listed = {r["code"] for r in rows}
        rows += [{"code": c, "name": n, "rank": len(rows) + i, "j": 0, "w": 0, "l": 0, "pf": None, "pa": None, "diff": 0, "pts": 0}           # a club the FTBB table does not list (added later)
                 for i, (c, n) in enumerate(((c, n) for c, n in d["teams"].items() if c not in listed), 1)]
        if not since_official(d) and len(games) == len(off["basis"]):
            return [{**r, "final": _over(rows)} for r in rows]          # nothing typed since the FTBB table: it is the table, in the FTBB's own order
        delta = _tally(d["teams"], d["results"])
        _tally(d["teams"], off["basis"], -1, delta)                     # what changed since the FTBB table: the results now minus the ones it counts
        now = _tally(d["teams"], d["results"])                          # (points scored, for the last tie-break of the law)
        by = {r["code"]: r for r in rows}
        order = {r["code"]: i for i, r in enumerate(rows)}
        out = []
        for c, x in by.items():
            dx = delta.get(c) or {"j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0}
            x = {**x, "j": x["j"] + dx["j"], "w": x["w"] + dx["w"], "l": x["l"] + dx["l"], "diff": x["diff"] + dx["pf"] - dx["pa"]}
            x["pts"] = 2 * x["w"] + x["l"]
            out.append(x)
        final = _over(out)
        pf = {c: (now.get(c) or {}).get("pf", 0) for c in by}
        if not final:                                                   # the season is not over: the points, then the point difference (the FTBB's own numbers count), then the FTBB's order
            out2 = sorted(out, key=lambda x: (-x["pts"], -x["diff"], order.get(x["code"], 99)))
            for i, x in enumerate(out2, 1):
                x["rank"], x["final"] = i, False
            return out2
        law = [{**x, "pf": pf[x["code"]], "pa": pf[x["code"]] - x["diff"]} for x in out]          # the law reads pf - pa as the difference: keep the FTBB's difference
        ranked = ranking.rank(law, games, fallback=lambda c: order.get(c, 99))
        keep = {x["code"]: x for x in out}
        moved = {c for c, x in delta.items() if any(x[k] for k in ("j", "w", "l", "pf", "pa"))}
        out = []
        for pts in sorted({x["pts"] for x in ranked}, reverse=True):     # clubs level on points: the law decides, unless none of them has played since the FTBB table (then its order stays)
            group = [keep[x["code"]] for x in ranked if x["pts"] == pts]
            out += group if moved & {x["code"] for x in group} else sorted(group, key=lambda x: order.get(x["code"], 99))
        for i, x in enumerate(out, 1):
            x["rank"], x["final"] = i, True
        return out
    out = list(_tally(d["teams"], d["results"]).values())
    for x in out:
        x["diff"] = x["pf"] - x["pa"]
        x["pts"] = 2 * x["w"] + x["l"]
    final = ranking.complete(len(d["teams"]), games)
    out = ranking.rank(out, games, final=final)       # until the last round: points, then point difference; at the last round the FTBB's law (ranking.py), like the Pro A table
    for i, x in enumerate(out, 1):
        x["rank"], x["final"] = i, final
    return out


def _over(rows):
    """The regular season is over when every club has played everybody home and away (the FTBB table's own numbers of games count)."""
    n = len(rows)
    return n > 1 and all(r["j"] >= 2 * (n - 1) for r in rows)


# The play-off bracket (the ids are the keys of the games stored in data/nat1.json "playoff"): seeds are the first eight of the table, "S:league:N" is the club ranked N
PLAYOFF_SERIES = [("qf1", "Quarter-finals", "S:league:1", "S:league:8", 3), ("qf2", "Quarter-finals", "S:league:4", "S:league:5", 3), ("qf3", "Quarter-finals", "S:league:2", "S:league:7", 3),
                  ("qf4", "Quarter-finals", "S:league:3", "S:league:6", 3), ("sf1", "Semi-finals", "W:qf1", "W:qf2", 3), ("sf2", "Semi-finals", "W:qf3", "W:qf4", 3), ("final", "Championship final", "W:sf1", "W:sf2", 1)]


def playoff(d=None):
    """The play-off as the page draws it: the eight best clubs of the table seeded 1v8, 4v5, 2v7, 3v6, semi-finals, then the final in one game on neutral ground. Until the regular season is over
    (the last game of the calendar is past) the seeds are provisional. The two semi-final winners are `promoted` (they go up to the Pro A); the final decides the title. None when fewer clubs than places."""
    import finals                                                   # (imported here: finals imports cup, which imports this module)
    d = d or load()
    n = FORMAT["playoff"]
    rows = standings(d)[:n]
    if len(rows) < n:
        return None
    dates = [f["date"] for f in d["fixtures"] if f.get("date")]
    over = bool(dates) and max(dates) < _today() and not any(f.get("projected") for f in d["fixtures"])
    teams = [{"code": r["code"], "name": r["name"], "start_rank": r["rank"], "start_pts": r["pts"]} for r in rows]
    series = [{"id": i, "round": rd, "a": a, "b": b, "best_of": bo, "games": d["playoff"].get(i, [])} for i, rd, a, b, bo in PLAYOFF_SERIES]
    out = finals._series({"groups": {"p": {"series": series}}}, "p", teams, {"league": {r["rank"]: r["code"] for r in rows}}, over)
    by = {s["id"]: s for rd in out["rounds"] for s in rd["series"]}
    out["promoted"] = [by[i]["winner"] for i in ("sf1", "sf2") if by[i]["winner"]]
    out["seeds_final"] = over
    out["promote_round"] = "Semi-finals"
    return out


def put_playoff_games(text):
    """Lines `GAME, series id, HOME, home score, away score[, date]` (ids: qf1..qf4, sf1, sf2, final). The games written for a series replace its games. All or nothing."""
    ids = {i for i, *_ in PLAYOFF_SERIES}
    games = {}
    for n, line in enumerate(str(text or "").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        try:
            if p[0].upper() != "GAME" or len(p) < 5:
                raise ValueError("write GAME, series, HOME, home score, away score[, date]")
            sid = p[1].lower()
            if sid not in ids:
                raise ValueError(f"unknown series {p[1]} (qf1 qf2 qf3 qf4 sf1 sf2 final)")
            g = {"home": p[2].upper(), "home_score": _int(p[3], 0, 250), "away_score": _int(p[4], 0, 250)}
            if g["home_score"] == g["away_score"]:
                raise ValueError("the scores are equal")
            if len(p) > 5 and p[5]:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p[5]):
                    raise ValueError("the date is YYYY-MM-DD")
                g["date"] = p[5]
        except ValueError as e:
            raise ValueError(f"line {n}: {e}") from None
        games.setdefault(sid, []).append(g)
    with _lock:
        d = load()
        d["playoff"] = {**d["playoff"], **games}
        _write(d)
    return sum(len(v) for v in games.values())


def set_playoff_on(on):
    """The admin announces (or hides again) the play-off: until then the public site shows no Play-off tab."""
    with _lock:
        d = load()
        d["playoff_on"] = bool(on)
        _write(d)


def clear_playoff():
    with _lock:
        d = load()
        d["playoff"] = {}
        _write(d)


def _today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))).strftime("%Y-%m-%d")


def view():
    """What the public page needs: the table, and every matchday with its games (a score when we have it). Each matchday says whether it was played
    ("played": at least one score, or its day has passed) or is still to come."""
    d = load()
    names = d["teams"]
    games = {}
    for f in d["fixtures"]:
        games[(f["matchday"], frozenset((f["home"], f["away"])))] = {"home": f["home"], "away": f["away"], "home_score": None, "away_score": None, "date": f.get("date"), "time": f.get("time"), "projected": bool(f.get("projected"))}
    for r in d["results"]:
        k = (r["matchday"], frozenset((r["home"], r["away"])))
        g = games.get(k) or {"date": None, "time": None, "projected": False}
        games[k] = {**g, "home": r["home"], "away": r["away"], "home_score": r["home_score"], "away_score": r["away_score"], "date": r.get("date") or g.get("date"), "time": r.get("time") or g.get("time"), "projected": False}
    by = {}
    for (md, _), g in games.items():
        by.setdefault(md, []).append({**g, "home_name": names.get(g["home"], g["home"]), "away_name": names.get(g["away"], g["away"])})
    today, days = _today(), []
    for md, gs in sorted(by.items()):
        dates = [g["date"] for g in gs if g["date"]]
        date, last = min(dates, default=None), max(dates, default=None)
        played = any(g["home_score"] is not None for g in gs) or bool(date and date <= today)
        for g in gs:                                                # the games of a matchday are not always played on the same day: each one is late (its score missing) on its own day
            g["missing"] = g["home_score"] is None and bool(g["date"] or date) and (g["date"] or date) <= today
        days.append({"matchday": md, "date": date, "date_end": last, "played": played, "projected": all(g["projected"] for g in gs),
                     "missing": sum(g["missing"] for g in gs), "games": sorted(gs, key=lambda g: g["home"])})
    off = d["official"]
    return {"season": d["season"] or season_default(), "teams": names, "standings": standings(d), "matchdays": days, "games": len(d["results"]), "format": FORMAT, "playoff": playoff(d), "playoff_on": d["playoff_on"],
            "official": {"published": off.get("published"), "source": off.get("source") or "FTBB", "since": len(since_official(d))} if off else None}


def _int(v, lo, hi):
    if isinstance(v, bool):
        raise ValueError("a number is needed")
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        raise ValueError("a number is needed") from None
    if not lo <= n <= hi:
        raise ValueError(f"{n} is out of range ({lo}-{hi})")
    return n


def clean_result(r, teams):
    """A trusted result from a dict (matchday, home, away, home_score, away_score, date), or ValueError naming what is wrong."""
    home, away = str(r.get("home") or "").strip().upper(), str(r.get("away") or "").strip().upper()
    for c in (home, away):
        if c not in teams:
            raise ValueError(f"unknown team {c or '(empty)'}: add it first")
    if home == away:
        raise ValueError("a team cannot play itself")
    date = str(r.get("date") or "").strip()
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("the date is YYYY-MM-DD")
    out = {"matchday": _int(r.get("matchday"), 1, 60), "home": home, "away": away, "home_score": _int(r.get("home_score"), 0, 250), "away_score": _int(r.get("away_score"), 0, 250)}
    if out["home_score"] == out["away_score"]:
        raise ValueError("a basketball game has a winner: the scores are equal")
    if date:
        out["date"] = date
    time = clean_time(r.get("time"))
    if time:
        out["time"] = time
    return out


def add_team(code, name):
    code, name = str(code or "").strip().upper(), " ".join(str(name or "").split())
    if not CODE.match(code):
        raise ValueError("the code is 2 to 8 letters or digits (ESM, EOS...)")
    if not 2 <= len(name) <= 40:
        raise ValueError("the name is 2 to 40 characters")
    with _lock:
        d = load()
        d["teams"][code] = name
        d["season"] = d["season"] or season_default()
        _write(d)
    return d


def remove_team(code):
    with _lock:
        d = load()
        if any(code in (r["home"], r["away"]) for r in d["results"]):
            raise ValueError("this team has results: remove them first")
        d["teams"].pop(code, None)
        _write(d)


def set_season(season):
    if not re.fullmatch(r"\d{4}-\d{4}", str(season or "")):
        raise ValueError("the season is written like 2026-2027")
    with _lock:
        d = load()
        d["season"] = season
        _write(d)


def _clash(d, r):
    """The result of the same matchday that has one of these teams already (a team plays once per matchday), other than the same pairing (which is replaced)."""
    pair = {r["home"], r["away"]}
    for x in d["results"]:
        if x["matchday"] == r["matchday"] and {x["home"], x["away"]} != pair and pair & {x["home"], x["away"]}:
            return x
    return None


def put_results(rows):
    """Add or replace results (same matchday + same pair = replace). All or nothing: returns (added, replaced), or raises ValueError('line N: ...')."""
    with _lock:
        d = load()
        added = replaced = 0
        for i, raw in enumerate(rows, 1):
            try:
                r = clean_result(raw, d["teams"])
                cal = [f for f in d["fixtures"] if f["matchday"] == r["matchday"]]
                fx = next((f for f in cal if {f["home"], f["away"]} == {r["home"], r["away"]}), None)
                if cal and not fx:                                      # the matchday has its calendar: the game must be one of it (home and away may be swapped: a venue change)
                    raise ValueError(f"{r['home']} – {r['away']} is not a game of J{r['matchday']} in the calendar")
                if fx and fx.get("date") and "date" not in r:
                    r["date"] = fx["date"]                              # the day of the calendar, unless another one is typed
                if fx and fx.get("time") and "time" not in r:
                    r["time"] = fx["time"]                              # and its hour
                x = _clash(d, r)
                if x:
                    raise ValueError(f"{x['home']} - {x['away']} is already J{r['matchday']}: a team plays once per matchday")
            except ValueError as e:
                raise ValueError(f"line {i}: {e}") from None
            hit = next((x for x in d["results"] if x["matchday"] == r["matchday"] and {x["home"], x["away"]} == {r["home"], r["away"]}), None)
            if hit:
                d["results"].remove(hit)
                replaced += 1
            else:
                added += 1
            d["results"].append(r)
        d["results"].sort(key=lambda r: (r["matchday"], r["home"]))
        d["season"] = d["season"] or season_default()
        _write(d)
    return added, replaced


def parse_lines(text):
    """A pasted list, one result per line: `matchday, HOME, AWAY, home score, away score[, date[, time]]` (commas, semicolons or tabs). Blank lines and lines starting with # are skipped."""
    rows = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        if len(p) < 5:
            raise ValueError(f"“{line}”: write matchday, home, away, home score, away score")
        rows.append({"matchday": p[0].lstrip("Jj"), "home": p[1], "away": p[2], "home_score": p[3], "away_score": p[4], "date": p[5] if len(p) > 5 else "", "time": p[6] if len(p) > 6 else ""})
    return rows


def remove_result(matchday, home, away):
    with _lock:
        d = load()
        n = len(d["results"])
        d["results"] = [r for r in d["results"] if not (r["matchday"] == matchday and {r["home"], r["away"]} == {home, away})]
        _write(d)
    return n - len(d["results"])


def set_time(matchday, home, away, time, date=None):
    """Set (or clear, with "") the hour of one game, and its day when `date` is given, in the calendar and in its result if it has one: the hour of a game is known
    well before its score. Raises ValueError when the game is neither in the calendar nor a result."""
    time = clean_time(time)
    date = str(date or "").strip()
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("the date is YYYY-MM-DD")
    pair = {str(home).upper(), str(away).upper()}
    with _lock:
        d = load()
        hit = [x for x in (*d["fixtures"], *d["results"]) if x["matchday"] == int(matchday) and {x["home"], x["away"]} == pair]
        if not hit:
            raise ValueError("that game is not in the calendar")
        for x in hit:
            if time:
                x["time"] = time
            else:
                x.pop("time", None)
            if date:
                x["date"] = date
        _write(d)
    return time


def parse_fixtures(text):
    """A pasted calendar, one game per line: `matchday, HOME, AWAY, date[, time][, projected]` (time = 18:30 or 18h30; projected = the pairing is assumed, not published)."""
    rows = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        if len(p) < 3:
            raise ValueError(f"“{line}”: write matchday, home, away, date")
        rest = p[4:]
        rows.append({"matchday": p[0].lstrip("Jj"), "home": p[1], "away": p[2], "date": p[3] if len(p) > 3 else "", "time": next((x for x in rest if TIME.match(x)), ""),
                     "projected": any(x.lower() in ("1", "true", "yes", "projected") for x in rest)})
    return rows


def put_fixtures(rows):
    """Add or replace calendar games (same matchday + same pair = replace). All or nothing, like the results."""
    with _lock:
        d = load()
        for i, raw in enumerate(rows, 1):
            try:
                home, away = str(raw.get("home") or "").strip().upper(), str(raw.get("away") or "").strip().upper()
                for c in (home, away):
                    if c not in d["teams"]:
                        raise ValueError(f"unknown team {c or '(empty)'}: add it first")
                if home == away:
                    raise ValueError("a team cannot play itself")
                date = str(raw.get("date") or "").strip()
                if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    raise ValueError("the date is YYYY-MM-DD")
                f = {"matchday": _int(raw.get("matchday"), 1, 60), "home": home, "away": away, "projected": bool(raw.get("projected"))}
                if date:
                    f["date"] = date
                time = clean_time(raw.get("time"))
                if time:
                    f["time"] = time
            except ValueError as e:
                raise ValueError(f"line {i}: {e}") from None
            d["fixtures"] = [x for x in d["fixtures"] if not (x["matchday"] == f["matchday"] and {x["home"], x["away"]} == {home, away})]
            d["fixtures"].append(f)
        d["fixtures"].sort(key=lambda x: (x["matchday"], x["home"]))
        _write(d)
    return len(rows)


def parse_official(text):
    """The federation's table, pasted: an optional first line `date: 2026-11-15`, then one team per line in table order: `CODE, played, won, lost, difference, points`."""
    published, rows = "", []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("date"):
            published = line.split(":", 1)[1].strip() if ":" in line else ""
            continue
        p = [x.strip() for x in re.split(r"[;,\t ]+", line.replace("+", ""))]
        if len(p) < 6:
            raise ValueError(f"“{line}”: write CODE, played, won, lost, difference, points")
        rows.append({"code": p[0].upper(), "j": p[1], "w": p[2], "l": p[3], "diff": p[4], "pts": p[5]})
    return published, rows


def set_official(published, rows, source="FTBB"):
    """Store the federation's table (every code must be a known team; points must be 2 per win + 1 per loss, a typo guard). An empty list removes it."""
    with _lock:
        d = load()
        if not rows:
            d["official"] = None
            _write(d)
            return 0
        out = []
        for i, r in enumerate(rows, 1):
            try:
                if r["code"] not in d["teams"]:
                    raise ValueError(f"unknown team {r['code']}")
                row = {"code": r["code"], "j": _int(r["j"], 0, 60), "w": _int(r["w"], 0, 60), "l": _int(r["l"], 0, 60), "diff": _int(r["diff"], -3000, 3000), "pts": _int(r["pts"], 0, 200)}
                if row["w"] + row["l"] != row["j"]:
                    raise ValueError("wins + losses must equal the games played")
                if row["pts"] != 2 * row["w"] + row["l"]:
                    raise ValueError(f"points should be {2 * row['w'] + row['l']} (2 per win, 1 per loss)")
            except ValueError as e:
                raise ValueError(f"line {i}: {e}") from None
            out.append(row)
        if published and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
            raise ValueError("the date is YYYY-MM-DD")
        d["official"] = {"published": published, "source": source, "rows": out, "basis": [_slim(r) for r in d["results"]]}     # it counts every result we have now
        _write(d)
        return len(out)
