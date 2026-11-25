"""The Tunisian men's national team: who is called up, the games, the statistics, the history. A discreet page of the site (not the league).

Two files, layered like the roster:

* assets/national_team.json (in git)   the starting data: the competitions, the called-up players of the latest window, the players who are not in the Tunisian
                                       league, the per-game statistics of the 2027 World Cup qualifiers, the games of the qualifiers, and the history (facts with their source).
* data/national_team.json (the admin)  what the admin changed; it wins over the shipped file:
      {"callup": {"label": "...", "date": "2027-02-20", "players": ["ca-24", "usm-23", "yacine-toumi"]},   replaces the shipped list
       "externals": {"yacine-toumi": {...} | null},                       players outside the league (a slug, not a team-number id); null hides a shipped one
       "competitions": [{"id": "wcq27", "en": "...", "fr": "..."}],       added to the shipped ones
       "games": {"<id>": {...}}, "hidden_games": ["<id>"],                a game of the admin, or a corrected shipped one; a shipped game can be hidden
       "stats": {"<competition id>": {"rows": [{"pid": "ca-24", "g": 7, "min": 33, "pts": 18.1, "reb": 4.3, "ast": 5.7}], "note": "..."}}}   per-game totals typed without box scores

A player of the league is named by his id (team code and jersey number: "ca-24"); somebody who does not play in Tunisia by a slug of his name ("yacine-toumi"), which can never look
like a league id (no number at the end). A game:  {"id", "competition", "date", "time", "opp" (country code or None), "opp_name", "site" ("home" | "away" | "neutral"), "venue", "round",
"tun" and "opp_score" (None while it is to come), "ot" (overtime periods), "box": [{"pid"|"name", "min", "pts", "reb", "ast", "stl", "blk", "tov", "pf"}], "check": true when a fact is not confirmed}.
The statistics of a competition come from the box scores of its games when there are some for the player (as many games as the summary counts, or more), else from the summary rows.
"""
import difflib
import json
import re
import threading
import time
import unicodedata

import config
import countries

ASSET = config.ASSETS_DIR / "national_team.json"
_lock = threading.Lock()
SLUG = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
LEAGUE_ID = re.compile(r"^[a-z0-9]+-\d+$")
SITES = ("home", "away", "neutral")
BOX_FIELDS = ("min", "pts", "reb", "ast", "stl", "blk", "tov", "pf")
SUMMARY_FIELDS = ("min", "pts", "reb", "ast", "eff")      # what a summary row (per game) can hold, besides g


def _file():
    return config.DATA_DIR / "national_team.json"


def _read(path):
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(d):
    f = _file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    tmp.replace(f)


def slugify(text):
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# ---------------------------------------------------------------- the merged data
def load():
    """The shipped data with the admin's changes on top (see the module doc)."""
    ship, adm = _read(ASSET), _read(_file())
    callup = adm.get("callup") if isinstance(adm.get("callup"), dict) and adm["callup"].get("players") is not None else ship.get("callup") or {}
    externals = {**(ship.get("externals") or {}), **(adm.get("externals") or {})}
    comps = {c["id"]: c for c in (ship.get("competitions") or []) if isinstance(c, dict)}
    comps.update({c["id"]: c for c in (adm.get("competitions") or []) if isinstance(c, dict) and c.get("id")})
    hidden = set(adm.get("hidden_games") or [])
    games = {g["id"]: g for g in (ship.get("games") or []) if isinstance(g, dict) and g.get("id") not in hidden}
    games.update({k: {**g, "id": k} for k, g in (adm.get("games") or {}).items() if isinstance(g, dict) and k not in hidden})
    summaries = {s["competition"]: s for s in (ship.get("stats") or []) if isinstance(s, dict)}
    summaries.update({k: {**v, "competition": k} for k, v in (adm.get("stats") or {}).items() if isinstance(v, dict)})
    return {"team": ship.get("team") or {}, "history": ship.get("history") or [], "callup": callup, "externals": {k: v for k, v in externals.items() if isinstance(v, dict)},
            "competitions": list(comps.values()), "games": sorted(games.values(), key=lambda g: (g.get("date") or "", g.get("time") or "")), "summaries": summaries,
            "admin": adm}


