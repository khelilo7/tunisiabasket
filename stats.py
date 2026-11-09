"""Aggregation, ratings and MVP logic. Pure functions over the stored game JSON files."""
import bisect
import difflib
import json
import math
import re
from collections import Counter, defaultdict

import config

config.ensure_data()
GAMES_DIR = config.DATA_DIR / "games"
OFFICIAL_FILE = config.DATA_DIR / "official.json"  # federation results + team names (source of truth)
FIXTURES_FILE = config.DATA_DIR / "fixtures.json"  # optional: the official calendar for later matchdays
BIOS_FILE = config.DATA_DIR / "players_info.json"  # optional corrections to assets/players_info.json
ROSTER_FILE = config.DATA_DIR / "roster.json"  # admin roster changes: added / hidden players, transfers, renames
POSITIONS_FILE = config.DATA_DIR / "positions.json"  # manual position corrections: {"<player id>": "PG"}
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
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
# Qualification for rankings (MVP race and league leaders), as in the NBA: the player must have played at least 70% of
# the games his team(s) have played (the NBA asks 58 of 82 = 70.7%), and not be a token appearance (minutes per game).
QUALIFY_SHARE = 0.7
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


def _unnamed(name):
    """The federation prints XX (or X X, ?) for a player whose name was not entered: no identity to build a profile on."""
    return not re.sub(r"[X\s.?_-]", "", (name or "").upper())


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
                if not p.get("dnp") and not _unnamed(p["name"]):
                    names[(t["code"], p["number"])][p["name"].title()] += w
    # Same team + same name but different jersey readings -> one player (most common number wins).
    nums = defaultdict(Counter)
    for g in games:
        for t in g["teams"]:
            for p in t["players"]:
                if not p.get("dnp") and not _unnamed(p["name"]):
                    c = names.get((t["code"], p["number"]))
                    if c:
                        nums[(t["code"], c.most_common(1)[0][0])][p["number"]] += 1
    for g in games:
        for t in g["teams"]:
            if tnames[t["code"]]:
                t["name"] = tnames[t["code"]].most_common(1)[0][0]
            for p in t["players"]:
                c = names.get((t["code"], p["number"]))
                if _unnamed(p["name"]):
                    p["pid"], p["unnamed"] = f"{t['code'].lower()}-x{p['number']}", True     # counted in the box score and the team, but no profile (nobody to credit)
                elif c and not p.get("dnp"):
                    p["name"] = c.most_common(1)[0][0]
                    p["pid"] = f"{t['code'].lower()}-{nums[(t['code'], p['name'])].most_common(1)[0][0]}"
                else:
                    # A player listed as "did not play" under a mistyped jersey number is still the player we know by that name on this team:
                    # without this, one misprinted number creates a second profile (and borrows the name of the real owner of that number).
                    known = nums.get((t["code"], p["name"].title()))
                    p["pid"] = f"{t['code'].lower()}-{known.most_common(1)[0][0] if known else p['number']}"
    alias = _pid_alias()
    if alias:
        for g in games:
            for t in g["teams"]:
                for p in t["players"]:
                    p["pid"] = alias.get(p["pid"], p["pid"])


def _pid_alias():
    """{alias id: player id}. A transfer marked by the admin says "the player now called jsk-9 is the one we knew as ca-24": same person, one profile.
    Merges say one person was printed under several numbers or spellings."""
    ro = load_roster()
    alias = {t["alias"]: t["id"] for t in ro["transfers"] if t.get("alias") and t["alias"] != t["id"]}
    alias.update({a: i for a, i in ro["merges"].items() if a != i})
    return alias


# --- One-team box scores ------------------------------------------------------------------------------------------
# Sometimes all we have is a hand-kept sheet for ONE team (no minutes, turnovers, fouls, +/-, and nothing for the opponent). Such a game is stored in
# assets/partial_games.json (ships with the code; data/partial_games.json adds to it). It is NOT a box score of the site: it never enters
# build()["games"], so standings, team averages, the home page, the MVP race and the fan vote are exactly what they were. It only adds ONE row to the game log of
# each listed player, where every stat the sheet does not give is None (never 0), and every average is taken over the games where the stat is known.
PARTIAL_FILES = (config.ASSETS_DIR / "partial_games.json", config.DATA_DIR / "partial_games.json")
PARTIAL_UNKNOWN = ("min", "tov", "pf", "fd", "pm", "pir", "rating", "impact")


