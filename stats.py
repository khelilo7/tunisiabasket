"""Aggregation, ratings and MVP logic. Pure functions over the stored game JSON files."""
import difflib
import json
import re
from collections import Counter, defaultdict

import config

config.ensure_data()
GAMES_DIR = config.DATA_DIR / "games"
OFFICIAL_FILE = config.DATA_DIR / "official.json"  # federation results + team names (source of truth)
FIXTURES_FILE = config.DATA_DIR / "fixtures.json"  # optional: the official calendar for later matchdays
PHASE_LEN = 11  # 12 teams, each plays every other team once per phase
MVP_TOP_TEAMS = 4  # the season MVP can only come from the top-N teams in the official standings

# --- Rating model -----------------------------------------------------------
# Game rating uses the FIBA Performance Index Rating (PIR):
#   PTS + REB + AST + STL + BLK + FD  -  missed FG - missed FT - TOV - PF
# (Blocks-against is not recorded per player in these sheets, so it is left out.)
# "Impact" = PIR + WIN_BONUS if the player's team won.
# Game MVP: best impact among the WINNING team's players only (the losing team never gets it).
# Season MVP: best average impact among players of the top-N teams of the official standings.
# Rating (0-99) is a simple linear scale of PIR so that ~0 PIR = 45 and ~20 PIR = 95.
WIN_BONUS = 2
MIN_GAMES_FOR_SEASON_MVP = 3
MIN_MINUTES_FOR_RANKING = 5


