"""Fantasy Pro A (HIDDEN: only when the server runs with FANTASY=1; every route answers 404 otherwise).

A fan picks a squad of 8 Pro A players (3 guards, 3 forwards, 2 centres, at most 3 from one club, within a budget), sets a starting five (at least one guard, one forward
and one centre) and a captain, and scores every matchday from the real box scores:

    points = PTS + 1.2 REB + 1.5 AST + 2 STL + 2 BLK + 0.5 x 3PM
             - 0.75 x missed shots - 0.5 x missed free throws - 1.5 x turnovers - 0.5 x fouls
             + 0.1 x (+/-)                          (what the team did while he was on the court: more minutes, more weight)
             + 3 for a double-double, + 5 more for a triple-double; rounded to 0.1, no floor and no cap
    so an efficient player scores a lot, and a player who misses, loses the ball and fouls through long minutes can end below zero.

* captain x2 (the vice-captain takes the armband if the captain does not play); the Triple Captain chip makes it x3;
* a starter who does not play is replaced by the first bench player who did (bench order);
* chips, once a season each: Triple Captain, Bench Boost (the bench scores too), Wildcard (unlimited free transfers), All-Star (any squad for one matchday, the old one comes back);
* one free transfer per matchday, one more can be saved (two at most), every extra one costs 4 points;
* each matchday a grade: the points against the best the same squad could have scored (best legal five and best captain), and the rank among all players;
* a public ranking and private leagues (a code to share). No account: a player is the device's random id (like the predictions), with a nickname.

The squad saved before a matchday's deadline (its first game, Tunisia time) plays that matchday; later changes are for the next one.
FANTASY_TEST=1 also lets the app save a squad for a matchday already played, to try the game on real results (local testing only).
"""
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import config
import stats

FILE = config.DATA_DIR / "fantasy.json"
TUNIS = timezone(timedelta(hours=1))
BUDGET = 70.0
SQUAD = {"G": 3, "F": 3, "C": 2}
STARTERS = 5
MAX_PER_CLUB = 3
TRANSFER_COST = 4
CHIPS = ("triple_captain", "bench_boost", "wildcard", "all_star")
POS = {"PG": "G", "SG": "G", "G": "G", "SF": "F", "PF": "F", "F": "F", "C": "C"}
_LOCK = threading.Lock()


def enabled():
    return os.environ.get("FANTASY") == "1"


def test_mode():
    return os.environ.get("FANTASY_TEST") == "1"


# ---------------------------------------------------------------- storage
def _load():
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {"entries": {}, "leagues": {}}


def _save(d):
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False))
    os.replace(tmp, FILE)


# ---------------------------------------------------------------- scoring
SCORING = [  # key, weight, label (what the app shows in a breakdown)
    ("pts", 1, "Points"), ("reb", 1.2, "Rebounds"), ("ast", 1.5, "Assists"), ("stl", 2, "Steals"), ("blk", 2, "Blocks"), ("p3m", 0.5, "Three-pointers made"),
    ("missed_fg", -0.75, "Missed shots"), ("missed_ft", -0.5, "Missed free throws"), ("tov", -1.5, "Turnovers"), ("pf", -0.5, "Fouls"), ("pm", 0.1, "Plus-minus"),
]
DOUBLE, TRIPLE = 3, 5


def breakdown(p):
    """[{"key","label","count","points"}] of a box-score line (None when the player did not play): every line of the formula, bonuses last."""
    if p.get("dnp") or not p.get("min"):
        return None
    vals = {**{k: p.get(k) or 0 for k in ("pts", "reb", "ast", "stl", "blk", "p3m", "tov", "pf", "pm")},
            "missed_fg": (p.get("fga") or 0) - (p.get("fgm") or 0), "missed_ft": (p.get("fta") or 0) - (p.get("ftm") or 0)}
    out = [{"key": k, "label": label, "count": vals[k], "points": round(w * vals[k], 2)} for k, w, label in SCORING if vals[k]]
    tens = sum(1 for k in ("pts", "reb", "ast", "stl", "blk") if vals[k] >= 10)
    if tens >= 2:
        out.append({"key": "double_double", "label": "Double-double", "count": 1, "points": DOUBLE})
    if tens >= 3:
        out.append({"key": "triple_double", "label": "Triple-double", "count": 1, "points": TRIPLE})
    return out