def called_ids():
    """Ids (league ids and slugs) of the called-up players, in the order of the list."""
    return [str(x) for x in (load()["callup"].get("players") or [])]


# ---------------------------------------------------------------- games and statistics
def _played(g):
    return g.get("tun") is not None and g.get("opp_score") is not None


def _round1(x):
    return None if x is None else round(x + 1e-9, 1)


def _box_totals(games, pid):
    """{competition: [games, totals]} from the box scores where `pid` has a line (a line with no minutes and no points is not a game played)."""
    out = {}
    for g in games:
        for ln in g.get("box") or []:
            if ln.get("pid") == pid and (ln.get("min") or ln.get("pts") or ln.get("reb") or ln.get("ast")):
                n, tot = out.setdefault(g.get("competition"), [0, {k: 0 for k in BOX_FIELDS}])
                out[g.get("competition")][0] = n + 1
                for k in BOX_FIELDS:
                    tot[k] += ln.get(k) or 0
    return out


def player_stats(pid, data=None):
    """Per-game national team statistics of one player: [{competition, g, min, pts, reb, ast, stl, blk, tov, pf, src}], one per competition, best known first."""
    d = data or load()
    boxes = _box_totals(d["games"], pid)
    rows = {}
    for comp, s in d["summaries"].items():
        r = next((r for r in s.get("rows") or [] if r.get("pid") == pid), None)
        if r:
            rows[comp] = {"competition": comp, "g": r.get("g"), **{k: r.get(k) for k in SUMMARY_FIELDS if r.get(k) is not None}, "src": "summary"}
    for comp, (n, tot) in boxes.items():
        if comp not in rows or n >= (rows[comp].get("g") or 0):
            rows[comp] = {"competition": comp, "g": n, **{k: _round1(v / n) for k, v in tot.items() if v or k in ("min", "pts", "reb", "ast")}, "src": "box"}
    order = {c["id"]: i for i, c in enumerate(d["competitions"])}
    return sorted(rows.values(), key=lambda r: order.get(r["competition"], 99))


def comp_table(comp, d):
    """Every player with statistics in a competition: [{pid, g, min, pts, reb, ast, ...}], the best scorer first."""
    pids = {r.get("pid") for r in (d["summaries"].get(comp) or {}).get("rows") or []}
    pids |= {ln.get("pid") for g in d["games"] if g.get("competition") == comp for ln in g.get("box") or [] if ln.get("pid")}
    out = []
    for pid in pids:
        r = next((x for x in player_stats(pid, d) if x["competition"] == comp), None)
        if r:
            out.append({"pid": pid, **{k: v for k, v in r.items() if k != "competition"}})
    return sorted(out, key=lambda r: (-(r.get("pts") or 0), -(r.get("g") or 0)))


def record(comp, d):
    """{w, l, pf, pa} of the played games of a competition."""
    g = [x for x in d["games"] if x.get("competition") == comp and _played(x)]
    return {"w": sum(1 for x in g if x["tun"] > x["opp_score"]), "l": sum(1 for x in g if x["tun"] < x["opp_score"]), "pf": sum(x["tun"] for x in g), "pa": sum(x["opp_score"] for x in g)}


def _game_out(g):
    c = g.get("opp")
    en, fr = countries.COUNTRIES.get(c, (g.get("opp_name"), g.get("opp_name")))
    return {"id": g["id"], "competition": g.get("competition"), "date": g.get("date"), "time": g.get("time") or "", "opp": c, "opp_name": g.get("opp_name") or en, "opp_name_en": en or g.get("opp_name"),
            "opp_name_fr": fr or g.get("opp_name"), "site": g.get("site") or "neutral", "venue": g.get("venue") or "", "round": g.get("round") or "", "tun": g.get("tun"), "opp_score": g.get("opp_score"),
            "ot": g.get("ot") or 0, "played": _played(g), "won": (g["tun"] > g["opp_score"]) if _played(g) else None, "check": bool(g.get("check")), "box": len(g.get("box") or [])}


def today():
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 3600))      # Tunisia time (UTC+1)


# ---------------------------------------------------------------- the public view
def _league():
    import stats
    return {p["id"]: p for p in stats.build()["players"]}


