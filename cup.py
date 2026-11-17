"""The Cup (Coupe de Tunisie): clubs of the Pro A and of the Nationale 1 meet in single-leg knockout ties, the winner of each game goes through.

Data lives in `data/cup.json` (kept across deployments and in the backups):

    {"name": "Coupe de Tunisie", "season": "2026-2027", "demo": false,
     "teams": {"XYZ": {"name": "A club of neither league", "league": "other"}},          # only clubs the two leagues do not know
     "rounds": [{"key": "r1", "name": "1/8 de finale", "date": "2026-12-19",
                 "ties": [{"id": "r1-1", "home": "CA", "away": "CAK", "home_score": 81, "away_score": 74, "date": "2026-12-19", "note": ""},
                          {"id": "r2-1", "home": "W:r1-1", "away": "W:r1-2"}]}]}

A side is a club code, "BYE" (the other side goes through without playing) or "W:<tie id>" (the winner of that tie): the whole bracket can be drawn before a single game is played, and
every round fills itself as the results arrive. The league of a club (Pro A / Nationale 1 / other) comes from the two leagues, so the page can show who is who and flag an upset (a club of a lower
division beating a club of a higher one). A game has a winner: scores are never equal.
"""
import json
import re
import threading

import config
import nat1
import stats

FILE = config.DATA_DIR / "cup.json"
LEVEL = {"proa": 3, "nat1": 2, "other": 1}
LEAGUE_NAME = {"proa": "Pro A", "nat1": "Nationale 1", "other": ""}
CODE = re.compile(r"^[A-Z0-9]{2,8}$")
_lock = threading.Lock()


def load():
    try:
        d = json.loads(FILE.read_text())
    except (OSError, ValueError):
        d = {}
    return {"name": str(d.get("name") or "Coupe de Tunisie"), "season": str(d.get("season") or ""), "demo": bool(d.get("demo")),
            "teams": {k: v for k, v in (d.get("teams") or {}).items() if isinstance(v, dict)}, "rounds": [r for r in d.get("rounds") or [] if isinstance(r, dict)]}


def _write(d):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    tmp.replace(FILE)


def known_teams(d=None):
    """{code: {"name", "league"}} of every club that can be drawn: the Pro A, the Nationale 1, then the clubs added for the Cup only."""
    d = d or load()
    out = {}
    for code, name in stats.load_official()["teams"].items():
        out[code] = {"name": name, "league": "proa"}
    for code, name in nat1.load()["teams"].items():
        out.setdefault(code, {"name": name, "league": "nat1"})
    for code, t in d["teams"].items():
        out.setdefault(code, {"name": str(t.get("name") or code), "league": t.get("league") if t.get("league") in LEVEL else "other"})
    return out


def _winner_of(tie, sides):
    """The code that goes through, or None: a BYE passes the other side; otherwise the higher score of a played tie."""
    h, a = sides
    if h == "BYE":
        return a if a not in (None, "BYE") else None
    if a == "BYE":
        return h if h not in (None, "BYE") else None
    if tie.get("home_score") is None or tie.get("away_score") is None or not h or not a:
        return None
    return h if tie["home_score"] > tie["away_score"] else a