def fantasy_points(p):
    """A box-score line -> fantasy points (None when the player did not play). Can be negative; no cap."""
    b = breakdown(p)
    return None if b is None else round(sum(x["points"] for x in b), 1)


def _season_games():
    s = stats.build()["season"]
    return [g for g in stats.build_all_games() if stats.season_of(g["date"]) == s and g.get("matchday_no")]


def matchday_scores(md):
    """{player id: {"pts": fantasy points, "line": {...}, "game": id}} for matchday `md` (box scores only)."""
    out = {}
    for g in _season_games():
        if g["matchday_no"] != md:
            continue
        a, b = g["teams"]
        for t, o in ((a, b), (b, a)):
            for p in t["players"]:
                fp = fantasy_points(p)
                if fp is None:
                    continue
                prev = out.get(p["pid"])
                line = {k: p.get(k) for k in ("pts", "reb", "ast", "stl", "blk", "tov", "p3m", "min", "fgm", "fga", "ftm", "fta", "pf", "pm")}
                out[p["pid"]] = {"pts": round((prev["pts"] if prev else 0) + fp, 1), "line": line, "game": g["id"], "opp": o["code"], "won": t["won"]}
    return out


# ---------------------------------------------------------------- calendar
def _deadline(md):
    dates = [(g.get("game_date") or md["date"], g.get("time")) for g in md["games"]]
    d, t = min(dates)
    hh, mm = (t or "15:00").split(":")[:2]
    return datetime.fromisoformat(d).replace(hour=int(hh), minute=int(mm), tzinfo=TUNIS) - timedelta(minutes=30)


@stats._cached
def calendar():
    """[{"md","deadline","locked","done","games":[...]}] for the whole season: the matchdays already played (official results, dated by their box scores)
    and those of the planning (dates and times the admin set)."""
    now = datetime.now(TUNIS)
    days = {}
    dates = {}
    for g in _season_games():
        dates.setdefault(g["matchday_no"], []).append(g["date"])
    for r in stats.load_official().get("results") or []:
        days.setdefault(r["matchday"], {"matchday": r["matchday"], "date": min(dates.get(r["matchday"]) or ["2000-01-01"]), "games": []})["games"].append(
            {"home": r["home"], "away": r["away"], "home_score": r["home_score"], "away_score": r["away_score"], "played": r.get("home_score") is not None})
    for md in stats.planning()["matchdays"]:
        days[md["matchday"]] = md
    out = []
    for n in sorted(days):
        md = days[n]
        dl = _deadline(md)
        played = sum(1 for g in md["games"] if g["played"])
        out.append({"md": n, "date": md["date"], "deadline": dl.isoformat(), "deadline_ts": int(dl.timestamp()),
                    "locked": now >= dl or played > 0, "done": played == len(md["games"]) and played > 0,
                    "games": [{"home": g["home"], "away": g["away"], "home_score": g.get("home_score"), "away_score": g.get("away_score"), "played": g["played"],
                               "date": g.get("game_date") or md["date"], "time": g.get("time")} for g in md["games"]]})
    return out


def open_md():
    """The matchday the next saved squad plays (None after the last one)."""
    return next((m["md"] for m in calendar() if not m["locked"]), None)