def _person(pid, d, league):
    """One called-up (or listed) player: his league data when he plays in Tunisia, his own profile when he does not."""
    p = league.get(pid)
    if p:
        return {"pid": pid, "ext": False, "name": p["name"], "team": p["team"], "number": p["number"], "photo": p.get("photo"), "pos": p.get("pos"), "bio": p.get("bio")}
    e = d["externals"].get(pid)
    if e:
        return {"pid": pid, "ext": True, "name": e.get("name") or pid, "team": None, "club": e.get("club") or "", "number": None, "photo": e.get("photo"), "pos": e.get("position"),
                "bio": {k: e[k] for k in ("birth", "height", "nationality") if e.get(k)} or None}
    return {"pid": pid, "ext": False, "name": pid, "team": None, "number": None, "photo": None, "pos": None, "bio": None}


def view():
    """Everything the national team page needs (/api/national-team)."""
    d, league = load(), None
    league = _league()
    ids = called_ids()
    comps = [{**c, "record": record(c["id"], d)} for c in d["competitions"]]
    games = [{**_game_out(g), "lines": [{**{k: ln.get(k) for k in BOX_FIELDS if ln.get(k) is not None}, "pid": ln.get("pid"),
                                          "name": _person(ln["pid"], d, league)["name"] if ln.get("pid") else ln.get("name") or "?", "ext": ln.get("pid") in d["externals"]}
                                         for ln in sorted(g.get("box") or [], key=lambda x: -(x.get("min") or 0))]} for g in d["games"]]
    td = today()
    upcoming = [g for g in games if not g["played"] and (g["date"] or "") >= td]
    seen = set(ids)
    tables = []
    for c in d["competitions"]:
        rows = comp_table(c["id"], d)
        if rows:
            seen |= {r["pid"] for r in rows}
            sm = d["summaries"].get(c["id"]) or {}
            tables.append({"competition": c["id"], "note": sm.get("note") or "", "note_en": sm.get("note_en") or sm.get("note") or "", "note_fr": sm.get("note_fr") or sm.get("note") or "", "src": sm.get("src") or "", "rows": [{**r, **{k: v for k, v in _person(r["pid"], d, league).items() if k in ("name", "team", "ext", "number")}} for r in rows]})
    return {"team": d["team"], "history": d["history"], "competitions": comps, "games": games[::-1], "next": upcoming[0] if upcoming else None,
            "callup": {"label": d["callup"].get("label") or "", "label_fr": d["callup"].get("label_fr") or "", "date": d["callup"].get("date") or "",
                       "players": [{**_person(pid, d, league), "stats": player_stats(pid, d)} for pid in ids]},
            "stats": tables,
            "externals": {k: {**v, "stats": player_stats(k, d)} for k, v in d["externals"].items()}, "today": td}


def for_player(pid):
    """What a player page shows about the national team: whether he was called up in the latest window, and his statistics."""
    d = load()
    return {"called": pid in called_ids(), "label": d["callup"].get("label") or "", "label_fr": d["callup"].get("label_fr") or "", "stats": player_stats(pid, d),
            "competitions": {c["id"]: {"en": c.get("en"), "fr": c.get("fr")} for c in d["competitions"]}}


def called_view():
    """Light list for the labels shown next to names: ids of the called-up players of the latest window."""
    d = load()
    return {"ids": called_ids(), "label": d["callup"].get("label") or "", "label_fr": d["callup"].get("label_fr") or "", "date": d["callup"].get("date") or ""}


# ---------------------------------------------------------------- matching names to players
_SAME = {"med": "mohamed", "mohammed": "mohamed", "muhammad": "mohamed", "mouhamed": "mohamed", "mohamad": "mohamed", "oussama": "oussema", "ousama": "oussema", "jawhar": "jawher",
         "ziyed": "zied", "ziad": "zied", "bechir": "bechir", "bachir": "bechir", "belhssan": "belhsan", "belhassan": "belhsan", "yasin": "yacine", "yassin": "yacine"}


def _tokens(name):
    t = re.sub(r"[^a-z0-9 ]+", " ", unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()).split()
    return [_SAME.get(x, x) for x in t]