def season_of(date: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    return f"{y}-{y+1}" if m >= 8 else f"{y-1}-{y}"


def pir(p: dict) -> int:
    return (p["pts"] + p["reb"] + p["ast"] + p["stl"] + p["blk"] + p["fd"]
            - (p["fga"] - p["fgm"]) - (p["fta"] - p["ftm"]) - p["tov"] - p["pf"])


def rating(value: float) -> int:
    return max(0, min(99, round(45 + 2.5 * value)))


SOURCE_WEIGHT = {"text": 3, "claude": 3, "ocr": 1}  # trust exact text over OCR when names disagree


def _garbled(name: str) -> bool:
    """Some PDFs have overlapping text in headings ('Uunniioonn Ssppoortt...')."""
    low = name.lower()
    pairs = sum(1 for a, b in zip(low, low[1:]) if a == b and a.isalpha())
    singles = sum(1 for t in name.split() if len(t) == 1)
    return pairs >= 4 or singles >= 2


def _fix_codes(raw):
    """OCR can misread a team's short code ('CSS' -> 'ES'). Fix it by matching the team name against
    names/codes seen in exact (text-layer) games."""
    known = defaultdict(Counter)
    for g in raw:
        if g.get("source") in ("text", "claude", None):
            for t in g["teams"]:
                if not _garbled(t["name"]):
                    known[re.sub(r"[^a-z]", "", t["name"].lower())][t["code"]] += 1
    for g in raw:
        if g.get("source") == "ocr":
            for t in g["teams"]:
                m = difflib.get_close_matches(re.sub(r"[^a-z]", "", t["name"].lower()), list(known), 1, 0.85)
                if m:
                    t["code"] = known[m[0]].most_common(1)[0][0]


def load_games():
    raw = []
    for f in sorted(GAMES_DIR.glob("*.json")):
        g = json.loads(f.read_text())
        g["id"] = g.get("id") or f.stem
        raw.append(g)
    _fix_codes(raw)
    games, by_key = [], {}
    for g in raw:
        t1, t2 = sorted(g["teams"], key=lambda t: t["code"])
        key = (t1["code"], t2["code"], t1["points"], t2["points"])  # same game uploaded twice
        prev = by_key.get(key)
        if prev is not None:
            # keep the better copy: exact text > OCR > hand-entered sample; real date over approximate
            rank = lambda x: (SOURCE_WEIGHT.get(x.get("source"), 0), not x.get("date_approx"))
            if rank(g) <= rank(prev):
                continue
            games.remove(prev)
        by_key[key] = g
        games.append(g)
    _canonicalise(games)
    games.sort(key=lambda g: (g["date"], g["id"]))
    return games


def _canonicalise(games):
    """Players are identified by (team, jersey number); spelling is the weighted-majority variant.
    Team names are the majority non-garbled variant per team code."""
    names, tnames = defaultdict(Counter), defaultdict(Counter)
    for g in games:
        w = SOURCE_WEIGHT.get(g.get("source"), 3)
        for t in g["teams"]:
            if not _garbled(t["name"]):
                tnames[t["code"]][t["name"]] += w
            for p in t["players"]:
                if not p.get("dnp"):
                    names[(t["code"], p["number"])][p["name"].title()] += w
    # Same team + same name but different jersey readings -> one player (most common number wins).
    nums = defaultdict(Counter)
    for g in games:
        for t in g["teams"]:
            for p in t["players"]:
                if not p.get("dnp"):
                    c = names.get((t["code"], p["number"]))
                    if c:
                        nums[(t["code"], c.most_common(1)[0][0])][p["number"]] += 1
    for g in games:
        for t in g["teams"]:
            if tnames[t["code"]]:
                t["name"] = tnames[t["code"]].most_common(1)[0][0]
            for p in t["players"]:
                c = names.get((t["code"], p["number"]))
                if c and not p.get("dnp"):
                    p["name"] = c.most_common(1)[0][0]
                    p["pid"] = f"{t['code'].lower()}-{nums[(t['code'], p['name'])].most_common(1)[0][0]}"
                else:
                    p["pid"] = f"{t['code'].lower()}-{p['number']}"


def build_all_games():
    games = load_games()
    official = load_official()
    link_official(games, official)
    return [enrich_game(g) for g in games]


def load_official():
    if OFFICIAL_FILE.exists():
        return json.loads(OFFICIAL_FILE.read_text())
    return {"season": None, "teams": {}, "results": []}


def official_standings(official=None):
    """League table computed from ALL official results (including games without a box score)."""
    o = official or load_official()
    t = {c: {"code": c, "name": n, "j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0} for c, n in o["teams"].items()}
    for r in o["results"]:
        for c, f, a in ((r["home"], r["home_score"], r["away_score"]), (r["away"], r["away_score"], r["home_score"])):
            row = t.setdefault(c, {"code": c, "name": c, "j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0})
            row["j"] += 1
            row["w" if f > a else "l"] += 1
            row["pf"] += f
            row["pa"] += a
    out = list(t.values())
    for r in out:
        r["diff"] = r["pf"] - r["pa"]
        r["pts"] = 2 * r["w"] + r["l"]  # 2 points for a win, 1 for a loss
    out.sort(key=lambda r: (-r["pts"], -r["diff"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def matchday_hint(g):
    """Matchday number from an explicit value (admin) or the Drive folder name ('J5 PHASE ALLER' -> 5,
    'J3 PHASE RETOUR' -> 14: the second phase continues the numbering, 11 matchdays per phase)."""
    if g.get("matchday_no"):
        return int(g["matchday_no"])
    m = re.match(r"\s*J\s*(\d+)(.*)", g.get("matchday") or "", re.I)
    if not m:
        return None
    return int(m.group(1)) + (11 if "RETOUR" in m.group(2).upper() else 0)


def link_official(games, official):
    """Attach each box score to its official result: official score and matchday win, team names are
    the official ones. A box score whose total differs keeps its player stats but is flagged.
    The same two teams meet again in the second phase, so a pair can have several official results:
    pick by matchday hint, then by identical score, then by being the only one left."""
    by_pair = defaultdict(list)
    for r in official["results"]:
        by_pair[frozenset([r["home"], r["away"]])].append(r)
    used = set()
    for g in sorted(games, key=lambda g: matchday_hint(g) is None):  # games with a matchday hint first
        a, b = g["teams"]
        for t in g["teams"]:
            t["box_points"] = t["points"]
            if t["code"] in official["teams"]:
                t["name"] = official["teams"][t["code"]]
        cands = [r for r in by_pair.get(frozenset([a["code"], b["code"]]), []) if id(r) not in used]
        hint = matchday_hint(g)
        box = {t["code"]: t["box_points"] for t in g["teams"]}
        same = [r for r in cands if {r["home"]: r["home_score"], r["away"]: r["away_score"]} == box]
        r = None
        if hint is not None and any(c["matchday"] == hint for c in cands):
            r = next(c for c in cands if c["matchday"] == hint)
        elif len(same) == 1:
            r = same[0]
        elif len(cands) == 1:
            r = cands[0]
        if not r:
            continue
        used.add(id(r))
        exp = {r["home"]: r["home_score"], r["away"]: r["away_score"]}
        g["matchday_no"] = r["matchday"]
        g["matchday"] = f"J{r['matchday']}"
        if box != exp:
            g["score_note"] = "Box score sheet says " + " – ".join(f"{t['code']} {t['box_points']}" for t in g["teams"])
            for t in g["teams"]:
                t["points"] = exp[t["code"]]


def enrich_game(g: dict) -> dict:
    """Add per-player PIR/rating/impact and the game MVP."""
    t1, t2 = g["teams"]
    best = None
    for t, o in ((t1, t2), (t2, t1)):
        t["won"] = t["points"] > o["points"]
        for p in t["players"]:
            if p.get("dnp"):
                continue
            p["pir"] = pir(p)
            p["rating"] = rating(p["pir"])
            p["impact"] = p["pir"] + (WIN_BONUS if t["won"] else 0)
            if t["won"] and p["min"] >= MIN_MINUTES_FOR_RANKING:  # only the winning team can have the MVP
                if best is None or (p["impact"], p["pts"]) > (best[0]["impact"], best[0]["pts"]):
                    best = (p, t)
    g["mvp"] = ({"player_id": best[0]["pid"], "name": best[0]["name"], "team": best[1]["code"],
                 "pir": best[0]["pir"], "pts": best[0]["pts"], "reb": best[0]["reb"], "ast": best[0]["ast"]}
                if best else None)
    return g


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def build(season=None):
    """Return (games, players) for a season (default: the latest one)."""
    all_games = build_all_games()
    seasons = sorted({season_of(g["date"]) for g in all_games}, reverse=True)
    if not season and seasons:
        season = seasons[0]
    games = [g for g in all_games if season_of(g["date"]) == season]

    log = defaultdict(list)
    meta = {}
    for g in games:
        for t in g["teams"]:
            opp = next(x for x in g["teams"] if x is not t)
            for p in t["players"]:
                i = p["pid"]
                meta.setdefault(i, {"id": i, "name": p["name"].title(), "teams": [], "numbers": set()})
                if t["code"] not in meta[i]["teams"]:
                    meta[i]["teams"].append(t["code"])
                meta[i]["team"] = t["code"]
                meta[i]["number"] = p["number"]
                if p.get("dnp"):
                    continue
                row = dict(p)
                row.update(game_id=g["id"], date=g["date"], matchday=g.get("matchday"), team=t["code"],
                           opp=opp["code"], score=f'{t["points"]}-{opp["points"]}', won=t["won"],
                           is_mvp=bool(g["mvp"] and g["mvp"]["player_id"] == i))
                log[i].append(row)

    players = []
    for i, rows in log.items():
        n = len(rows)
        tot = lambda k: sum(r[k] for r in rows)
        fga, fta = tot("fga"), tot("fta")
        pts = tot("pts")
        players.append({
            **{k: v for k, v in meta[i].items() if k != "numbers"},
            "gp": n,
            "min": _avg([r["min"] for r in rows]),
            "pts": _avg([r["pts"] for r in rows]),
            "reb": _avg([r["reb"] for r in rows]),
            "ast": _avg([r["ast"] for r in rows]),
            "stl": _avg([r["stl"] for r in rows]),
            "blk": _avg([r["blk"] for r in rows]),
            "tov": _avg([r["tov"] for r in rows]),
            "pf": _avg([r["pf"] for r in rows]),
            "pm": _avg([r["pm"] for r in rows]),
            "fg_pct": round(100 * tot("fgm") / tot("fga"), 1) if tot("fga") else 0,
            "p3_pct": round(100 * tot("p3m") / tot("p3a"), 1) if tot("p3a") else 0,
            "ft_pct": round(100 * tot("ftm") / fta, 1) if fta else 0,
            "ts_pct": round(100 * pts / (2 * (fga + 0.44 * fta)), 1) if (fga + fta) else 0,
            "pir": _avg([r["pir"] for r in rows]),
            "impact": _avg([r["impact"] for r in rows]),
            "wins": sum(r["won"] for r in rows),
            "mvp_games": sum(r["is_mvp"] for r in rows),
            "totals": {k: tot(k) for k in ("pts", "reb", "ast", "stl", "blk", "tov")},
            "rating": rating(_avg([r["pir"] for r in rows])),
            "log": sorted(rows, key=lambda r: (r["date"], r["game_id"])),
        })
    # Ranking: need enough games (or all games if the season is still short).
    max_gp = max((p["gp"] for p in players), default=0)
    need = min(MIN_GAMES_FOR_SEASON_MVP, max_gp)
    for p in players:
        p["qualified"] = p["gp"] >= need and p["min"] >= MIN_MINUTES_FOR_RANKING
    official = load_official()
    table = official_standings(official) if official.get("season") == season else []
    rank = {r["code"]: r["rank"] for r in table}
    top = {r["code"] for r in table[:MVP_TOP_TEAMS]}
    for p in players:
        p["team_rank"] = rank.get(p["team"])
        # MVP pool: enough games AND plays for a top-N team (if no official table, everyone is eligible)
        p["mvp_eligible"] = p["qualified"] and (not table or p["team"] in top)
    players.sort(key=lambda p: (p["mvp_eligible"], p["qualified"], p["impact"], p["pts"]), reverse=True)
    return {"season": season, "seasons": seasons, "games": games, "players": players,
            "standings": table, "top_teams": sorted(top, key=lambda c: rank[c]) if table else []}


def box_counts(games):
    """How many box scores we have per team (the official table covers every game)."""
    c = Counter()
    for g in games:
        for t in g["teams"]:
            c[t["code"]] += 1
    return c


# --- Planning (calendar) -----------------------------------------------------
def planning(official=None):
    """Matchdays after phase 1. If data/fixtures.json exists it is the official calendar; otherwise the
    calendar is PROJECTED as the mirror of phase 1 (same order, home/away swapped), the usual double
    round-robin. Played games (official results for later matchdays) replace their fixture."""
    o = official or load_official()
    projected = not FIXTURES_FILE.exists()
    if projected:
        base = [{"matchday": r["matchday"] + PHASE_LEN, "home": r["away"], "away": r["home"]}
                for r in o["results"] if r["matchday"] <= PHASE_LEN]
    else:
        base = json.loads(FIXTURES_FILE.read_text())["fixtures"]
    played = {(r["matchday"], frozenset([r["home"], r["away"]])): r for r in o["results"] if r["matchday"] > PHASE_LEN}
    by_md = defaultdict(list)
    seen = set()
    for f in base:
        key = (f["matchday"], frozenset([f["home"], f["away"]]))
        r = played.get(key)
        seen.add(key)
        by_md[f["matchday"]].append({
            "home": r["home"] if r else f["home"], "away": r["away"] if r else f["away"],
            "played": bool(r), "home_score": r["home_score"] if r else None, "away_score": r["away_score"] if r else None})
    for key, r in played.items():  # results for games that were not in the calendar
        if key not in seen:
            by_md[r["matchday"]].append({"home": r["home"], "away": r["away"], "played": True,
                                         "home_score": r["home_score"], "away_score": r["away_score"]})
    return {"projected": projected, "teams": o["teams"],
            "matchdays": [{"matchday": md, "games": sorted(gs, key=lambda g: g["home"])} for md, gs in sorted(by_md.items())]}


def team_view(code, season=None):
    """Everything for one team page: standing, match history (with box-score links), upcoming games, players."""
    d = build(season)
    o = load_official()
    if code not in o["teams"]:
        return None
    gid = {}
    for g in d["games"]:
        if g.get("matchday_no"):
            gid[(g["matchday_no"], frozenset(t["code"] for t in g["teams"]))] = g["id"]
    results = []
    for r in sorted(o["results"], key=lambda r: r["matchday"]):
        if code not in (r["home"], r["away"]):
            continue
        home = r["home"] == code
        pf, pa = (r["home_score"], r["away_score"]) if home else (r["away_score"], r["home_score"])
        opp = r["away"] if home else r["home"]
        results.append({"matchday": r["matchday"], "opp": opp, "opp_name": o["teams"][opp], "home": home,
                        "pf": pf, "pa": pa, "won": pf > pa,
                        "game_id": gid.get((r["matchday"], frozenset([r["home"], r["away"]])))})
    plan = planning(o)
    upcoming = []
    for md in plan["matchdays"]:
        for g in md["games"]:
            if code in (g["home"], g["away"]) and not g["played"]:
                home = g["home"] == code
                opp = g["away"] if home else g["home"]
                upcoming.append({"matchday": md["matchday"], "opp": opp, "opp_name": o["teams"][opp], "home": home})
    row = next((r for r in d["standings"] if r["code"] == code), None)
    return {"code": code, "name": o["teams"][code], "standing": row, "results": results, "upcoming": upcoming,
            "projected": plan["projected"], "top_teams": d["top_teams"],
            "players": [{k: v for k, v in p.items() if k != "log"} for p in d["players"] if p["team"] == code]}
