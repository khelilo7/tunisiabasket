"""Season pages of the French Wikipedia ("Championnat de Tunisie masculin de basket-ball 2016-2017" ...) -> assets/history/seasons/<season>.json.

    python tools/history_wikifr.py DIR        # DIR holds <season>.txt (the wikitext), e.g. 2016-2017.txt

The French pages carry what the English ones lack for 2016-2021: both groups of the first phase, the play-off and play-out tables, every score of the round-robin phases
(a "Basket résultat" matrix: the row team's score and the column team's score of the game the row team hosted, first leg then second leg), the barrage ties and the super play-off
series game by game. A season already written by history_wikipedia.py is completed, not replaced: phases that the English page also gave are kept as they are.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history_wikipedia as hw  # noqa: E402

OUT = hw.OUT
CODES = {**hw.CODES, "es goulettoise": "ESG", "étoile sportive goulettoise": "ESG", "étoile olympique la goulette kram": "ESG", "eo goulette": "ESG", "ca bizertin": "CAB", "club athlétique bizertin": "CAB",
         "js menzah": "JSM", "jeunesse sportive d'el menzah": "JSM", "js el menzah": "JSM", "jeunesse sportive kairouanaise": "JSK", "union sportive monastirienne": "USM", "étoile sportive du sahel": "ESS",
         "étoile sportive de radès": "ESR", "association sportive d'hammamet": "ASH", "as hammamet": "ASH", "stade nabeulien": "SN", "union sportive el ansar": "USA", "us el ansar": "USA", "ezzahra sports": "EZS",
         "dalia sportive de grombalia": "DSG", "ds grombalia": "DSG", "club sportif des cheminots": "CSC", "cs cheminots": "CSC", "stade gabésien": "SG", "stade sportif sfaxien": "SSS", "basket club mahdia": "BCM",
         "bc mahdia": "BCM", "club africain": "CA", "us monastir": "USM", "es radès": "ESR", "es sahel": "ESS", "js kairouan": "JSK", "us ansar": "USA", "ca": "CA", "esr": "ESR", "ess": "ESS", "jsk": "JSK", "sn": "SN",
         "usm": "USM", "usmo": "USM", "asm": "ASM", "as la marsa": "ASM", "avenir sportif de la marsa": "ASM", "jsmz": "JSM", "ash": "ASH", "csc": "CSC", "dsg": "DSG", "esg": "ESG", "ezs": "EZS", "jsm": "JSM", "sg": "SG", "usa": "USA", "bcm": "BCM", "cab": "CAB"}
hw.CODES.update(CODES)
team = hw.team


def plain(s):
    """wikitext -> text: links, bold, templates, <sup>, refs removed."""
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|<sup>.*?</sup>|<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return s.replace("'''", "").replace("''", "").strip()


def tname(raw):
    """A team cell -> {"code","name"}; '(+1)', '(barrage)', 'T' markers and seeds are dropped."""
    n = plain(raw)
    n = re.sub(r"\((?:\+\d|barrage|\d)\)", "", n)
    n = re.sub(r"[\s,]+$", "", n)
    n = re.sub(r"(?:\s+[TFPC])+$", "", n).strip()
    return team(n)


def standings(body):
    rows = []
    for m in re.finditer(r"\{\{Basket classement(?: type %)?\s*\|\s*(\d+)\s*\|([^|]+)\|([^|]*)\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)", body):
        rank, nm, pts, j, w, l, pf, pa = m.groups()
        t = tname(nm)
        row = {"rank": len(rows) + 1, **t, "j": int(j), "w": int(w), "l": int(j) - int(w)}   # rank by order (ties print the same number); a forfeit can print an odd 'lost' column
        if int(pf) or int(pa):
            row.update(pf=int(pf), pa=int(pa))
        if pts.strip().isdigit():
            row["pts"] = int(pts)
        rows.append(row)
    return rows or None


def matrix(body):
    """[{"home","away","hs","as","leg"}] from a 'Basket résultat' block: the row team hosted; each opponent column holds (row score, column score) for leg 1 then leg 2."""
    m = re.search(r"\{\{Basket résultat début\|(.*?)\}\}\s*\n(.*?)\{\{Basket résultat fin\}\}", body, re.S)
    if not m:
        return None
    cols = [tname(c)["code"] or plain(c) for c in re.split(r"\|", re.sub(r"\n.*", "", m.group(1)))]
    cols = [c for c in cols if c]
    out = []
    for row in re.findall(r"\{\{Basket résultat\|(.*?)\}\}", m.group(2)):
        cells = [c.strip() for c in row.split("|")]
        home = tname(cells[0])["code"] or plain(cells[0])
        vals = cells[1:]
        per = len(vals) // len(cols)                       # 2 numbers per opponent (one leg) or 4 (two legs)
        for i, opp in enumerate(cols):
            chunk = vals[i * per:(i + 1) * per]
            if opp == home or "XXX" in chunk or len(chunk) < 2:
                continue
            for leg in range(per // 2):
                a, b = chunk[leg * 2], chunk[leg * 2 + 1]
                if a.isdigit() and b.isdigit() and (int(a) or int(b)):
                    out.append({"home": home, "away": opp, "hs": int(a), "as": int(b)})
    return out or None


def dated_rows(body):
    """The 'date | home | score | away' blocks of the barrage and of 2017-18 semi-finals: [{"date","home","away","hs","as"}]."""
    out = []
    parts = re.split(r"\n\|-[^\n]*\n", "\n" + body)
    for blk in parts:
        cells = [c for c in re.split(r"\n\|", "\n" + blk.strip()) if c.strip()]
        if len(cells) < 4:
            continue
        cells = [re.sub(r'^[^|\n]*\|(?!\[)', "", c) if re.match(r"^(width|align)", c.strip()) else c for c in cells]
        date, home, score, away = cells[0], cells[1], cells[2], cells[3]
        m = re.search(r"(\d+)\D+?(\d+)", plain(score))
        if not m:
            continue
        out.append({"date_text": plain(date), "home": tname(home), "away": tname(away), "hs": int(m.group(1)), "as": int(m.group(2))})
    return out or None


def barrage_bullets(body):
    out = []
    for m in re.finditer(r"^\*\s*(Pour [^:]+):\s*(.+?)\s+-\s+(.+?)\s*\(([\d\-, ]+)\)\s*$", body, re.M):
        what, a, b, sc = m.groups()
        games = [[int(x), int(y)] for x, y in re.findall(r"(\d+)-(\d+)", sc)]
        out.append({"round": plain(what), "a": tname(a), "b": tname(b), "games": games})
    return out or None


def play_offs4(body):
    """{{Play-offs 4 Pro A - avec troisième v2 |1=dates |2=team A |3=wins |4,5 = site, score ...}}: semi-finals, final, third place."""
    tpl = hw.template(body, r"\{\{Play-offs 4 Pro A")
    if not tpl:
        return None
    p = {}
    for m in re.finditer(r"^\|\s*(\d+)\s*=(.*?)(?=^\|\s*\d+\s*=|\Z)", tpl, re.M | re.S):
        p[int(m.group(1))] = m.group(2)
    seq = [p[k] for k in sorted(p)]
    groups, cur = [], []
    for v in seq:
        if re.match(r"\s*(?:Lun|Mar|Mer|Jeu|Ven|Sam|Dim)\b", plain(v)):
            if cur:
                groups.append(cur)
            cur = [("date", plain(v))]
        elif cur or v.strip():
            cur.append(("site", None) if "Dom/Ext" in v else ("val", plain(v)))
    if cur:
        groups.append(cur)
    names = ["Semi-finals", "Semi-finals", "Final", "Third place"]
    out = []
    for gi, g in enumerate(groups):
        if gi >= len(names):
            break
        toks = [t for t in g if t[0] != "date"]
        sides, i = [], 0
        while i < len(toks) and len(sides) < 2:                       # name, wins, then (site, score) pairs until the next name
            k, v = toks[i]
            if k == "val" and re.search(r"[A-Za-zÀ-ÿ]", v) and "orfait" not in v:
                nm, i = v, i + 1
                wins = int(toks[i][1]) if i < len(toks) and toks[i][1].isdigit() else None
                i += 1
                scores = []
                while i < len(toks):
                    if toks[i][0] == "site":
                        v = toks[i + 1][1] if i + 1 < len(toks) and toks[i + 1][0] == "val" else ""
                        scores += re.findall(r"\d+", v) if "/" in v else [v]       # "78 / 77": two games in one cell
                        i += 2
                    elif toks[i][0] == "val" and not re.search(r"[A-Za-zÀ-ÿ]", toks[i][1]) :
                        i += 1
                    else:
                        break
                sides.append((nm, wins, scores))
            else:
                i += 1
        if len(sides) < 2:
            continue
        (na, wa, sa), (nb, wb, sb) = sides
        games = [[int(x), int(y)] for x, y in zip(sa, sb) if x.isdigit() and y.isdigit()]
        s = {"round": names[gi], "a": tname(na), "b": tname(nb), "games": games}
        if wa is not None and wb is not None:
            s["wins"] = [wa, wb]
        if any("orfait" in x for x in sa + sb):
            s["note"] = "Forfeit"
        out.append(s)
    return out or None


def infobox(t):
    def f(key):
        m = re.search(r"\|\s*%s\s*=\s*([^\n]*)" % key, t)
        return plain(re.sub(r"<br\s*/?>.*", "", m.group(1))) if m and m.group(1).strip() else None
    out = {"champion": f("vainqueur"), "relegated": f("relégué fin"), "teams": f("participants")}
    return {k: re.sub(r"\s*\(\d+\)", "", v) for k, v in out.items() if v and not v.startswith("|")}


SKIP = ("Clubs participants", "Champion", "Autres", "Notes et références", "Références", "Récompenses individuelles", "MVPs par journée")


FR_MONTHS = {m: i for i, m in enumerate("janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split(), 1)}


def iso_date(text, season):
    """'3 février' in the season 2017-2018 -> '2018-02-03' (August to December belong to the first year of the season)."""
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zéû]+)", text or "")
    if not m or m.group(2) not in FR_MONTHS:
        return None
    mo, y0 = FR_MONTHS[m.group(2)], int(season[:4])
    return f"{y0 if mo >= 8 else y0 + 1}-{mo:02d}-{int(m.group(1)):02d}"


def convert(season, text):
    phases = []
    for path, body in hw.sections(hw.clean(text)):
        if not path or path[0] in SKIP or path[-1] in SKIP:
            continue
        if path[-1] == "Deuxième phase" and re.search(r"^;Play-off", body, re.M):       # 2018-19: the second phase table is the play-off
            path = [*path, "Play-off"]
        name = " · ".join(x for x in path if x != "Compétition")
        if not name:
            continue
        entries = []
        rows = standings(body)
        if rows:
            entries.append({"name": name, "kind": "table", "rows": rows})
        games = matrix(body)
        if games:
            entries.append({"name": name, "kind": "games", "games": games})
        series = play_offs4(body) or hw.round_n(body) or barrage_bullets(body)
        if series:
            entries.append({"name": name, "kind": "series", "series": series})
        else:
            dr = dated_rows(body)
            if dr and re.search(r"barrage|Demi|Finale|Play", name, re.I):
                entries.append({"name": name, "kind": "games", "games": dr})
        for e in entries:
            for g in e.get("games", []):
                if "date_text" in g:
                    g["date"] = iso_date(g.pop("date_text"), season)
                    if not g["date"]:
                        del g["date"]
            first = next((g["date"] for g in e.get("games", []) if g.get("date")), None)
            for g in e.get("games", []):                         # a typo in the page ("14 février" for a game of April): a date before the first game of the round is dropped
                if first and g.get("date") and g["date"] < first:
                    del g["date"]
        phases += entries
    # the "Play-out" table directly followed by its matrix lives in one section: keep both entries (table + games)
    return {"season": season, **{k: v for k, v in infobox(text).items() if v}, "phases": phases}


def main():
    src = Path(sys.argv[1])
    for f in sorted(src.glob("*.txt")):
        season = f.stem
        d = convert(season, f.read_text())
        path = OUT / "seasons" / f"{season}.json"
        if path.exists() and json.loads(path.read_text()).get("phases") and "--force" not in sys.argv:
            print(season, "already built from the English page; kept (--force to replace)")
            continue
        path.write_text(json.dumps(d, indent=1, ensure_ascii=False))
        print(season, len(d["phases"]), [(p["name"], p["kind"]) for p in d["phases"]])


if __name__ == "__main__":
    main()