def similarity(a, b):
    """0..1: how alike two names are, whatever the order of the words and small spelling changes (Lahyani / Lahiani, Oussama / Oussema)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    s1 = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    s2 = difflib.SequenceMatcher(None, "".join(ta), "".join(tb)).ratio()
    last = difflib.SequenceMatcher(None, ta[-1], tb[-1]).ratio() if len(ta) > 1 and len(tb) > 1 else 1.0         # the family name counts
    return round(max(s1, s2) * (0.6 + 0.4 * last), 3)


def match(name, pool, n=3):
    """The best candidates of `pool` ({id: name}) for a typed name: [(id, name, score)], best first."""
    sc = sorted(((i, nm, similarity(name, nm)) for i, nm in pool.items()), key=lambda x: -x[2])
    return sc[:n]


def match_report(names, limit=0.6):
    """For each typed name: the best match among the league players and the externals, and whether it needs a look (score under 0.95, or a close second)."""
    d, league = load(), None
    league = _league()
    pool = {pid: p["name"] for pid, p in league.items()}
    pool.update({k: v.get("name") or k for k, v in d["externals"].items()})
    out = []
    for nm in names:
        top = match(nm, pool)
        best = top[0] if top and top[0][2] >= limit else None
        out.append({"input": nm, "pid": best[0] if best else None, "name": best[1] if best else None, "score": best[2] if best else 0,
                    "team": (league.get(best[0]) or {}).get("team") if best else None, "ext": bool(best and best[0] in d["externals"]),
                    "uncertain": not best or best[2] < 0.95 or (len(top) > 1 and top[1][2] > best[2] - 0.05),
                    "others": [{"pid": i, "name": x, "score": s} for i, x, s in top[1:] if s >= limit]})
    return out


# ---------------------------------------------------------------- the admin's changes
def _edit(fn):
    with _lock:
        adm = _read(_file())
        res = fn(adm)
        _write(adm)
        return res


def _num(v, lo, hi, what, integer=True):
    if v in (None, ""):
        return None
    x = float(str(v).replace(",", "."))
    if integer:
        x = int(x)
    if not lo <= x <= hi:
        raise ValueError(f"{what} must be between {lo} and {hi}.")
    return x


def known_ids():
    """Ids a call-up may contain: the players of the league (hidden ones too) and the players outside it."""
    import stats
    return {p["id"] for p in stats.build(keep_hidden=True)["players"]} | set(load()["externals"])


def set_callup(ids, label="", label_fr="", date=""):
    ids = [str(x) for x in ids]
    if len(set(ids)) != len(ids):
        raise ValueError("A player is listed twice.")
    unknown = [x for x in ids if x not in known_ids()]
    if unknown:
        raise ValueError("Unknown player: " + ", ".join(unknown))
    if len(ids) > 40:
        raise ValueError("Too many players in the list.")
    day = date and time.strftime("%Y-%m-%d", time.strptime(str(date)[:10], "%Y-%m-%d"))

    def fn(adm):
        adm["callup"] = {"label": str(label or "")[:120], "label_fr": str(label_fr or "")[:120], "date": day or "", "players": ids}
    _edit(fn)


def reset_callup():
    """Back to the list that ships with the code."""
    _edit(lambda adm: adm.pop("callup", None))


def save_external(b):
    """Create or change a player who is not in the Tunisian league. Body: name, birth, height, position, club, nationality, note_en, note_fr, key (to change one)."""
    name = " ".join(str(b.get("name") or "").split())
    if not name:
        raise ValueError("Type his name.")
    key = str(b.get("key") or "") or slugify(name)
    if not SLUG.match(key) or LEAGUE_ID.match(key):
        raise ValueError("Pick another name: this one cannot be used as an address.")
    e = {"name": name}
    if b.get("birth"):
        e["birth"] = time.strftime("%Y-%m-%d", time.strptime(str(b["birth"])[:10], "%Y-%m-%d"))
    h = _num(b.get("height"), 140, 235, "Height")
    if h:
        e["height"] = h
    for f in ("position", "club"):
        if str(b.get(f) or "").strip():
            e[f] = str(b[f]).strip()[:60]
    nat = countries.clean(b.get("nationality"))
    if nat:
        e["nationality"] = nat
    for f in ("note_en", "note_fr", "src"):
        if str(b.get(f) or "").strip():
            e[f] = str(b[f]).strip()[:600]
    if isinstance(b.get("career"), list):
        e["career"] = b["career"]

    def fn(adm):
        old = {**(_read(ASSET).get("externals") or {}).get(key, {}), **((adm.get("externals") or {}).get(key) or {})}
        if "career" not in e and old.get("career"):
            e["career"] = old["career"]                      # the admin form does not edit the career lines: keep the shipped ones
        if "photo" in old:
            e["photo"] = old["photo"]
        adm.setdefault("externals", {})[key] = e
    _edit(fn)
    return key


def delete_external(key):
    def fn(adm):
        adm.setdefault("externals", {})[key] = None
        adm["callup"] = adm.get("callup") or {**(_read(ASSET).get("callup") or {})}
        adm["callup"]["players"] = [x for x in adm["callup"].get("players") or [] if x != key]
    _edit(fn)


def add_competition(en, fr=""):
    en = " ".join(str(en or "").split())
    if not en:
        raise ValueError("Type the name of the competition.")
    cid = slugify(en)[:30]
    if not cid:
        raise ValueError("Type the name of the competition.")

    def fn(adm):
        if any(c["id"] == cid for c in load()["competitions"]):
            raise ValueError("This competition is already in the list.")
        adm.setdefault("competitions", []).append({"id": cid, "en": en, "fr": " ".join(str(fr or en).split()), "admin": True})
    _edit(fn)
    return cid


def delete_competition(cid):
    """Only a competition of the admin, and only when no game uses it."""
    d = load()
    if not any(c["id"] == cid and c.get("admin") for c in d["competitions"]):
        raise ValueError("Only a competition you added can be removed.")
    if any(g.get("competition") == cid for g in d["games"]):
        raise ValueError("Games still use this competition: remove them first.")
    _edit(lambda adm: adm.update(competitions=[c for c in adm.get("competitions") or [] if c.get("id") != cid]))


def clean_game(b, old=None):
    """A game from the admin's form (see the module doc)."""
    d = load()
    comp = str(b.get("competition") or "")
    if comp not in {c["id"] for c in d["competitions"]}:
        raise ValueError("Pick a competition.")
    date = time.strftime("%Y-%m-%d", time.strptime(str(b.get("date") or "")[:10], "%Y-%m-%d"))
    opp_txt = " ".join(str(b.get("opp_name") or b.get("opp") or "").split())
    if not opp_txt:
        raise ValueError("Type the opponent.")
    code = countries.lookup(opp_txt)
    if code == "TN":
        raise ValueError("The opponent cannot be Tunisia.")
    site = str(b.get("site") or "neutral")
    if site not in SITES:
        raise ValueError("Home, away or neutral ground?")
    tun, opp = _num(b.get("tun"), 0, 250, "Tunisia's score"), _num(b.get("opp_score"), 0, 250, "The opponent's score")
    if (tun is None) != (opp is None):
        raise ValueError("Type both scores, or none while the game is to come.")
    if tun is not None and tun == opp:
        raise ValueError("A basketball game has a winner: check the scores (overtime is included).")
    t = str(b.get("time") or "").strip()
    if t and not re.fullmatch(r"([01]?\d|2[0-3])[:hH][0-5]\d", t):
        raise ValueError("The time is HH:MM, for example 18:30.")
    g = {"competition": comp, "date": date, "opp": code, "opp_name": countries.COUNTRIES[code][0] if code else opp_txt, "site": site, "venue": str(b.get("venue") or "").strip()[:80],
         "round": str(b.get("round") or "").strip()[:80], "tun": tun, "opp_score": opp, "ot": _num(b.get("ot"), 0, 6, "Overtime") or 0}
    if t:
        n = re.split(r"[:hH]", t)
        g["time"] = f"{int(n[0]):02d}:{n[1]}"
    if (old or {}).get("box"):
        g["box"] = old["box"]
    if old and old.get("check") and not b.get("confirmed"):
        g["check"] = True
    return g


