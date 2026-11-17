"""Several sources for one game: keep every version that was ever sent, compare them, let the ADMIN choose what is published (one source, or a mix cell by cell).

Until now sending a game again silently replaced the published one. Now every box score that reaches the site for a game id (a PDF, a CSV, a hand sheet, the production sheet...) is kept as a SOURCE in
`data/game_sources/<game id>.json` (kept across deployments and in the backups):

    {"id": "d01c5cf8761957d2", "locked": true, "chosen": "s2", "picks": {"DSG|23|pts": "s1"},
     "sources": [{"sid": "s1", "label": "published before", "at": "2026-11-16T22:58:11Z", "reviewed": true, "game": {...complete game, same format as data/games...}}, ...]}

  * Sources are added by `intake()` (called whenever a game is saved). The first time a game with a published file gets a second version, the published one becomes source s1 ("published before").
  * While a game is NOT locked, the newest version is published as before. Once the admin has chosen (`publish()`), the game is LOCKED: a later push only adds a source (flagged "new, not reviewed") and the
    published box score stays what the admin decided, until they unlock it or choose again.
  * `compare()` lines the sources up player by player (team + jersey number) and stat by stat and says where they differ. `publish()` publishes one source as it is, or a MIX: a base source plus picks
    "TEAM|NUMBER|stat": source id (also "TEAM|NUMBER|*": whether the player is on the sheet at all, and "TEAM||points": the team's total). The mix goes through the same consistency checks as any game.
  * `duplicates()` finds two game files that look like the same game (same two teams, same matchday) so that one can be attached to the other as a source.
"""
import copy
import datetime
import hashlib
import json
import re
import shutil

import config
from validate import validate

DIR = config.DATA_DIR / "game_sources"
GAMES = config.DATA_DIR / "games"
STATS = ("min", "fgm", "fga", "p2m", "p2a", "p3m", "p3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts")
VOLATILE = ("uploaded", "forced_with_problems", "merged_from")
GID = re.compile(r"^[A-Za-z0-9_-]{4,40}$")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(game):
    return hashlib.sha1(json.dumps({k: v for k, v in game.items() if k not in VOLATILE}, sort_keys=True).encode()).hexdigest()[:16]


def _path(gid):
    if not GID.match(str(gid or "")):
        raise ValueError("bad game id")
    return DIR / f"{gid}.json"


def load(gid):
    try:
        d = json.loads(_path(gid).read_text())
    except (OSError, ValueError):
        d = {}
    srcs = [s for s in d.get("sources") or [] if isinstance(s, dict) and isinstance(s.get("game"), dict)]
    return {"id": gid, "locked": bool(d.get("locked")), "chosen": d.get("chosen"), "base": d.get("base"), "picks": d.get("picks") if isinstance(d.get("picks"), dict) else {}, "sources": srcs}


def _write(d):
    DIR.mkdir(parents=True, exist_ok=True)
    f = _path(d["id"])
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: d[k] for k in ("id", "locked", "chosen", "base", "picks", "sources")}, indent=1, ensure_ascii=False))
    tmp.replace(f)


def _next_sid(d):
    return "s" + str(1 + max([int(re.sub(r"\D", "", s["sid"]) or 0) for s in d["sources"]] + [0]))


def _label(game):
    return str(game.get("source_file") or game.get("source") or "upload")[:80]