# ---------------------------------------------------------------- player pool
@stats._cached
def pool():
    d = stats.build()
    cal = calendar()
    nxt = next((m for m in cal if not m["locked"]), None)
    games = _season_games()
    per = {}
    for g in sorted(games, key=lambda g: g["date"]):
        for t in g["teams"]:
            for p in t["players"]:
                fp = fantasy_points(p)
                if fp is not None:
                    per.setdefault(p["pid"], []).append(fp)
    ent = _load()["entries"]
    owners = {}
    om = open_md() or 999
    for e in ent.values():
        pick = _effective(e, om)
        for pid in (pick or {}).get("squad", []):
            owners[pid] = owners.get(pid, 0) + 1
    n = max(1, sum(1 for e in ent.values() if e.get("picks")))
    out = []
    for p in d["players"]:
        if p.get("hidden"):
            continue
        pts = per.get(p["id"], [])
        avg = round(sum(pts) / len(pts), 1) if pts else 0.0
        price = max(4.0, min(15.0, round((4 + avg * 0.35) * 2) / 2))      # 4.0 for a newcomer or a player in the red, about 13.5 for 27 points a game; a squad of 8 for 70
        opp = None
        if nxt:
            gm = next((x for x in nxt["games"] if p["team"] in (x["home"], x["away"])), None)
            if gm:
                opp = {"code": gm["away"] if gm["home"] == p["team"] else gm["home"], "home": gm["home"] == p["team"]}
        out.append({"id": p["id"], "name": p["name"], "team": p["team"], "number": p.get("number"), "pos": POS.get(p.get("pos") or "", "F"), "price": price,
                    "avg": avg, "form": round(sum(pts[-3:]) / len(pts[-3:]), 1) if pts else 0.0, "gp": len(pts), "total": round(sum(pts), 1),
                    "last": pts[-1] if pts else None, "pts": p.get("pts"), "reb": p.get("reb"), "ast": p.get("ast"), "min": p.get("min"),
                    "photo": p.get("photo"), "owned": round(100 * owners.get(p["id"], 0) / n, 1), "next": opp})
    return sorted(out, key=lambda x: -x["price"])


# ---------------------------------------------------------------- one entry
def _effective(e, md):
    """The pick that plays matchday `md`: the one saved for it, else the latest earlier one (an All-Star pick only counts for its own matchday)."""
    picks = e.get("picks") or {}
    if str(md) in picks:
        return picks[str(md)]
    earlier = sorted((int(k) for k, v in picks.items() if int(k) < md and v.get("chip") != "all_star"), reverse=True)
    return picks[str(earlier[0])] if earlier else None


def _score_pick(pick, scores):
    squad, starters = pick["squad"], pick["starters"]
    bench = [p for p in squad if p not in starters]
    played = lambda pid: pid in scores  # noqa: E731
    lineup, subs = [], []
    used = set()
    for pid in starters:
        if played(pid):
            lineup.append(pid)
        else:
            sub = next((b for b in bench if b not in used and played(b)), None)
            if sub:
                used.add(sub)
                lineup.append(sub)
                subs.append({"out": pid, "in": sub})
    cap = pick["captain"] if played(pick["captain"]) else (pick.get("vice") if played(pick.get("vice")) else None)
    mult = 3 if pick.get("chip") == "triple_captain" else 2
    counted = lineup + ([b for b in bench if b not in used] if pick.get("chip") == "bench_boost" else [])
    rows, total = [], 0.0
    for pid in squad:
        base = scores.get(pid, {}).get("pts", 0.0)
        m = (mult if pid == cap else 1) if pid in counted else 0
        rows.append({"id": pid, "base": base, "mult": m, "points": round(base * m, 1), "played": played(pid), "starter": pid in starters,
                     "line": scores.get(pid, {}).get("line"), "opp": scores.get(pid, {}).get("opp")})
        total += base * m
    return round(total, 1), rows, subs, cap


def _best_possible(pick, scores, pos, chip=None):
    """The most the same squad could have scored: the best legal five (one guard, one forward, one centre at least) and the best of them as captain."""
    squad = pick["squad"]
    pts = {p: scores.get(p, {}).get("pts", 0.0) for p in squad}
    best = 0.0
    from itertools import combinations
    for five in combinations(squad, STARTERS):
        if {"G", "F", "C"} <= {pos.get(p, "F") for p in five}:
            s = sum(pts[p] for p in five) + max(pts[p] for p in five) * (2 if chip == "triple_captain" else 1)
            if chip == "bench_boost":
                s += sum(pts[p] for p in squad if p not in five)
            best = max(best, s)
    return round(best, 1)


