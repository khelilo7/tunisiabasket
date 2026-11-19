"""The history of the league: past seasons (assets/history), what they were made of (format), their tables, series and results, and the box scores the site holds for them.

Everything here ships with the code and is read-only. Where it comes from (assets/history/*, built by the scripts in tools/):
* champions.json   every champion since 1955-56 (Wikipedia), with the final's score when it is known;
* formats.json     how each season was played (play-off, play-out, super play-off... the format changed almost every year), written from the FTBB's formula and from the season pages;
* seasons/*.json   the phases of a season: tables, round-robin scores, series, from Wikipedia (English and French pages);
* games/*.json     box scores read from the PDFs the FTBB published (Internet Archive), loaded by stats.load_games like any other game.
A season is never shown as more than what these files hold: `coverage` says how many box scores there are and the page says which parts are missing.
"""
import json
import re

import config

ROOT = config.ASSETS_DIR / "history"


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def champions():
    return _read(ROOT / "champions.json", [])


def formats():
    return _read(ROOT / "formats.json", {})


def season_ids():
    """Seasons that have a detail file, newest first."""
    return sorted((p.stem for p in (ROOT / "seasons").glob("*.json")), reverse=True) if (ROOT / "seasons").exists() else []


def _boxes(season):
    """The box scores of `season` the site holds: [{"id","date","phase","a","b","as","bs"}], oldest first."""
    import stats
    out = []
    for g in stats.build_all_games():
        if stats.season_of(g["date"]) != season or not g.get("history_label"):
            continue
        a, b = g["teams"]
        out.append({"id": g["id"], "date": g["date"], "phase": g.get("phase"), "a": a["code"], "b": b["code"], "as": a["points"], "bs": b["points"],
                    **({"matchday": g["history_matchday"]} if g.get("date_approx") and g.get("history_matchday") else {})})
    return sorted(out, key=lambda x: (x["date"], x["id"]))


def _link(phases, boxes):
    """Mark every game of the phases that has a box score with its id (same two clubs, same two scores, in whichever order the home side is written)."""
    index = {}
    for x in boxes:
        index[(x["a"], x["b"], x["as"], x["bs"])] = x["id"]
        index[(x["b"], x["a"], x["bs"], x["as"])] = x["id"]
    for p in phases:
        for g in p.get("games") or []:
            h, a = (g.get("home") or {}), (g.get("away") or {})
            h = h.get("code") if isinstance(h, dict) else h
            a = a.get("code") if isinstance(a, dict) else a
            i = index.get((h, a, g.get("hs"), g.get("as")))
            if i:
                g["box"] = i
        for s in p.get("series") or []:
            ids = []
            for sa, sb in s.get("games") or []:
                ids.append(index.get((s["a"].get("code"), s["b"].get("code"), sa, sb)))
            if any(ids):
                s["box"] = ids


_SEG = [(r"(?:phase 1|première phase|first phase|first stage)", "First phase"), (r"(?:phase 2|deuxième phase|second phase)", "Second phase"),
        (r"(?:(?:phase 3|troisième phase)\s*\(super play-?offs?\)|super play-?offs?)", "Super play-off"), (r"(?:play-?offs?|championship playoff)", "Play-off"), (r"play-?outs?", "Play-out"),
        (r"(?:poule|groupe|group) (\w)", "Group {}"), (r"(?:matchs de )?barrages?", "Barrage"), (r"demi-?finales?|semi-?finals?", "Semi-finals"), (r"finales?|finals?", "Final"),
        (r"regular season", "Regular season"), (r"super 6", "Super 6"), (r"relegation round", "Relegation round"), (r"(?:formule de la compétition)", None), (r"classement|game \d+|.* vs\.? .*", None)]


def _segment(seg):
    seg = seg.strip()
    for pat, out in _SEG:
        m = re.fullmatch(pat, seg, re.I)
        if m:
            return out.format(*m.groups()) if out else None
    return seg


def phase_name(name):
    """'Deuxième phase · Play-off · Classement' -> 'Second phase · Play-off': one English name per stage whatever the page it comes from (the site translates it)."""
    segs = [x for x in (_segment(p) for p in name.split(" · ")) if x]
    if segs and segs[-1] == "Play-out":
        segs = [x for x in segs if x != "Play-off"]
    out = []
    for x in segs:
        if not out or out[-1] != x:
            out.append(x)
    return " · ".join(out) or name


def sections(phases):
    """The phases grouped under one name each, in order: [{"name","table","games","series"}]."""
    out, by = [], {}
    for p in phases:
        n = phase_name(p["name"])
        sec = by.get(n)
        if sec is None:
            sec = by[n] = {"name": n, "table": None, "games": [], "series": []}
            out.append(sec)
        if p["kind"] == "table" and sec["table"] is None:
            sec["table"] = [{**r, "rank": r.get("rank") or i, "j": r.get("j") or r["w"] + r["l"]} for i, r in enumerate(p["rows"], 1)]
        elif p["kind"] == "games":
            sec["games"] += p["games"]
        elif p["kind"] == "series":
            sec["series"] += p["series"]
    return out


def index():
    """{"champions": [...], "seasons": [{"season","champion","runner_up","score","boxes"}]}: what the history page lists."""
    champ = {c["season"]: c for c in champions()}
    seasons = []
    for s in season_ids():
        c = champ.get(s) or {}
        d = _read(ROOT / "seasons" / f"{s}.json", {})
        seasons.append({"season": s, "champion": c.get("champion") or d.get("champion"), "champion_code": c.get("champion_code"),
                        "runner_up": (c.get("final") or {}).get("runner_up") or d.get("runner_up"), "score": (c.get("final") or {}).get("score"),
                        "phases": len(d.get("phases") or []), "boxes": len(_boxes(s))})
    return {"champions": champions(), "seasons": seasons}


def view(season):
    """One season: format, phases, box scores. None for an unknown season."""
    if not re.fullmatch(r"\d{4}-\d{4}", season or ""):
        return None
    d = _read(ROOT / "seasons" / f"{season}.json", None)
    champ = {c["season"]: c for c in champions()}.get(season)
    if d is None and champ is None:
        return None
    d = d or {"season": season, "phases": []}
    boxes = _boxes(season)
    _link(d["phases"], boxes)
    c = champ or {}
    return {"season": season, "format": formats().get(season), "champion": c.get("champion") or d.get("champion"), "champion_code": c.get("champion_code"),
            "runner_up": (c.get("final") or {}).get("runner_up") or d.get("runner_up"), "final_score": (c.get("final") or {}).get("score"), "third": d.get("third"), "relegated": d.get("relegated"),
            "teams": d.get("teams"), "dates": d.get("dates"), "sections": sections(d["phases"]), "boxes": boxes, "source": d.get("source"),
            "coverage": {"boxes": len(boxes), "phases": len(d["phases"])}, "seasons": season_ids()}