def save_game(b):
    """Create (no id) or change (id) a game. Returns its id."""
    gid = str(b.get("id") or "")
    old = next((g for g in load()["games"] if g["id"] == gid), None) if gid else None
    if gid and not old:
        raise ValueError("Unknown game.")
    g = clean_game(b, old)
    if not gid:
        gid = "g" + format(int(time.time() * 1000) % (16 ** 8), "08x")

    def fn(adm):
        adm.setdefault("games", {})[gid] = g
        adm["hidden_games"] = [x for x in adm.get("hidden_games") or [] if x != gid]
    _edit(fn)
    return gid


def delete_game(gid):
    d = load()
    if not any(g["id"] == gid for g in d["games"]):
        raise ValueError("Unknown game.")

    def fn(adm):
        (adm.get("games") or {}).pop(gid, None)
        if any(g.get("id") == gid for g in (_read(ASSET).get("games") or [])):
            adm["hidden_games"] = sorted({*(adm.get("hidden_games") or []), gid})        # a game that ships with the code is hidden, not erased
    _edit(fn)


# ---------------------------------------------------------------- box scores and statistics typed or pasted by the admin
NUM = re.compile(r"^-?\d+([.,]\d+)?$|^\d{1,2}:\d{2}$")
ALIASES = {"min": "min", "mins": "min", "minutes": "min", "mn": "min", "pts": "pts", "pt": "pts", "points": "pts", "pp": "pts", "reb": "reb", "rebs": "reb", "rebounds": "reb", "tr": "reb", "rebonds": "reb",
           "ast": "ast", "assists": "ast", "pd": "ast", "passes": "ast", "as": "ast", "stl": "stl", "steals": "stl", "int": "stl", "blk": "blk", "blocks": "blk", "ctr": "blk", "contres": "blk",
           "eff": "eff", "evaluation": "eff", "index": "eff", "to": "tov", "tov": "tov", "turnovers": "tov", "bp": "tov", "pf": "pf", "fouls": "pf", "fautes": "pf", "g": "g", "gp": "g", "games": "g", "mj": "g", "j": "g", "matchs": "g"}
