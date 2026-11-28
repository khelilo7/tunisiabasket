"""A finished season shown the way the current one is: one view per phase (tables, series, the cup bracket), each club's season, and the Finals MVP.

Everything is computed from what ships with the code: the results of assets/history/seasons/<season>.json (every score, with or without a box score)
and the box scores of assets/history/games. A result nobody published is listed as missing, never guessed.
"""
import itertools
from collections import defaultdict

import history
import ranking
import stats

SEASONS = ("2025-2026",)
# key -> (name of the section in the season file, "phase" of its box scores)
PHASES = [("regular", "First phase", "regular season"), ("playoff", "Play-off", "play-off"), ("playout", "Play-out", "play-out"), ("super", "Super play-off", "super play-off"),
          ("superout", "Super play-out", "super play-out"), ("cup", "Tunisian Cup", "cup"), ("ftbb", "FTBB Cup", "ftbb cup")]
CARRY = {"playoff": "regular", "playout": "regular", "superout": "playout"}     # these tables start with the points of the phase before
LOWER = {"EZS": "nat1", "AA": "nat1"}                                          # the clubs of the cup that were not in the Pro A that season
CUP_ROUNDS = [("1/8", 8), ("Quarter-finals", 4), ("Semi-finals", 2), ("Championship final", 1)]


def available(season):
    return season in SEASONS


def _sections(season):
    v = history.view(season)
    return {s["name"]: s for s in v["sections"]}, v


def _names(sections):
    out = {}
    for s in sections.values():
        for g in s["games"]:
            for side in (g["home"], g["away"]):
                out[side["code"]] = side["name"]
    return out


def _game(g):
    return {"date": g.get("date"), "home": g["home"]["code"], "away": g["away"]["code"], "home_score": g["hs"], "away_score": g["as"], "box": g.get("box")}


def _groups(games):
    """The clubs that met each other, as groups (the two pools of the first phase)."""
    near = defaultdict(set)
    for g in games:
        near[g["home"]].add(g["away"])
        near[g["away"]].add(g["home"])
    seen, out = set(), []
    for c in sorted(near):
        if c in seen:
            continue
        group, todo = set(), [c]
        while todo:
            x = todo.pop()
            if x not in group:
                group.add(x)
                todo += near[x]
        seen |= group
        out.append(sorted(group))
    return out