def view():
    """The bracket as the page draws it: every round with its ties, each side resolved to a club (or a label like "Winner of 1/8 #3"), the winner, upsets, and the champion."""
    d = load()
    teams = known_teams(d)
    won, label, rounds = {}, {}, []

    def side(ref):
        if ref == "BYE":
            return {"bye": True}
        if isinstance(ref, str) and ref.startswith("W:"):
            tid = ref[2:]
            code = won.get(tid)
            if code:
                return {"code": code, **teams.get(code, {"name": code, "league": "other"})}
            return {"from": tid, "label": label.get(tid, "")}
        if ref in teams:
            return {"code": ref, **teams[ref]}
        return {"code": ref, "name": ref or "", "league": "other"} if ref else {"tbd": True}

    for ri, r in enumerate(d["rounds"]):
        ties = []
        for i, t in enumerate(r.get("ties") or [], 1):
            label[t["id"]] = f"{r.get('name', '')} #{i}"
            home, away = side(t.get("home")), side(t.get("away"))
            code = _winner_of(t, (home.get("code") or ("BYE" if home.get("bye") else None), away.get("code") or ("BYE" if away.get("bye") else None)))
            if code:
                won[t["id"]] = code
            played = t.get("home_score") is not None and t.get("away_score") is not None and "code" in home and "code" in away
            upset = bool(code and played and LEVEL[teams[code]["league"]] < max(LEVEL[teams[x["code"]]["league"]] for x in (home, away) if x.get("code") in teams))
            ties.append({"id": t["id"], "n": i, "home": home, "away": away, "home_score": t.get("home_score"), "away_score": t.get("away_score"), "date": t.get("date") or r.get("date"),
                         "note": t.get("note") or "", "winner": code, "played": played, "bye": bool(home.get("bye") or away.get("bye")), "upset": upset})
        rounds.append({"key": r.get("key") or f"r{ri + 1}", "name": r.get("name") or f"Round {ri + 1}", "date": r.get("date"), "ties": ties,
                       "done": bool(ties) and all(x["winner"] for x in ties)})
    last = rounds[-1] if rounds else None
    champion = None
    if last and len(last["ties"]) == 1 and last["ties"][0]["winner"] and not last["ties"][0]["bye"]:
        c = last["ties"][0]["winner"]
        champion = {"code": c, **teams[c]}
    current = next((i for i, r in enumerate(rounds) if not r["done"]), max(0, len(rounds) - 1))
    played_ties = [t for r in rounds for t in r["ties"] if t["played"]]
    clubs = {}
    for r in rounds:
        for t in r["ties"]:
            for s in (t["home"], t["away"]):
                if s.get("code") and s["code"] in teams:
                    clubs[s["code"]] = teams[s["code"]]["league"]
    by_league = {lg: sum(1 for v in clubs.values() if v == lg) for lg in LEVEL}
    return {"name": d["name"], "season": d["season"], "demo": d["demo"], "rounds": rounds, "current": current, "champion": champion, "upsets": sum(t["upset"] for t in played_ties),
            "games": len(played_ties), "clubs": by_league, "teams": teams}


# ---------------------------------------------------------------- admin
def _int(v, lo=0, hi=250):
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        raise ValueError("a number is needed") from None
    if not lo <= n <= hi:
        raise ValueError(f"{n} is out of range")
    return n


def add_team(code, name, league="other"):
    code, name = str(code or "").strip().upper(), " ".join(str(name or "").split())
    if not CODE.match(code):
        raise ValueError("the code is 2 to 8 letters or digits")
    if not 2 <= len(name) <= 40:
        raise ValueError("the name is 2 to 40 characters")
    with _lock:
        d = load()
        d["teams"][code] = {"name": name, "league": league if league in LEVEL else "other"}
        _write(d)


def set_title(name, season):
    with _lock:
        d = load()
        d["name"] = " ".join(str(name or "").split())[:60] or d["name"]
        if season is not None:
            if season and not re.fullmatch(r"\d{4}-\d{4}", str(season)):
                raise ValueError("the season is written like 2026-2027")
            d["season"] = str(season)
        _write(d)