NAME_HEADS = {"player", "players", "joueur", "joueurs", "name", "nom", "joueuse"}
BOX_ORDER = ("min", "pts", "reb", "ast", "stl", "blk", "tov", "pf")
SUMMARY_ORDER = ("g", "min", "pts", "reb", "ast", "eff")
MAX_ROWS = 40


def _cut(line):
    """The fields of a pasted line: split on tabs, semicolons, commas or bars when there are some, else on spaces."""
    s = line.strip()
    if re.search(r"[\t;|]", s):
        return [x.strip() for x in re.split(r"[\t;|]", s)]
    if re.search(r",\s*\S", s) and not re.search(r"\d,\d", s):
        return [x.strip() for x in s.split(",")]
    return s.split()


def _tok_num(tok):
    t = str(tok).strip().replace(",", ".")
    if re.fullmatch(r"\d{1,2}:\d{2}", t):
        m, s = t.split(":")
        return round(int(m) + int(s) / 60, 1)
    return float(t)


def parse_table(text, order):
    """A pasted table (CSV, tab separated from a spreadsheet, or lines like 'Omar Abada 33 18 4 5') -> [{name, <field>: number}]. A first line of column names ('Player MIN PTS REB AST')
    sets the order of the columns; without it `order` is the order. Lines with no number (headers, titles) are skipped. ValueError when nothing can be read."""
    rows, cols = [], None
    for line in str(text or "").splitlines():
        if not line.strip():
            continue
        parts = _cut(line)
        heads = [ALIASES.get(re.sub(r"[^a-z]", "", p.lower())) for p in parts]
        if cols is None and not rows and sum(1 for h in heads if h) >= 2 and not any(NUM.match(p) for p in parts):
            cols = [h for h in heads if h]                   # the names of the columns, the first column being the player
            continue
        i = next((k for k, p in enumerate(parts) if NUM.match(p) and k > 0), None)
        if i is None:
            continue
        name = " ".join(parts[:i]).strip(" .-")
        if not name or name.lower() in NAME_HEADS:
            continue
        try:
            nums = [_tok_num(p) for p in parts[i:] if NUM.match(p)]
        except ValueError:
            raise ValueError(f"Cannot read the numbers of: {line.strip()[:60]}")
        use = cols or order
        row = {"name": name}
        for k, f in enumerate(use):
            if k < len(nums):
                row[f] = nums[k]
        rows.append(row)
        if len(rows) > MAX_ROWS:
            raise ValueError("Too many lines.")
    if not rows:
        raise ValueError("No line with a name followed by numbers was found.")
    return rows