def partial_games(games):
    """The one-team games of the sheet files, linked to the official result (score, winner) and to the players we already know (same pid as in the
    full box scores). A game with no official result, or a team that is not in it, is ignored. `games` = the canonical full games (pids set)."""
    raw = []
    for path in PARTIAL_FILES:
        try:
            raw += json.loads(path.read_text()).get("games") or []
        except (OSError, ValueError, AttributeError):
            continue
    if not raw:
        return []
    official = load_official()
    ident, names = defaultdict(Counter), {}
    for g in games:
        for t in g["teams"]:
            for p in t["players"]:
                if p.get("pid") and not p.get("dnp") and not p.get("unnamed"):
                    ident[(t["code"], p["number"])][p["pid"]] += 1
                    names[p["pid"]] = p["name"]
    alias, out, seen = _pid_alias(), [], set()
    for raw_g in raw:
        if raw_g.get("id") in seen:
            continue
        seen.add(raw_g.get("id"))
        r = next((r for r in official["results"] if r["matchday"] == raw_g.get("matchday") and {r["home"], r["away"]} == {raw_g.get("home"), raw_g.get("away")}), None)
        rec = raw_g.get("recorded")
        if not r or rec not in (r["home"], r["away"]) or not raw_g.get("date"):
            continue
        pair = frozenset([r["home"], r["away"]])
        if any(matchday_hint(g) == r["matchday"] and frozenset(t["code"] for t in g["teams"]) == pair for g in games):
            continue                                                  # the real box score of this game arrived: it replaces the sheet (no double counting)
        score = {r["home"]: r["home_score"], r["away"]: r["away_score"]}
        teams = []
        for code in (r["home"], r["away"]):
            players = []
            if code == rec:
                for p in raw_g.get("players") or []:
                    pid = ident[(code, p["number"])].most_common(1)[0][0] if ident.get((code, p["number"])) else f"{code.lower()}-{p['number']}"
                    pid = alias.get(pid, pid)
                    row = {"number": p["number"], "name": names.get(pid) or p["name"], "pid": pid, "dnp": False, "starter": False, "partial": True,
                           **{k: p.get(k, 0) for k in ("pts", "fgm", "fga", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk")},
                           **{k: None for k in PARTIAL_UNKNOWN}}
                    row["reb"], row["p2m"], row["p2a"] = row["oreb"] + row["dreb"], row["fgm"] - row["p3m"], row["fga"] - row["p3a"]
                    players.append(row)
            teams.append({"code": code, "name": official["teams"].get(code, code), "points": score[code], "box_points": score[code],
                          "won": score[code] > score[r["away"] if code == r["home"] else r["home"]], "players": players, "recorded": code == rec})
        out.append({"id": raw_g["id"], "partial": True, "date": raw_g["date"], "date_approx": bool(raw_g.get("date_approx")), "competition": raw_g.get("competition"),
                    "matchday_no": r["matchday"], "matchday": f"J{r['matchday']}", "mvp": None, "note": raw_g.get("note"), "source": raw_g.get("source"),
                    "recorded": rec, "teams": teams})
    return out


def partial_game(gid):
    """The API view of one one-team game (or None)."""
    return next((g for g in partial_games(load_games()) if g["id"] == gid), None)


SCHEDULE_FILE = config.DATA_DIR / "schedule.json"     # per game: {"12:CA-ESG": {"time": "18:30", "date": "2026-11-11", "featured": 1}} (admin)
ROSTER_BASE = config.ASSETS_DIR / "roster.json"      # roster facts that ship with the code (same shape as data/roster.json, plus 'merges')


def _roster_raw(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def load_roster(include_base=True):
    """{'added': [{id,name,team,number,pos}], 'hidden': [ids], 'transfers': [{id,from,to,number,alias,date,note}], 'renames': {id: name},
    'merges': {alias id: player id}}. The admin's file (data/roster.json) comes on top of assets/roster.json; the admin only ever writes its own
    (include_base=False), so what ships with the code can never be copied into, or undone from, the data folder."""
    base, raw = (_roster_raw(ROSTER_BASE) if include_base else {}), _roster_raw(ROSTER_FILE)
    seen, transfers = set(), []
    for t in [*(base.get("transfers") or []), *(raw.get("transfers") or [])]:
        k = (t.get("id"), t.get("to"))
        if k not in seen:                                  # the same transfer in both files counts once
            seen.add(k)
            transfers.append(t)
    return {"added": [*(base.get("added") or []), *(raw.get("added") or [])], "hidden": sorted({*(base.get("hidden") or []), *(raw.get("hidden") or [])}),
            "transfers": transfers, "renames": {**(base.get("renames") or {}), **(raw.get("renames") or {})},
            "merges": {**(base.get("merges") or {}), **(raw.get("merges") or {})}}


def blank_player(a: dict) -> dict:
    """A rostered player with no box score yet (new signing): all statistics zero, same fields as a played one."""
    z = 0.0
    return {"id": a["id"], "name": a["name"], "teams": [a["team"]], "team": a["team"], "number": a["number"], "gp": 0,
            **{k: z for k in ("min", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "oreb", "dreb", "fd", "fgm", "fga", "p3m", "p3a", "ftm", "fta",
                              "pm", "fg_pct", "p3_pct", "ft_pct", "ts_pct", "pir", "impact", "total_min", "reb36", "ast36", "blk36", "stl36", "p3_share")},
            "wins": 0, "mvp_games": 0, "totals": {k: 0 for k in ("pts", "reb", "ast", "stl", "blk", "tov")},
            "rating": rating(0.0), "log": [], "added": True}


def apply_roster(players: list, keep_hidden: bool = False) -> list:
    """The admin's roster changes on top of what the box scores say."""
    ro = load_roster()
    byid = {p["id"]: p for p in players}
    for a in ro["added"]:
        if a["id"] not in byid:                       # once the player has a box score the real data takes over
            p = blank_player(a)
            players.append(p)
            byid[p["id"]] = p
    for tr in ro["transfers"]:
        p = byid.get(tr["id"])
        if not p:
            continue
        p.setdefault("transfers", []).append({k: tr.get(k) for k in ("from", "to", "number", "date", "note")})
        if tr["to"] not in p["teams"]:                # no game for the new club yet: show him there already
            p["teams"] = [*p["teams"], tr["to"]]
            p["team"], p["number"] = tr["to"], tr.get("number") or p["number"]
    for pid, name in ro["renames"].items():
        if pid in byid:
            byid[pid]["name"] = name
    hidden = set(ro["hidden"])
    if keep_hidden:
        for p in players:
            p["hidden"] = p["id"] in hidden
        return players
    return [p for p in players if p["id"] not in hidden]


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
            if t["won"] and not p.get("unnamed") and p["min"] >= MIN_MINUTES_FOR_RANKING:  # only the winning team can have the MVP
                if best is None or (p["impact"], p["pts"]) > (best[0]["impact"], best[0]["pts"]):
                    best = (p, t)
    g["mvp"] = ({"player_id": best[0]["pid"], "name": best[0]["name"], "team": best[1]["code"],
                 "pir": best[0]["pir"], "pts": best[0]["pts"], "reb": best[0]["reb"], "ast": best[0]["ast"]}
                if best else None)
    return g


def _per36(rows, key):
    rows = [r for r in rows if r.get("min") is not None]      # a one-team sheet has no minutes: it cannot say what a player does per 36
    m = sum(r["min"] for r in rows)
    return round(36 * sum(r[key] for r in rows) / m, 2) if m else 0.0


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def build(season=None, keep_hidden=False):
    """Return (games, players) for a season (default: the latest one)."""
    all_games = build_all_games()
    seasons = sorted({season_of(g["date"]) for g in all_games}, reverse=True)
    if not season and seasons:
        season = seasons[0]
    games = [g for g in all_games if season_of(g["date"]) == season]

    partials = [g for g in partial_games(all_games) if season_of(g["date"]) == season]
    log = defaultdict(list)
    meta = {}
    for g in sorted([*games, *partials], key=lambda g: (g["date"], g["id"])):
        for t in g["teams"]:
            opp = next(x for x in g["teams"] if x is not t)
            for p in t["players"]:
                if p.get("unnamed"):
                    continue
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
        # Every statistic is taken over the games where it is KNOWN: a one-team sheet counts for points, rebounds... but never as 0 minutes, 0 turnovers or a 0 rating.
        known = lambda k: [r[k] for r in rows if r.get(k) is not None]
        tot = lambda k: sum(known(k))
        avg = lambda k: _avg(known(k))
        full = [r for r in rows if r.get("min") is not None]           # the games with a complete box score
        fga, fta = tot("fga"), tot("fta")
        pts = tot("pts")
        players.append({
            **{k: v for k, v in meta[i].items() if k != "numbers"},
            "gp": n,
            "min": avg("min"),
            "pts": avg("pts"),
            "reb": avg("reb"),
            "ast": avg("ast"),
            "stl": avg("stl"),
            "blk": avg("blk"),
            "tov": avg("tov"),
            "pf": avg("pf"),
            **{k: avg(k) for k in ("oreb", "dreb", "fd", "fgm", "fga", "p3m", "p3a", "ftm", "fta")},
            "pm": avg("pm"),
            "fg_pct": round(100 * tot("fgm") / tot("fga"), 1) if tot("fga") else 0,
            "p3_pct": round(100 * tot("p3m") / tot("p3a"), 1) if tot("p3a") else 0,
            "ft_pct": round(100 * tot("ftm") / fta, 1) if fta else 0,
            "ts_pct": round(100 * pts / (2 * (fga + 0.44 * fta)), 1) if (fga + fta) else 0,
            "pir": avg("pir"),
            "impact": avg("impact"),
            "wins": sum(r["won"] for r in rows),
            "mvp_games": sum(r["is_mvp"] for r in rows),
            "totals": {k: tot(k) for k in ("pts", "reb", "ast", "stl", "blk", "tov")},
            "total_min": round(tot("min"), 1),
            "reb36": _per36(rows, "reb"), "ast36": _per36(rows, "ast"), "blk36": _per36(rows, "blk"),
            "stl36": _per36(rows, "stl"),
            "p3_share": round(sum(r["p3a"] for r in full) / sum(r["fga"] for r in full), 3) if sum(r["fga"] for r in full) else 0.0,
            "rating": rating(avg("pir")),
            "log": sorted(rows, key=lambda r: (r["date"], r["game_id"])),
        })
    players = apply_roster(players, keep_hidden)
    # Ranking: need enough games (or all games if the season is still short).
    # Games a team has really played come from the official table (box scores may be missing for some games).
    official = load_official()
    table = official_standings(official) if official.get("season") == season else []
    team_games = Counter(t["code"] for g in games for t in g["teams"])
    for r in table:
        team_games[r["code"]] = max(team_games[r["code"]], r["j"])
    for p in players:
        avail = sum(team_games[c] for c in p["teams"])
        p["games_needed"] = max(1, math.ceil(QUALIFY_SHARE * avail))
        p["qualified"] = p["gp"] >= p["games_needed"] and p["min"] >= MIN_MINUTES_FOR_RANKING
    assign_positions(players)
    attach_bios(players)
    rank = {r["code"]: r["rank"] for r in table}
    top = {r["code"] for r in table[:MVP_TOP_TEAMS]}
    for p in players:
        p["team_rank"] = rank.get(p["team"])
        # MVP pool: enough games AND plays for a top-N team (if no official table, everyone is eligible)
        p["mvp_eligible"] = p["qualified"] and (not table or p["team"] in top)
    players.sort(key=lambda p: (p["mvp_eligible"], p["qualified"], p["impact"], p["pts"]), reverse=True)
    return {"season": season, "seasons": seasons, "games": games, "partials": partials, "players": players,
            "standings": table, "top_teams": sorted(top, key=lambda c: rank[c]) if table else []}


def box_counts(games):
    """How many box scores we have per team (the official table covers every game)."""
    c = Counter()
    for g in games:
        for t in g["teams"]:
            c[t["code"]] += 1
    return c


# --- Planning (calendar) -----------------------------------------------------
def load_calendar() -> dict:
    """{matchday number: 'YYYY-MM-DD'} from assets/calendar.json, single dates overridden by data/calendar.json."""
    out = {}
    for path in (config.ASSETS_DIR / "calendar.json", config.DATA_DIR / "calendar.json"):
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        out.update({int(k): v for k, v in raw.items() if str(k).isdigit() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v))})
    return out


def _schedule():
    try:
        return json.loads(SCHEDULE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _sched_fields(md, g, sched):
    """key, kick-off time, own date and featured rank of a game (the admin's schedule overlay)."""
    key = f"{md}:{g['home']}-{g['away']}"
    s = sched.get(key) or sched.get(f"{md}:{g['away']}-{g['home']}") or {}
    return {"key": key, "time": s.get("time"), "game_date": s.get("date"), "featured": s.get("featured")}


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
    sched = _schedule()
    for f in base:
        key = (f["matchday"], frozenset([f["home"], f["away"]]))
        r = played.get(key)
        seen.add(key)
        by_md[f["matchday"]].append({
            "home": r["home"] if r else f["home"], "away": r["away"] if r else f["away"],
            "played": bool(r), "home_score": r["home_score"] if r else None, "away_score": r["away_score"] if r else None})
        by_md[f["matchday"]][-1].update(_sched_fields(f["matchday"], by_md[f["matchday"]][-1], sched))
    for key, r in played.items():  # results for games that were not in the calendar
        if key not in seen:
            by_md[r["matchday"]].append({"home": r["home"], "away": r["away"], "played": True,
                                         "home_score": r["home_score"], "away_score": r["away_score"]})
            by_md[r["matchday"]][-1].update(_sched_fields(r["matchday"], by_md[r["matchday"]][-1], sched))
    return {"projected": projected, "teams": o["teams"],
            "matchdays": [{"matchday": md, "date": load_calendar().get(md), "games": sorted(gs, key=lambda g: g["home"])} for md, gs in sorted(by_md.items())]}


def team_stats(season=None):
    """One row per team for comparisons: official record and scoring, plus per-game averages from the box scores we have."""
    d = build(season)
    acc = defaultdict(lambda: Counter())
    for g in d["games"]:
        for t in g["teams"]:
            c = acc[t["code"]]
            c["n"] += 1
            for p in t["players"]:
                if not p.get("dnp"):
                    for k in ("fgm", "fga", "p3m", "p3a", "ftm", "fta", "reb", "ast", "stl", "blk", "tov", "oreb", "fd"):
                        c[k] += p[k]
    rows = []
    for r in d["standings"]:
        c, n = acc[r["code"]], acc[r["code"]]["n"]
        per = lambda k: round(c[k] / n, 1) if n else 0.0
        pct = lambda m, a: round(100 * c[m] / c[a], 1) if c[a] else 0.0
        top = max((p for p in d["players"] if p["team"] == r["code"] and p["gp"]), key=lambda p: p["pts"], default=None)
        rows.append({"code": r["code"], "name": r["name"], "rank": r["rank"], "gp": r["j"], "box": n, "w": r["w"], "l": r["l"],
                     "ppg": round(r["pf"] / r["j"], 1) if r["j"] else 0.0, "opp_ppg": round(r["pa"] / r["j"], 1) if r["j"] else 0.0,
                     "diff_pg": round(r["diff"] / r["j"], 1) if r["j"] else 0.0,
                     "fg_pct": pct("fgm", "fga"), "p3_pct": pct("p3m", "p3a"), "ft_pct": pct("ftm", "fta"),
                     "reb": per("reb"), "ast": per("ast"), "stl": per("stl"), "blk": per("blk"), "tov": per("tov"),
                     "top_scorer": {"name": top["name"], "pts": top["pts"]} if top else None})
    return {"season": d["season"], "teams": rows}


def matchup(home, away, season=None):
    """Everything to compare two teams before they meet, from the games played so far."""
    o = load_official()
    if home not in o["teams"] or away not in o["teams"] or home == away:
        return None
    ts = {r["code"]: r for r in team_stats(season)["teams"]}
    d = build(season)

    def form(code):
        rs = [r for r in sorted(o["results"], key=lambda r: r["matchday"]) if code in (r["home"], r["away"])][-5:]
        return [{"matchday": r["matchday"], "won": (r["home_score"] > r["away_score"]) == (r["home"] == code),
                 "opp": r["away"] if r["home"] == code else r["home"]} for r in rs]

    def key_players(code):
        ps = sorted((p for p in d["players"] if p["team"] == code and p["gp"]), key=lambda p: (p["pts"], p["pir"]), reverse=True)[:3]
        return [{k: p[k] for k in ("id", "name", "number", "pts", "reb", "ast", "pir", "gp")} for p in ps]

    meetings = [{"matchday": r["matchday"], "home": r["home"], "away": r["away"], "home_score": r["home_score"], "away_score": r["away_score"]}
                for r in sorted(o["results"], key=lambda r: r["matchday"]) if {r["home"], r["away"]} == {home, away}]
    cal = load_calendar()
    nxt = next((m for m in planning(o)["matchdays"] for g in m["games"] if not g["played"] and {g["home"], g["away"]} == {home, away}), None)
    return {"home": ts.get(home), "away": ts.get(away), "meetings": meetings, "form": {home: form(home), away: form(away)},
            "players": {home: key_players(home), away: key_players(away)},
            "next": {"matchday": nxt["matchday"], "date": cal.get(nxt["matchday"])} if nxt else None}


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
    for g in d.get("partials", []):          # a one-team sheet has its own match page; a full box score of the same game wins
        gid.setdefault((g["matchday_no"], frozenset(t["code"] for t in g["teams"])), g["id"])
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
    team_players = [p for p in d["players"] if p["team"] == code]
    return {"code": code, "name": o["teams"][code], "standing": row, "results": results, "upcoming": upcoming,
            "lineup": team_lineup(team_players),
            "projected": plan["projected"], "top_teams": d["top_teams"],
            "players": [{k: v for k, v in p.items() if k != "log"} for p in d["players"] if p["team"] == code]}


# --- Positions and lineups ------------------------------------------------------
# The box scores do not say who plays where, so positions are INFERRED from how a player plays: big men rebound
# and block, guards pass, steal and shoot threes. The result is a number from 1 (point guard) to 5 (center) =
# the player's percentile among all regular players on the "bigness" score. A manual correction in
# data/positions.json (edited in the admin tool) always wins.
def load_positions():
    try:
        return json.loads(POSITIONS_FILE.read_text())
    except (OSError, ValueError):
        return {}


# Category leaders for the home page: the top three players of each statistic among players with enough games.
# (key, value taken from the player's averages or computed from the game log, minimum shot attempts per game if any)
LEADER_STATS = ("pts", "reb", "ast", "stl", "blk", "p3m", "fg_pct", "pir")


def leaders(players, n=10):
    """Per category the best n qualified players (value = per-game average, or a percentage)."""
    pool = [p for p in players if p["qualified"]]
    out = []
    for key in LEADER_STATS:
        rows = [p for p in pool if key != "fg_pct" or p["fga"] >= 4]      # shooting % only means something with volume
        rows.sort(key=lambda p: (p[key], p["pir"]), reverse=True)
        out.append({"key": key, "top": [{"id": p["id"], "name": p["name"], "team": p["team"], "number": p["number"],
                                         "gp": p["gp"], "rating": p["rating"], "value": p[key]} for p in rows[:n]]})
    return out


def load_bios():
    """Profiles (height cm, weight kg, birth date) from assets/players_info.json, overridden per player by data/players_info.json."""
    out = {}
    for path in (config.ASSETS_DIR / "players_info.json", BIOS_FILE):
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for pid, info in raw.items():
            if not pid.startswith("_") and isinstance(info, dict):
                out[pid] = {**out.get(pid, {}), **info}
    for pid in out:                                  # the admin clears a field by saving null
        out[pid] = {k: v for k, v in out[pid].items() if v is not None}
    return out


def load_photos() -> dict:
    """{player id: image path}: assets/player_photos.json, single entries overridden by data/player_photos.json."""
    out = {}
    for path in (config.ASSETS_DIR / "player_photos.json", config.DATA_DIR / "player_photos.json"):
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        out.update({k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, str) and v.startswith("/")})
    return out


def attach_bios(players):
    """Adds p['bio'] (or None). height may be a [min, max] pair; 'approx' names the estimated fields."""
    bios, photos = load_bios(), load_photos()
    for p in players:
        p["photo"] = photos.get(p["id"])
        b = bios.get(p["id"])
        p["bio"] = {k: b[k] for k in ("height", "weight", "birth", "approx") if k in b} if b else None


def _z(values):
    m = sum(values) / len(values)
    sd = (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5 or 1.0
    return m, sd


def assign_positions(players):
    """Adds pos (PG..C), pos_value (1..5), auto_pos and pos_source ('auto' or 'manual') to every player dict."""
    manual = load_positions()
    ref = [p for p in players if p["total_min"] >= 60] or players
    if not ref:
        return
    feats = ("reb36", "ast36", "blk36", "stl36", "p3_share")
    stat = {k: _z([p[k] for p in ref]) for k in feats}

    def bigness(p):
        z = {k: (p[k] - stat[k][0]) / stat[k][1] for k in feats}
        return z["reb36"] + 0.8 * z["blk36"] - 1.0 * z["ast36"] - 0.5 * z["p3_share"] - 0.3 * z["stl36"]

    ref_scores = sorted(bigness(p) for p in ref)
    for p in players:
        pct = bisect.bisect_left(ref_scores, bigness(p)) / max(1, len(ref_scores) - 1)
        value = 1 + 4 * min(1.0, pct)
        p["auto_pos"] = POSITIONS[min(4, max(0, round(value) - 1))]
        if manual.get(p["id"]) in POSITIONS:
            p["pos"], p["pos_source"] = manual[p["id"]], "manual"
            p["pos_value"] = float(POSITIONS.index(p["pos"]) + 1)
        else:
            p["pos"], p["pos_source"], p["pos_value"] = p["auto_pos"], "auto", round(value, 2)


def arrange(items):
    """Put up to five players on the five court spots: sorted by pos_value, so spots PG..C are each used once.
    Returns the list in spot order, each item gaining 'spot' (the role it fills on the floor)."""
    ordered = sorted(items, key=lambda x: (x["pos_value"], -x.get("total_min", x.get("min", 0))))[:5]
    # with fewer than five players spread them over the spots by value instead of packing the first ones
    n = len(ordered)
    for i, it in enumerate(ordered):
        idx = i if n == 5 else min(4, round((it["pos_value"] - 1)))
        it["spot"] = POSITIONS[idx]
    return ordered


def team_lineup(players):
    """The five most-played players of a team (by total minutes) arranged on the court."""
    top = sorted((p for p in players if p["total_min"] > 0), key=lambda p: -p["total_min"])[:5]
    keys = ("id", "name", "number", "pos", "pos_source", "pos_value", "gp", "total_min", "min", "pts", "reb", "ast",
            "stl", "blk", "tov", "pm", "pir", "rating", "fg_pct", "p3_pct", "ft_pct", "ts_pct")
    return arrange([{k: p[k] for k in keys} for p in top])


def game_lineups(g, pos_by_id):
    """Per team: the starting five arranged on the court, the bench by minutes, and who did not play."""
    out = {}
    for t in g["teams"]:
        rows = []
        for p in t["players"]:
            pos = pos_by_id.get(p.get("pid"), {"pos": "SF", "pos_value": 3.0, "pos_source": "auto"})
            r = {"id": None if p.get("unnamed") else p.get("pid"), "name": p["name"], "number": p["number"], "dnp": bool(p.get("dnp")),
                 "starter": bool(p.get("starter")), "pos": pos["pos"], "pos_value": pos["pos_value"],
                 "pos_source": pos["pos_source"]}
            if not p.get("dnp"):
                fga, p3a = p["fga"], p["p3a"]
                r.update(min=p["min"], pts=p["pts"], reb=p["reb"], oreb=p["oreb"], dreb=p["dreb"], ast=p["ast"],
                         stl=p["stl"], blk=p["blk"], tov=p["tov"], pf=p["pf"], fd=p["fd"], pm=p["pm"], pir=p["pir"],
                         rating=p["rating"], fgm=p["fgm"], fga=fga, p2m=p["p2m"], p2a=p["p2a"], p3m=p["p3m"], p3a=p3a,
                         ftm=p["ftm"], fta=p["fta"],
                         fg_pct=round(100 * p["fgm"] / fga, 1) if fga else 0.0,
                         p3_pct=round(100 * p["p3m"] / p3a, 1) if p3a else 0.0,
                         ts_pct=round(100 * p["pts"] / (2 * (fga + 0.44 * p["fta"])), 1) if (fga + p["fta"]) else 0.0)
            rows.append(r)
        played = [r for r in rows if not r["dnp"]]
        starters = [r for r in played if r["starter"]]
        if len(starters) != 5:  # the sheet did not mark five starters: use the five with most minutes
            starters = sorted(played, key=lambda r: -r["min"])[:5]
        sid = {id(r) for r in starters}
        out[t["code"]] = {"starters": arrange(starters),
                          "bench": sorted((r for r in played if id(r) not in sid), key=lambda r: -r["min"]),
                          "dnp": [r for r in rows if r["dnp"]]}
    return out