def intake(game):
    """Remember a game that is being saved as one more source of its id. Returns "publish" (write it as the published game, as always) or "kept" (the admin locked this game: only the source is added).
    The caller holds the admin's file lock."""
    gid = game.get("id")
    if not gid or not GID.match(str(gid)):
        return "publish"
    d = load(gid)
    existing = GAMES / f"{gid}.json"
    if not d["sources"] and existing.exists():
        try:
            old = json.loads(existing.read_text())
            d["sources"].append({"sid": "s1", "label": "published before", "at": datetime.datetime.fromtimestamp(existing.stat().st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "reviewed": True, "game": old})
            d["chosen"] = "s1"
        except (OSError, ValueError):
            pass
    h = _hash(game)
    same = next((s for s in d["sources"] if _hash(s["game"]) == h), None)
    held = d["locked"] and bool(d["sources"])
    if same is None:
        same = {"sid": _next_sid(d), "label": _label(game), "at": _now(), "reviewed": not held, "game": copy.deepcopy(game)}
        d["sources"].append(same)
    if held:
        _write(d)
        return "kept"
    d["chosen"], d["base"], d["picks"] = same["sid"], same["sid"], {}
    for s in d["sources"]:
        s["reviewed"] = True
    _write(d)
    return "publish"


# ---------------------------------------------------------------- the list and the comparison
def _score(game):
    return "–".join(str(t.get("points")) for t in game["teams"])


def _title(game):
    return " – ".join(t["code"] for t in game["teams"])


def list_games():
    """Games with at least two sources, the ones with something to review first."""
    out = []
    if DIR.exists():
        for f in sorted(DIR.glob("*.json")):
            d = load(f.stem)
            if len(d["sources"]) < 2:
                continue
            pub = next((s for s in d["sources"] if s["sid"] == d["chosen"]), d["sources"][-1])["game"]
            diffs = len(compare(f.stem)["diffs"])
            out.append({"id": d["id"], "title": _title(pub), "matchday": pub.get("matchday_no") or pub.get("matchday"), "date": pub.get("date"), "sources": len(d["sources"]), "locked": d["locked"], "chosen": d["chosen"],
                        "unreviewed": sum(1 for s in d["sources"] if not s.get("reviewed", True)), "diffs": diffs})
    out.sort(key=lambda g: (-g["unreviewed"], -g["diffs"], g["id"]))
    return out


def compare(gid):
    """The sources side by side: {id, locked, chosen, picks, sources: [{sid, label, at, reviewed, score}], teams: [{code, name, points: {sid: n}, players: [{number, names, present, stats: {stat: {sid: n}}, diff: [stat...]}]}], diffs: [cell keys]}"""
    d = load(gid)
    if not d["sources"]:
        raise KeyError(gid)
    sids = [s["sid"] for s in d["sources"]]
    games = {s["sid"]: s["game"] for s in d["sources"]}
    codes = []
    for g in games.values():
        for t in g["teams"]:
            if t["code"] not in codes:
                codes.append(t["code"])
    diffs, teams = [], []
    for code in codes:
        trows = {sid: next((t for t in g["teams"] if t["code"] == code), None) for sid, g in games.items()}
        points = {sid: (t.get("points") if t else None) for sid, t in trows.items()}
        if len({v for v in points.values() if v is not None}) > 1:
            diffs.append(f"{code}||points")
        nums = []
        for t in trows.values():
            for p in (t or {}).get("players") or []:
                if p.get("number") not in nums:
                    nums.append(p.get("number"))
        players = []
        for n in sorted(nums, key=lambda x: (x is None, x if isinstance(x, int) else 0)):
            prow = {sid: next((p for p in (t or {}).get("players") or [] if p.get("number") == n), None) for sid, t in trows.items()}
            present = {sid: p is not None for sid, p in prow.items()}
            names = {sid: p.get("name") for sid, p in prow.items() if p}
            st, diff = {}, []
            for k in STATS:
                vals = {sid: p.get(k) for sid, p in prow.items() if p is not None}
                st[k] = vals
                if len({v for v in vals.values() if v is not None}) > 1:
                    diff.append(k)
                    diffs.append(f"{code}|{n}|{k}")
            if len(set(present.values())) > 1:
                diffs.append(f"{code}|{n}|*")
            players.append({"number": n, "names": names, "name_diff": len(set(names.values())) > 1, "present": present, "stats": st, "diff": diff})
        teams.append({"code": code, "name": next((t.get("name") for t in trows.values() if t and t.get("name")), code), "points": points, "players": players})
    return {"id": gid, "locked": d["locked"], "chosen": d["chosen"], "base": d.get("base") or d["chosen"], "picks": d["picks"],
            "sources": [{"sid": s["sid"], "label": s.get("label"), "at": s.get("at"), "reviewed": s.get("reviewed", True), "score": _score(s["game"]), "title": _title(s["game"]), "problems": validate(s["game"])} for s in d["sources"]],
            "teams": teams, "diffs": diffs, "sids": sids}


# ---------------------------------------------------------------- the admin's decision
def _parse(key):
    parts = str(key).split("|")
    if len(parts) != 3:
        raise ValueError(f"bad cell {key!r}")
    return parts[0], parts[1], parts[2]


def build(d, base, picks):
    """The game that results from `base` (a source id) and the cell picks. Raises ValueError for an unknown source or cell."""
    src = {s["sid"]: s["game"] for s in d["sources"]}
    if base not in src:
        raise ValueError("unknown source")
    game = copy.deepcopy(src[base])
    for key, sid in sorted(picks.items()):
        if sid not in src:
            raise ValueError(f"unknown source {sid} for {key}")
        code, num, what = _parse(key)
        team = next((t for t in game["teams"] if t["code"] == code), None)
        steam = next((t for t in src[sid]["teams"] if t["code"] == code), None)
        if team is None or steam is None:
            raise ValueError(f"unknown team in {key}")
        if what == "points" and not num:
            team["points"] = steam["points"]
            continue
        n = int(num)
        mine = next((p for p in team["players"] if p.get("number") == n), None)
        theirs = next((p for p in steam["players"] if p.get("number") == n), None)
        if what == "*":
            if theirs is None and mine is not None:
                team["players"].remove(mine)
            elif theirs is not None and mine is None:
                team["players"].append(copy.deepcopy(theirs))
                team["players"].sort(key=lambda p: (p.get("number") is None, p.get("number") or 0))
            continue
        if what not in STATS:
            raise ValueError(f"unknown stat in {key}")
        if mine is None or theirs is None:
            raise ValueError(f"{key}: the player is not on both sheets (choose the whole row with *)")
        mine[what] = theirs.get(what)
    return game


def publish(gid, base, picks=None, lock=True, force=False):
    """Publish `base` (a source id) with the picks applied. Returns (game, problems); nothing is written when there are problems and not `force`."""
    d = load(gid)
    if not d["sources"]:
        raise KeyError(gid)
    picks = {k: v for k, v in (picks or {}).items() if v and v != base}
    game = build(d, base, picks)
    problems = validate(game)
    if problems and not force:
        return None, problems
    game["id"] = gid
    game["uploaded"] = True
    if picks:
        game["merged_from"] = sorted({base, *picks.values()})
    else:
        game.pop("merged_from", None)
    if problems:
        game["forced_with_problems"] = problems
    else:
        game.pop("forced_with_problems", None)
    GAMES.mkdir(parents=True, exist_ok=True)
    (GAMES / f"{gid}.json").write_text(json.dumps(game, indent=1, ensure_ascii=False))
    d.update(chosen=base if not picks else "mixed", base=base, picks=picks, locked=bool(lock))
    for s in d["sources"]:
        s["reviewed"] = True
    _write(d)
    return game, problems


def unlock(gid):
    d = load(gid)
    if not d["sources"]:
        raise KeyError(gid)
    d["locked"] = False
    _write(d)


# ---------------------------------------------------------------- two files for one game
def duplicates():
    """Pairs of game files that look like one game (same two teams on the same matchday): [{"ids": [a, b], "title", "matchday"}]."""
    seen, out = {}, []
    for f in sorted(GAMES.glob("*.json")) if GAMES.exists() else []:
        try:
            g = json.loads(f.read_text())
            key = (frozenset(t["code"] for t in g["teams"]), g.get("matchday_no") or g.get("matchday"))
        except (OSError, ValueError, KeyError):
            continue
        seen.setdefault(key, []).append((f.stem, g))
    for (_, md), items in seen.items():
        if len(items) > 1:
            out.append({"ids": [i for i, _ in items], "title": _title(items[0][1]), "matchday": md})
    return out


def attach(gid, other):
    """Make the game file `other` one more source of `gid` and take it off the site (it goes to games_replaced/)."""
    a, b = GAMES / f"{gid}.json", GAMES / f"{other}.json"
    if gid == other or not a.exists() or not b.exists():
        raise ValueError("two different games of the site are needed")
    ga, gb = json.loads(a.read_text()), json.loads(b.read_text())
    if {t["code"] for t in ga["teams"]} != {t["code"] for t in gb["teams"]}:
        raise ValueError("these are not the same two teams")
    d = load(gid)
    if not d["sources"]:
        d["sources"].append({"sid": "s1", "label": "published before", "at": _now(), "reviewed": True, "game": ga})
        d["chosen"] = "s1"
    gb["id"] = gid
    if _hash(gb) not in {_hash(s["game"]) for s in d["sources"]}:
        d["sources"].append({"sid": _next_sid(d), "label": f"{_label(gb)} (file {other})", "at": _now(), "reviewed": False, "game": gb})
    _write(d)
    (config.DATA_DIR / "games_replaced").mkdir(parents=True, exist_ok=True)
    shutil.move(str(b), str(config.DATA_DIR / "games_replaced" / f"{other}-{_now().replace(':', '')}.json"))