def _preview(rows, order):
    """Match each parsed line to a player (league or outside) and keep its numbers."""
    rep = match_report([r["name"] for r in rows])
    out = []
    for r, m in zip(rows, rep):
        out.append({**m, "values": {f: r.get(f) for f in order if r.get(f) is not None}})
    return out


def box_preview(text):
    return _preview(parse_table(text, list(BOX_ORDER)), BOX_ORDER)


def stats_preview(text):
    return _preview(parse_table(text, list(SUMMARY_ORDER)), SUMMARY_ORDER)


def _clean_values(v, order, limits):
    out = {}
    for f in order:
        x = v.get(f)
        if x in (None, ""):
            continue
        x = float(x)
        lo, hi = limits.get(f, (0, 200))
        if not lo <= x <= hi:
            raise ValueError(f"{f.upper()} must be between {lo} and {hi}.")
        out[f] = int(x) if x == int(x) and f != "min" else round(x, 1)
    return out


def set_box(gid, lines):
    """Store the box score of a game: lines [{pid or None, name, min, pts, reb, ast, stl, blk, tov, pf}]. Returns a warning when the points do not add up to Tunisia's score."""
    d = load()
    g = next((x for x in d["games"] if x["id"] == gid), None)
    if not g:
        raise ValueError("Unknown game.")
    if not _played(g):
        raise ValueError("Type the score of the game first.")
    known = known_ids()
    box, seen = [], set()
    for ln in lines or []:
        pid = ln.get("pid") or None
        if pid and pid not in known:
            raise ValueError(f"Unknown player {pid}.")
        if pid and pid in seen:
            raise ValueError("A player is in the box score twice.")
        seen.add(pid)
        v = _clean_values(ln, BOX_FIELDS, {"min": (0, 70), "pts": (0, 120), "reb": (0, 40), "ast": (0, 30), "stl": (0, 15), "blk": (0, 15), "tov": (0, 20), "pf": (0, 7)})
        box.append({**({"pid": pid} if pid else {"name": str(ln.get("name") or "")[:60]}), **v})
    if not box:
        raise ValueError("The box score is empty.")

    def fn(adm):
        base = {**g}
        base.pop("id", None)
        base["box"] = box
        adm.setdefault("games", {})[gid] = base
        adm["hidden_games"] = [x for x in adm.get("hidden_games") or [] if x != gid]
    _edit(fn)
    pts = sum(b.get("pts") or 0 for b in box)
    return None if pts == g["tun"] else f"The points of the box score add up to {pts}, the score is {g['tun']}: check the numbers (or a player is missing)."


def clear_box(gid):
    d = load()
    g = next((x for x in d["games"] if x["id"] == gid), None)
    if not g:
        raise ValueError("Unknown game.")

    def fn(adm):
        base = {**g}
        base.pop("id", None)
        base.pop("box", None)
        adm.setdefault("games", {})[gid] = base
    _edit(fn)


def set_stats(comp, rows, note=""):
    """Per-game totals of a competition typed without box scores: rows [{pid, g, min, pts, reb, ast}] replace the shipped ones of that competition."""
    if comp not in {c["id"] for c in load()["competitions"]}:
        raise ValueError("Pick a competition.")
    known, out, seen = known_ids(), [], set()
    for r in rows or []:
        pid = r.get("pid")
        if not pid or pid not in known:
            raise ValueError("Every line needs a known player: match the names first.")
        if pid in seen:
            raise ValueError("A player is listed twice.")
        seen.add(pid)
        v = _clean_values(r, SUMMARY_ORDER, {"g": (1, 60), "min": (0, 60), "pts": (0, 80), "reb": (0, 40), "ast": (0, 30), "eff": (-30, 80)})
        if "g" not in v:
            raise ValueError("Every line needs the number of games.")
        out.append({"pid": pid, **v})
    if not out:
        raise ValueError("No statistics to save.")
    _edit(lambda adm: adm.setdefault("stats", {}).__setitem__(comp, {"rows": out, "note": str(note or "")[:200]}))


def clear_stats(comp):
    _edit(lambda adm: (adm.get("stats") or {}).pop(comp, None))
