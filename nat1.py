"""Nationale 1 (National One), the second league below the Pro A: teams, results and the table, nothing else.

We have no box scores for it, so the site only shows what a result gives: who played whom, the score, the standings. The admin types the teams and the results (Admin tab "Nationale 1",
one by one or a pasted list) and they live in `data/nat1.json`, kept across deployments and in the backups:

    {"season": "2026-2027", "teams": {"ESM": "ES Marsa", ...}, "results": [{"matchday": 3, "home": "ESM", "away": "EOS", "home_score": 78, "away_score": 71, "date": "2026-10-04"}],
     "fixtures": [{"matchday": 5, "home": "BS", "away": "EZS", "date": "2026-11-21", "projected": false}],
     "official": {"published": "2026-11-15", "source": "FTBB", "rows": [{"code": "EZS", "j": 4, "w": 4, "l": 0, "diff": 97, "pts": 8}]}}

`fixtures` is the calendar (a game with no result yet is shown as "to come", or "score missing" once its day has passed). `official` is the federation's own table: when it is there it IS the table
(we may not have every score, so we cannot recompute it); otherwise the table is computed from the results.

Players come later, "as we go": a player is a name on a team, so the day somebody sends a sheet for a Nationale 1 game it can be added without changing this file's shape.
Same table rules as the Pro A: 2 points for a win, 1 for a loss; a better goal difference breaks a tie in points.
"""
import datetime
import json
import re
import threading

import config

FILE = config.DATA_DIR / "nat1.json"
CODE = re.compile(r"^[A-Z0-9]{2,8}$")
_lock = threading.Lock()


def load():
    try:
        d = json.loads(FILE.read_text())
    except (OSError, ValueError):
        d = {}
    return {"season": str(d.get("season") or ""), "teams": {k: v for k, v in (d.get("teams") or {}).items() if isinstance(v, str)},
            "results": [r for r in d.get("results") or [] if isinstance(r, dict)], "fixtures": [r for r in d.get("fixtures") or [] if isinstance(r, dict)],
            "official": d.get("official") if isinstance(d.get("official"), dict) and d["official"].get("rows") else None}


def _write(d):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    tmp.replace(FILE)


def season_default():
    t = datetime.date.today()
    y = t.year if t.month >= 8 else t.year - 1
    return f"{y}-{y + 1}"


def standings(d=None):
    d = d or load()
    if d.get("official"):
        rows = []
        for i, r in enumerate(d["official"]["rows"], 1):
            rows.append({"code": r["code"], "name": d["teams"].get(r["code"], r["code"]), "rank": i, "j": r["j"], "w": r["w"], "l": r["l"], "pf": None, "pa": None, "diff": r["diff"], "pts": r["pts"]})
        return rows
    t = {c: {"code": c, "name": n, "j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0} for c, n in d["teams"].items()}
    for r in d["results"]:
        for c, f, a in ((r["home"], r["home_score"], r["away_score"]), (r["away"], r["away_score"], r["home_score"])):
            if c in t:
                x = t[c]
                x["j"] += 1
                x["w" if f > a else "l"] += 1
                x["pf"] += f
                x["pa"] += a
    out = list(t.values())
    for x in out:
        x["diff"] = x["pf"] - x["pa"]
        x["pts"] = 2 * x["w"] + x["l"]
    out.sort(key=lambda x: (-x["pts"], -x["diff"], -x["pf"], x["name"]))
    for i, x in enumerate(out, 1):
        x["rank"] = i
    return out


def _today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))).strftime("%Y-%m-%d")


def view():
    """What the public page needs: the table, and every matchday with its games (a score when we have it). Each matchday says whether it was played
    ("played": at least one score, or its day has passed) or is still to come."""
    d = load()
    names = d["teams"]
    games = {}
    for f in d["fixtures"]:
        games[(f["matchday"], frozenset((f["home"], f["away"])))] = {"home": f["home"], "away": f["away"], "home_score": None, "away_score": None, "date": f.get("date"), "projected": bool(f.get("projected"))}
    for r in d["results"]:
        k = (r["matchday"], frozenset((r["home"], r["away"])))
        g = games.get(k) or {"date": None, "projected": False}
        games[k] = {**g, "home": r["home"], "away": r["away"], "home_score": r["home_score"], "away_score": r["away_score"], "date": r.get("date") or g.get("date"), "projected": False}
    by = {}
    for (md, _), g in games.items():
        by.setdefault(md, []).append({**g, "home_name": names.get(g["home"], g["home"]), "away_name": names.get(g["away"], g["away"])})
    today, days = _today(), []
    for md, gs in sorted(by.items()):
        date = min((g["date"] for g in gs if g["date"]), default=None)
        played = any(g["home_score"] is not None for g in gs) or bool(date and date <= today)
        days.append({"matchday": md, "date": date, "played": played, "projected": all(g["projected"] for g in gs),
                     "missing": sum(g["home_score"] is None for g in gs) if played else 0, "games": sorted(gs, key=lambda g: g["home"])})
    off = d["official"]
    return {"season": d["season"] or season_default(), "teams": names, "standings": standings(d), "matchdays": days, "games": len(d["results"]),
            "official": {"published": off.get("published"), "source": off.get("source") or "FTBB"} if off else None}


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
    """A pasted list, one result per line: `matchday, HOME, AWAY, home score, away score[, date]` (commas, semicolons or tabs). Blank lines and lines starting with # are skipped."""
    rows = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        if len(p) < 5:
            raise ValueError(f"“{line}”: write matchday, home, away, home score, away score")
        rows.append({"matchday": p[0].lstrip("Jj"), "home": p[1], "away": p[2], "home_score": p[3], "away_score": p[4], "date": p[5] if len(p) > 5 else ""})
    return rows


def remove_result(matchday, home, away):
    with _lock:
        d = load()
        n = len(d["results"])
        d["results"] = [r for r in d["results"] if not (r["matchday"] == matchday and {r["home"], r["away"]} == {home, away})]
        _write(d)
    return n - len(d["results"])


def parse_fixtures(text):
    """A pasted calendar, one game per line: `matchday, HOME, AWAY, date[, projected]` (projected = the pairing is assumed, not published)."""
    rows = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in re.split(r"[;,\t]", line)]
        if len(p) < 3:
            raise ValueError(f"“{line}”: write matchday, home, away, date")
        rows.append({"matchday": p[0].lstrip("Jj"), "home": p[1], "away": p[2], "date": p[3] if len(p) > 3 else "", "projected": len(p) > 4 and p[4].lower() in ("1", "true", "yes", "projected")})
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
        d["official"] = {"published": published, "source": source, "rows": out}
        _write(d)
        return len(out)