def draw(round_name, text, date="", demo=False):
    """Draw the FIRST round from a pasted list, one tie per line: `HOME, AWAY[, date]` (AWAY may be BYE), and build every later round empty with winner links, halving each time until
    one tie is left (the final). Replaces the whole bracket. All or nothing."""
    teams = known_teams()
    pairs = []
    for i, line in enumerate(str(text or "").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip().upper() if k < 2 else x.strip() for k, x in enumerate(re.split(r"[;,\t]| - ", line))]
        if len(p) < 2:
            raise ValueError(f"line {i}: write HOME, AWAY")
        for c in p[:2]:
            if c != "BYE" and c not in teams:
                raise ValueError(f"line {i}: unknown club {c}: add it first")
        if p[0] == "BYE":
            p[0], p[1] = p[1], p[0]
        pairs.append(p)
    codes = [c for p in pairs for c in p[:2] if c != "BYE"]
    if len(pairs) < 1 or len(set(codes)) != len(codes):
        raise ValueError("a club can be drawn only once, and at least one tie is needed")
    n = len(pairs)
    if n & (n - 1):
        raise ValueError(f"{n} ties do not make a bracket: use 1, 2, 4, 8, 16 ties (give a BYE to the clubs that wait for the next round)")
    names = {1: "Finale", 2: "Demi-finales", 4: "Quarts de finale", 8: "1/8 de finale", 16: "1/16 de finale", 32: "1/32 de finale"}
    rounds, size, k = [], n, 1
    first = [{"id": f"r{k}-{i}", "home": p[0], "away": p[1], **({"date": p[2]} if len(p) > 2 and p[2] else {})} for i, p in enumerate(pairs, 1)]
    rounds.append({"key": f"r{k}", "name": round_name or names.get(size, f"Round {k}"), "ties": first, **({"date": date} if date else {})})
    while size > 1:
        size //= 2
        k += 1
        ties = [{"id": f"r{k}-{i}", "home": f"W:r{k - 1}-{2 * i - 1}", "away": f"W:r{k - 1}-{2 * i}"} for i in range(1, size + 1)]
        rounds.append({"key": f"r{k}", "name": names.get(size, f"Round {k}"), "ties": ties})
    with _lock:
        d = load()
        d["rounds"] = rounds
        if demo:
            d["demo"] = True
        _write(d)
    return len(rounds)


def set_round(key, name=None, date=None):
    with _lock:
        d = load()
        r = next((x for x in d["rounds"] if x.get("key") == key), None)
        if not r:
            raise ValueError("unknown round")
        if name:
            r["name"] = " ".join(str(name).split())[:40]
        if date is not None:
            if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
                raise ValueError("the date is YYYY-MM-DD")
            r["date"] = date
        _write(d)


def set_result(tie_id, home_score, away_score, date=None, note=None):
    """Record (or, with empty scores, clear) the result of a tie whose two sides are known."""
    with _lock:
        d = load()
        v = view()
        tie = next((t for r in v["rounds"] for t in r["ties"] if t["id"] == tie_id), None)
        raw = next((t for r in d["rounds"] for t in r.get("ties", []) if t["id"] == tie_id), None)
        if not tie or raw is None:
            raise ValueError("unknown tie")
        if home_score in (None, "") and away_score in (None, ""):
            raw.pop("home_score", None), raw.pop("away_score", None)
        else:
            if "code" not in tie["home"] or "code" not in tie["away"]:
                raise ValueError("both clubs of this tie are not known yet")
            hs, as_ = _int(home_score), _int(away_score)
            if hs == as_:
                raise ValueError("a cup tie has a winner: the scores cannot be equal (an overtime score decides)")
            raw["home_score"], raw["away_score"] = hs, as_
        if date is not None:
            if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
                raise ValueError("the date is YYYY-MM-DD")
            raw["date"] = date
        if note is not None:
            raw["note"] = str(note)[:120]
        _write(d)


def set_sides(tie_id, home, away):
    """Correct the clubs of a tie of the FIRST round of the bracket (a later tie takes the winners of the previous ones)."""
    teams = known_teams()
    with _lock:
        d = load()
        raw = next((t for r in d["rounds"] for t in r.get("ties", []) if t["id"] == tie_id), None)
        if raw is None:
            raise ValueError("unknown tie")
        for c in (home, away):
            if c != "BYE" and not str(c).startswith("W:") and c not in teams:
                raise ValueError(f"unknown club {c}")
        raw["home"], raw["away"] = home, away
        _write(d)


def reset():
    with _lock:
        d = load()
        d["rounds"] = []
        d["demo"] = False
        _write(d)