def grade(points, best):
    r = points / best if best else 0
    return "A+" if r >= .95 else "A" if r >= .85 else "B" if r >= .7 else "C" if r >= .55 else "D"


def _history(e, cal, pos):
    """Per matchday played: points, transfers, hits, chip, grade, best possible."""
    out, bank, prev_squad, total = [], 0, None, 0.0
    first = min((int(k) for k in (e.get("picks") or {})), default=None)
    if first is None:
        return out, 0.0, 1
    for m in cal:
        md = m["md"]
        if md < first:
            continue
        pick = _effective(e, md)
        if not pick:
            continue
        free = min(2, 1 + bank)
        moves = len(set(pick["squad"]) - set(prev_squad)) if prev_squad and str(md) in (e.get("picks") or {}) else 0
        chip = pick.get("chip") if str(md) in (e.get("picks") or {}) else None
        hit = 0 if chip in ("wildcard", "all_star") else max(0, moves - free) * TRANSFER_COST
        bank = 0 if moves >= free else min(1, free - moves) if chip not in ("wildcard", "all_star") else bank
        if chip != "all_star":
            prev_squad = pick["squad"]
        elif prev_squad is None:
            prev_squad = pick["squad"]
        if not m["locked"]:
            out.append({"md": md, "upcoming": True, "transfers": moves, "hit": hit, "chip": chip, "free": free})
            break
        scores = matchday_scores(md)
        pts, rows, subs, cap = _score_pick({**pick, "chip": chip}, scores)
        best = _best_possible(pick, scores, pos, chip)
        net = round(pts - hit, 1)
        total += net
        out.append({"md": md, "points": net, "raw": pts, "hit": hit, "transfers": moves, "chip": chip, "captain": cap, "rows": rows, "subs": subs,
                    "best": best, "grade": grade(pts, best) if best else None, "done": m["done"]})
    return out, round(total, 1), (min(2, 1 + bank))


def _pos_map():
    return {p["id"]: p["pos"] for p in pool()}