def _table(codes, games, names, carried=None):
    carried = carried or {}
    rows = {c: {"code": c, "name": names.get(c, c), "j": 0, "w": 0, "l": 0, "pf": 0, "pa": 0, "carry": carried.get(c, 0)} for c in codes}
    for g in games:
        for c, f, a in ((g["home"], g["home_score"], g["away_score"]), (g["away"], g["away_score"], g["home_score"])):
            r = rows[c]
            r["j"] += 1
            r["w" if f > a else "l"] += 1
            r["pf"] += f
            r["pa"] += a
    for r in rows.values():
        r["diff"] = r["pf"] - r["pa"]
        r["pts"] = r["carry"] + 2 * r["w"] + r["l"]
    out = ranking.rank(list(rows.values()), games, final=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def _missing_pairs(codes, games):
    """Home-and-away round robin: the (home, away) meetings with no result. A meeting listed the other way round twice counts as both."""
    left = []
    for a, b in itertools.combinations(codes, 2):
        n = sum({g["home"], g["away"]} == {a, b} for g in games)
        if n < 2:
            have = {(g["home"], g["away"]) for g in games}
            open_ = [p for p in ((a, b), (b, a)) if p not in have]
            left += [{"home": h, "away": w} for h, w in open_[: 2 - n]]
    return left


def _series(sec, names, seeds, boxes):
    rounds = []
    for key, title in (("Semi-finals", "Semi-finals"), ("Final", "Championship final"), ("Third place", "Third place")):
        out = []
        for s in sec["series"]:
            if s["round"] != key:
                continue
            a, b = s["a"]["code"], s["b"]["code"]
            wa = sum(x > y for x, y in s["games"])
            wb = len(s["games"]) - wa
            winner = a if wa > wb else b if wb > wa else None
            side = lambda c, w: {"code": c, "name": names.get(c, c), "seed": seeds.get(c), "wins": w}
            ids = list(s.get("box") or [])
            games = []
            for i, (x, y) in enumerate(s["games"]):
                bid = ids[i] if i < len(ids) else None
                g = boxes.get(bid)
                games.append({"home": a, "away": b, "home_score": x, "away_score": y, "played": True, "box": bid, "date": g["date"] if g else None})
            need = 3 if key != "Third place" else 2
            out.append({"a": side(a, wa), "b": side(b, wb), "winner": winner, "done": True, "live": False, "need": need, "best_of": 2 * need - 1, "games": games, "two_legs": key == "Third place"})
        if out:
            rounds.append({"name": title, "series": out})
    return rounds


def _bracket(games, names):
    """The knockout cup as a tree, from the final backwards: each side of a tie comes from the tie its club won the round before; a tie nobody published is left blank."""
    by_date = sorted(games, key=lambda g: g["date"] or "")
    if not by_date:
        return [], []
    club = lambda c: {"code": c, "name": names.get(c, c), "league": LOWER.get(c, "proa")}

    def tie(g):
        win = g["home"] if g["home_score"] > g["away_score"] else g["away"]
        lose = g["away"] if win == g["home"] else g["home"]
        return {"home": club(g["home"]), "away": club(g["away"]), "home_score": g["home_score"], "away_score": g["away_score"], "date": g["date"], "winner": win, "played": True,
                "upset": LOWER.get(win) == "nat1" and LOWER.get(lose) != "nat1", "note": "", "box": g["box"]}

    final = tie(by_date[-1])
    levels, left, used = [[final]], by_date[:-1], {id(by_date[-1])}
    for _ in range(len(CUP_ROUNDS) - 1):
        prev = []
        for t in levels[0]:
            for side in (t["home"], t["away"]):
                code = side.get("code")
                g = None
                if code:
                    wins = [x for x in left if id(x) not in used and code in (x["home"], x["away"]) and (x["date"] or "") < (t.get("date") or "9")
                            and (x["home_score"] > x["away_score"]) == (x["home"] == code)]
                    g = wins[-1] if wins else None
                if g:
                    used.add(id(g))
                    prev.append(tie(g))
                else:
                    prev.append({"home": club(code) if code else {"tbd": True, "unknown": True}, "away": {"tbd": True, "unknown": True}, "home_score": None, "away_score": None, "date": None, "winner": code, "played": False,
                                 "upset": False, "note": "", "box": None})
        levels.insert(0, prev)
    rounds = [{"name": n, "date": None, "done": True, "ties": lv} for (n, _), lv in zip(CUP_ROUNDS, levels)]
    earlier = [tie(g) for g in left if id(g) not in used]
    return rounds, earlier


def finals_mvp(season):
    """The champion's player who did most in the final series: highest total evaluation (PIR), then points. None while a final has no box score."""
    secs, _ = _sections(season)
    final = next((s for s in secs.get("Super play-off", {}).get("series", []) if s["round"] == "Final"), None)
    if not final or not final.get("box"):
        return None
    wins = sum(x > y for x, y in final["games"])
    champ = final["a"]["code"] if 2 * wins > len(final["games"]) else final["b"]["code"]
    ids = {i for i in final["box"] if i}
    d = stats.build(season, phase="super play-off")
    rows = []
    for p in d["players"]:
        log = [r for r in p["log"] if r["game_id"] in ids and r["team"] == champ]
        if log:
            n = len(log)
            avg = lambda k: round(sum(r[k] or 0 for r in log) / n, 1)
            rows.append({"id": p["id"], "name": p["name"], "team": champ, "number": p["number"], "photo": p.get("photo"), "gp": n, "total_pir": sum(r["pir"] or 0 for r in log),
                         "pir": avg("pir"), "pts": avg("pts"), "reb": avg("reb"), "ast": avg("ast"), "stl": avg("stl")})
    if not rows:
        return None
    rows.sort(key=lambda r: (r["total_pir"], r["pts"]), reverse=True)
    return {**rows[0], "games": len(ids), "next": rows[1:3]}


def view(season):
    """The season page: one block per phase that has results. None for a season not shown this way."""
    if not available(season):
        return None
    secs, hv = _sections(season)
    names = _names(secs)
    boxes = {b["id"]: b for b in hv["boxes"]}
    phases, tables = [], {}
    series = secs.get("Super play-off", {}).get("series", [])
    semis = [s for s in series if s["round"] == "Semi-finals"]
    seeds = {}
    if len(semis) == 2:                                # the semi-finals are 1st v 4th and 2nd v 3rd: the better seed is written first
        seeds = {semis[0]["a"]["code"]: 1, semis[0]["b"]["code"]: 4, semis[1]["a"]["code"]: 2, semis[1]["b"]["code"]: 3}
    for key, name, box_phase in PHASES:
        sec = secs.get(name)
        if not sec or not (sec["games"] or sec["series"]):
            continue
        block = {"key": key, "name": name, "box_phase": box_phase}
        games = [_game(g) for g in sec["games"]]
        if key == "super":
            block.update(format="series", rounds=_series(sec, names, seeds, boxes), games=[g for r in _series(sec, names, seeds, boxes) for s in r["series"] for g in s["games"]])
            final = next((s for s in series if s["round"] == "Final"), None)
            if final:
                champ = final["a"]["code"] if sum(x > y for x, y in final["games"]) * 2 > len(final["games"]) else final["b"]["code"]
                block["champion"] = {"code": champ, "name": names.get(champ, champ)}
        elif key == "cup":
            rounds, earlier = _bracket(games, names)
            block.update(format="bracket", rounds=rounds, earlier=earlier, games=games,
                         champion=({"code": rounds[-1]["ties"][0]["winner"], "name": names.get(rounds[-1]["ties"][0]["winner"])} if rounds else None))
        else:
            groups = _groups(games)
            out = []
            for i, codes in enumerate(groups):
                mine = [g for g in games if g["home"] in codes]
                carried = {}
                if key in CARRY:
                    before = tables.get(CARRY[key], {})
                    carried = {c: before.get(c, 0) for c in codes}
                table = _table(codes, mine, names, carried)
                tables.setdefault(key, {}).update({r["code"]: r["pts"] for r in table})
                out.append({"name": f"Group {'AB'[i]}" if len(groups) > 1 else None, "table": table})
            missing = [m for codes in groups for m in _missing_pairs(codes, [g for g in games if g["home"] in codes])]
            if key == "playoff" and seeds:             # the order the semi-finals were drawn from is the official one
                for grp in out:
                    grp["table"].sort(key=lambda r: (seeds.get(r["code"], 9), r["rank"]))
                    for i, r in enumerate(grp["table"], 1):
                        r["rank"] = i
            block.update(format="league", groups=out, games=games, missing=missing, carry=key in CARRY)
        block["without_box"] = sum(not g["box"] for g in block["games"])
        phases.append(block)
    return {"season": season, "champion": hv["champion"], "champion_code": hv.get("champion_code"), "format": hv.get("format"), "teams": names,
            "phases": phases, "finals_mvp": finals_mvp(season), "boxes": len(boxes)}


def _line(rows):
    """A team's per-game numbers from its box scores: rows of (own player sums, opponent player sums)."""
    n = len(rows)
    if not n:
        return None
    tot = lambda i, k: sum(r[i][k] for r in rows)
    pct = lambda i, m, a: round(100 * tot(i, m) / tot(i, a), 1) if tot(i, a) else None
    per = lambda i, k: round(tot(i, k) / n, 1)
    return {"gp": n, "pts": per(0, "pts"), "opp_pts": per(1, "pts"), "reb": per(0, "reb"), "opp_reb": per(1, "reb"), "oreb": per(0, "oreb"), "ast": per(0, "ast"), "tov": per(0, "tov"),
            "stl": per(0, "stl"), "blk": per(0, "blk"), "fg_pct": pct(0, "fgm", "fga"), "p3_pct": pct(0, "p3m", "p3a"), "ft_pct": pct(0, "ftm", "fta"), "opp_fg_pct": pct(1, "fgm", "fga"),
            "p3a": per(0, "p3a"), "fta": per(0, "fta")}


def team(season, code, phase=None):
    """One club's season: record per phase, every game (with or without its box score), what is missing, team numbers and players for the chosen phase."""
    v = view(season)
    if not v or code not in v["teams"]:
        return None
    full = {g["id"]: g for g in stats.build(season)["games"]}
    phases, games, missing = [], [], []
    for b in v["phases"]:
        mine = [{**g, "phase": b["box_phase"], "phase_name": b["name"]} for g in b["games"] if code in (g["home"], g["away"])]
        gone = [{**m, "phase": b["box_phase"], "phase_name": b["name"]} for m in b.get("missing") or [] if code in (m["home"], m["away"])]
        if not mine and not gone:
            continue
        won = sum((g["home_score"] > g["away_score"]) == (g["home"] == code) and g["home_score"] != g["away_score"] for g in mine)
        pf = sum(g["home_score"] if g["home"] == code else g["away_score"] for g in mine)
        pa = sum(g["away_score"] if g["home"] == code else g["home_score"] for g in mine)
        rank = next((r["rank"] for grp in b.get("groups") or [] for r in grp["table"] if r["code"] == code), None)
        phases.append({"key": b["key"], "name": b["name"], "box_phase": b["box_phase"], "played": len(mine), "w": won, "l": len(mine) - won, "pf": pf, "pa": pa, "rank": rank,
                       "with_box": sum(bool(g["box"]) for g in mine), "no_result": len(gone)})
        games += mine
        missing += gone
    wanted = [g for g in games if g["box"] and (not phase or g["phase"] == phase)]
    rows = []
    for g in wanted:
        box = full.get(g["box"])
        if not box:
            continue
        sums = []
        for t in sorted(box["teams"], key=lambda t: t["code"] != code):
            s = defaultdict(int)
            for p in t["players"]:
                if not p.get("dnp"):
                    for k in ("pts", "reb", "oreb", "ast", "tov", "stl", "blk", "fgm", "fga", "p3m", "p3a", "ftm", "fta"):
                        s[k] += p.get(k) or 0
            sums.append(s)
        rows.append(sums)
    d = stats.build(season, phase=phase)
    players = []
    for p in d["players"]:
        log = [r for r in p["log"] if r["team"] == code]
        if not log:
            continue
        n = len(log)
        avg = lambda k: round(sum(r[k] or 0 for r in log) / n, 1)
        players.append({"id": p["id"], "name": p["name"], "number": log[-1]["number"], "pos": p.get("pos"), "gp": n, **{k: avg(k) for k in ("min", "pts", "reb", "ast", "pir")}})
    players.sort(key=lambda p: (p["pts"], p["gp"]), reverse=True)
    champion = [b["name"] for b in v["phases"] if (b.get("champion") or {}).get("code") == code]
    return {"season": season, "code": code, "name": v["teams"][code], "phase": phase, "phases": phases, "titles": champion,
            "games": sorted(games, key=lambda g: g["date"] or "", reverse=True), "without_box": [g for g in games if not g["box"]], "no_result": missing,
            "stats": _line(rows), "players": players, "finals_mvp": v["finals_mvp"] if v["finals_mvp"] and v["finals_mvp"]["team"] == code else None}