@stats._cached
def standings_table():
    """Every entry's total and per-matchday points (the ranking)."""
    cal, pos = calendar(), _pos_map()
    rows = []
    for vid, e in _load()["entries"].items():
        hist, total, _ = _history(e, cal, pos)
        rows.append({"vid": vid, "name": e.get("name") or "?", "team": e.get("team_name") or "", "total": total,
                     "md": {h["md"]: h["points"] for h in hist if not h.get("upcoming")}})
    rows.sort(key=lambda r: -r["total"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def me(vid):
    e = _load()["entries"].get(vid)
    cal, pos = calendar(), _pos_map()
    om = open_md()
    if not e:
        return {"entry": None, "open_md": om}
    hist, total, free = _history(e, cal, pos)
    table = standings_table()
    rank = next((r["rank"] for r in table if r["vid"] == vid), None)
    for h in hist:                                                   # the rank of the matchday
        if h.get("upcoming"):
            continue
        day = sorted((r["md"].get(h["md"], 0) for r in table), reverse=True)
        h["rank"] = 1 + sum(1 for x in day if x > h["points"])
        h["of"] = len(day)
        h["avg"] = round(sum(day) / len(day), 1) if day else 0
    cur = _effective(e, om) if om else None
    used = {k: v for k, v in (e.get("chips_used") or {}).items()}
    return {"entry": {"name": e.get("name"), "team_name": e.get("team_name"), "total": total, "rank": rank, "of": len(table), "history": hist,
                      "current": cur, "free_transfers": free, "chips_used": used, "chips_left": [c for c in CHIPS if c not in used], "leagues": leagues_of(vid)},
            "open_md": om}


# ---------------------------------------------------------------- saving
def _clean(s, n):
    return re.sub(r"[\x00-\x1f<>]", "", str(s or "")).strip()[:n]


def validate(squad, starters, captain, vice, players):
    errs = []
    by = {p["id"]: p for p in players}
    if len(squad) != sum(SQUAD.values()) or len(set(squad)) != len(squad) or any(p not in by for p in squad):
        return ["squad: pick 8 different players"]
    for k, n in SQUAD.items():
        if sum(1 for p in squad if by[p]["pos"] == k) != n:
            errs.append(f"squad: {n} {k}")
    clubs = {}
    for p in squad:
        clubs[by[p]["team"]] = clubs.get(by[p]["team"], 0) + 1
    if max(clubs.values()) > MAX_PER_CLUB:
        errs.append(f"club: at most {MAX_PER_CLUB} players from one club")
    if len(starters) != STARTERS or len(set(starters)) != STARTERS or not set(starters) <= set(squad):
        errs.append("starters: 5 players of the squad")
    elif not {"G", "F", "C"} <= {by[p]["pos"] for p in starters}:
        errs.append("starters: at least one guard, one forward and one centre")
    if captain not in starters:
        errs.append("captain: one of the starters")
    if vice and (vice not in starters or vice == captain):
        errs.append("vice: another starter")
    return errs


def save(body):
    vid = _clean(body.get("vid"), 64)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", vid or ""):
        return {"ok": False, "errors": ["vid"]}
    md = open_md()
    if test_mode() and body.get("md"):
        md = int(body["md"])                                         # local testing: play a matchday already played
    if md is None:
        return {"ok": False, "errors": ["season over"]}
    players = pool()
    squad, starters = [str(x) for x in body.get("squad") or []], [str(x) for x in body.get("starters") or []]
    captain, vice, chip = str(body.get("captain") or ""), str(body.get("vice") or ""), body.get("chip") or None
    errs = validate(squad, starters, captain, vice, players)
    price = {p["id"]: p["price"] for p in players}
    cost = round(sum(price.get(p, 0) for p in squad), 1)
    with _LOCK:
        d = _load()
        e = d["entries"].setdefault(vid, {"created": int(time.time()), "picks": {}, "chips_used": {}})
        prev = _effective(e, md)
        keep = set(prev["squad"]) if prev else set()
        # the All-Star chip has no budget; otherwise the squad fits the budget, or costs no more than the squad already held (prices move with form)
        limit = max(BUDGET, round(sum(price.get(p, 0) for p in keep), 1)) if keep and set(squad) == keep else BUDGET
        if chip != "all_star" and cost > limit:
            errs.append(f"budget: {cost} > {BUDGET}")
        if chip and chip not in CHIPS:
            errs.append("chip")
        used = e.get("chips_used") or {}
        if chip and chip in used and used[chip] != md:
            errs.append(f"chip already used on matchday {used[chip]}")
        if errs:
            return {"ok": False, "errors": errs, "cost": cost}
        old_chip = (e["picks"].get(str(md)) or {}).get("chip")
        if old_chip and old_chip != chip:
            used.pop(old_chip, None)
        if chip:
            used[chip] = md
        e["chips_used"] = used
        e["picks"][str(md)] = {"squad": squad, "starters": starters, "captain": captain, "vice": vice or None, "chip": chip, "saved": int(time.time())}
        if body.get("name"):
            e["name"] = _clean(body["name"], 24)
        if body.get("team_name"):
            e["team_name"] = _clean(body["team_name"], 30)
        _save(d)
    stats._CACHE.clear()
    return {"ok": True, "md": md, "cost": cost}


def dream_team(md):
    """The best five of a matchday (one guard, one forward, one centre at least) and its MVP."""
    scores = matchday_scores(md)
    pos = _pos_map()
    by = {p["id"]: p for p in pool()}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1]["pts"])
    five = []
    for need in ("G", "F", "C"):
        pid = next((k for k, v in ranked if pos.get(k) == need and k not in five), None)
        if pid:
            five.append(pid)
    for k, _v in ranked:
        if len(five) == STARTERS:
            break
        if k not in five:
            five.append(k)
    return [{**{x: by.get(k, {}).get(x) for x in ("name", "team", "pos", "photo", "price")}, "id": k, "points": scores[k]["pts"], "line": scores[k]["line"]}
            for k in sorted(five, key=lambda k: -scores[k]["pts"])]


# ---------------------------------------------------------------- leagues
def leagues_of(vid):
    d = _load()
    return [{"code": c, "name": l["name"], "members": len(l["members"])} for c, l in d["leagues"].items() if vid in l["members"]]


def league(body):
    vid = _clean(body.get("vid"), 64)
    with _LOCK:
        d = _load()
        if vid not in d["entries"]:
            return {"ok": False, "errors": ["make a team first"]}
        if body.get("action") == "create":
            code = secrets.token_hex(3).upper()
            d["leagues"][code] = {"name": _clean(body.get("name"), 30) or "League", "owner": vid, "members": [vid], "created": int(time.time())}
        else:
            code = _clean(body.get("code"), 8).upper()
            if code not in d["leagues"]:
                return {"ok": False, "errors": ["unknown code"]}
            if vid not in d["leagues"][code]["members"]:
                d["leagues"][code]["members"].append(vid)
        _save(d)
    stats._CACHE.clear()
    return {"ok": True, "code": code}


def ranking(league_code=None, limit=100):
    rows = standings_table()
    if league_code:
        l = _load()["leagues"].get(league_code.upper())
        if not l:
            return None
        rows = [r for r in rows if r["vid"] in l["members"]]
        rows = [{**r, "rank": i} for i, r in enumerate(rows, 1)]
    return [{k: v for k, v in r.items() if k != "vid"} | {"me_key": r["vid"][-6:]} for r in rows[:limit]]


def config_view():
    cal = calendar()
    return {"budget": BUDGET, "squad": SQUAD, "starters": STARTERS, "max_per_club": MAX_PER_CLUB, "transfer_cost": TRANSFER_COST, "chips": list(CHIPS),
            "scoring": {**{k: w for k, w, _l in SCORING}, "double_double": DOUBLE, "triple_double": TRIPLE},
            "open_md": open_md(), "test": test_mode(), "matchdays": [{k: m[k] for k in ("md", "date", "deadline", "deadline_ts", "locked", "done")} for m in cal]}


def player_view(pid):
    """One player for the fantasy screens: price and averages, and every game of the season with its line and the points each part of it gave."""
    p = next((x for x in pool() if x["id"] == pid), None)
    if not p:
        return None
    games = []
    for g in sorted(_season_games(), key=lambda g: g["date"]):
        a, b = g["teams"]
        for t, o in ((a, b), (b, a)):
            row = next((x for x in t["players"] if x["pid"] == pid), None)
            if not row:
                continue
            br = breakdown(row)
            games.append({"md": g["matchday_no"], "date": g["date"], "game_id": g["id"], "opp": o["code"], "home": g.get("home_team") == t["code"] if g.get("home_team") else None,
                          "score": f'{t["points"]}-{o["points"]}', "won": t["points"] > o["points"], "played": br is not None,
                          "line": {k: row.get(k) for k in ("min", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "fgm", "fga", "p3m", "p3a", "ftm", "fta", "pm")},
                          "fp": round(sum(x["points"] for x in br), 1) if br else None, "breakdown": br or []})
    played = [x for x in games if x["played"]]
    per = {}
    for x in played:
        for c in x["breakdown"]:
            per[c["key"]] = per.get(c["key"], {"key": c["key"], "label": c["label"], "count": 0, "points": 0.0})
            per[c["key"]]["count"] += c["count"]
            per[c["key"]]["points"] += c["points"]
    n = max(1, len(played))
    avg_breakdown = [{**v, "count": round(v["count"] / n, 1), "points": round(v["points"] / n, 1)} for v in per.values()]
    fps = [x["fp"] for x in played]
    return {**p, "games": list(reversed(games)), "avg_breakdown": sorted(avg_breakdown, key=lambda v: -abs(v["points"])),
            "best": max(fps, default=None), "worst": min(fps, default=None), "last": fps[-1] if fps else None,
            "real": {k: round(sum((x["line"].get(k) or 0) for x in played) / n, 1) for k in ("pts", "reb", "ast", "min")}}
