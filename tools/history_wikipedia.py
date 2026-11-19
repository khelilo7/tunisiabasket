"""Turn the Wikipedia pages of the past Pro A seasons into the site's history files (assets/history/seasons/<season>.json), and the list of champions (assets/history/champions.json).

    python tools/history_wikipedia.py DIR      DIR holds the wikitext of the pages, one .txt per page (see the NAMES below)

The pages are read as data, never copied as prose: the standings of each phase (wins and losses, points when given), the series of the play-offs with their game scores, the dates of the games
when the page has them, the champions and the finals. Every file says which page it comes from. What the pages do not have (the game by game results of the regular season) is not made up.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "history"

PAGES = {                       # file stem -> season
    "2014–15_Tunisian_Mens_Basketball_League": "2014-2015", "2019–20_Championnat_Pro_A": "2019-2020", "2021–22_Championnat_Pro_A": "2021-2022", "2022–23_Championnat_Pro_A": "2022-2023",
    "2023–24_Championnat_Pro_A": "2023-2024", "2024–25_Championnat_Pro_A": "2024-2025",
}
TITLE = {"2014-2015": "Tunisian Men's Basketball League 2014–15", "2019-2020": "Championnat Pro A 2019–20", "2021-2022": "Championnat National A 2021–22", "2022-2023": "Championnat Pro A 2022–23",
         "2023-2024": "Championnat Pro A 2023–24", "2024-2025": "Championnat Pro A 2024–25"}
CODES = {"us monastir": "USM", "monastir": "USM", "club africain": "CA", "es radès": "ESR", "étoile sportive de radès": "ESR", "es rades": "ESR", "es sahel": "ESS", "étoile du sahel": "ESS", "etoile sportive sahel": "ESS",
         "étoile sahel": "ESS", "js kairouan": "JSK", "js kairouanaise": "JSK", "stade nabeulien": "SN", "ezzahra sports": "EZS", "ezzahra": "EZS", "ds grombalia": "DSG", "dalia sport grombalia": "DSG",
         "dalia sportive de grombalia": "DSG", "grombalia": "DSG", "js menazah": "JSM", "js menzah": "JSM", "js menezah": "JSM", "js el menzah": "JSM", "us ansar": "USA", "ansar": "USA",
         "es goulettoise": "ESG", "es la goulette": "ESG", "eo goulette et kram": "ESG", "la goulette kram": "ESG", "bc mahdia": "BCM", "as hammamet": "ASH", "hammamet": "ASH", "ca bizertin": "CAB",
         "stade gabèsien": "SG", "ss sfaxien": "SSS", "club sportif des cheminots": "CSC", "gazelec sport de tunis": "GST", "sfax railways sports": "SRS"}
ALIAS_NAME = {"JSK": "JS Kairouan", "USM": "US Monastir", "ESR": "ES Radès", "ESS": "ES Sahel", "CA": "Club Africain", "SN": "Stade Nabeulien", "EZS": "Ezzahra Sports", "DSG": "DS Grombalia",
              "JSM": "JS Menazah", "USA": "US Ansar", "ESG": "ES Goulettoise", "BCM": "BC Mahdia", "ASH": "AS Hammamet", "CAB": "CA Bizertin", "SG": "Stade Gabèsien", "SSS": "SS Sfaxien"}


def clean(t):
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)
    return t.replace("'''", "").replace("''", "")


def team(name):
    n = re.sub(r"\s*\(\d+\)\s*$", "", re.sub(r"\s+", " ", name.strip().strip("|").strip()))
    code = CODES.get(n.lower())
    return {"code": code, "name": ALIAS_NAME.get(code, n) if code else n}


def sections(t):
    """[(heading path, body)] in page order."""
    out, path, pos, last = [], [], 0, None
    for m in re.finditer(r"^(={2,4})\s*([^=\n]+?)\s*\1\s*$", t, re.M):
        if last is not None:
            out.append((list(path), t[pos:m.start()]))
        lvl = len(m.group(1))
        path = path[:lvl - 2] + [m.group(2)]
        pos, last = m.end(), m.group(2)
    out.append((list(path), t[pos:]))
    return out


def template(body, start):
    """The text of the first {{...}} whose opening matches the regex `start` (braces are balanced, so a template on one line or on twenty both work), without the outer braces."""
    m = re.search(start, body)
    if not m:
        return None
    depth, i = 0, m.start()
    while i < len(body):
        if body.startswith("{{", i):
            depth += 1
            i += 2
        elif body.startswith("}}", i):
            depth -= 1
            i += 2
            if depth == 0:
                return body[m.start() + 2:i - 2]
        else:
            i += 1
    return None


def sports_table(body):
    """The rows of a {{#invoke:Sports table}}: [{team, w, l, pf, pa}] in table order."""
    tpl = template(body, r"\{\{#invoke:Sports table\|main")
    if not tpl:
        return None
    p = {k.strip(): v.strip() for k, v in re.findall(r"\|\s*([A-Za-z_]+[A-Za-z0-9_ -]*?)\s*=\s*([^|\n]*)", tpl)}
    codes = [v for k, v in sorted(p.items(), key=lambda kv: (len(kv[0]), kv[0])) if re.fullmatch(r"team\d+", k)]
    order = re.sub(r"\s", "", p.get("team_order", "")).split(",") if p.get("team_order") else codes
    rows = []
    for c in dict.fromkeys(order or re.findall(r"win_(\w+)", tpl)):
        if f"win_{c}" not in p:
            continue
        rows.append({**team(p.get(f"name_{c}", c)), "w": int(p[f"win_{c}"]), "l": int(p.get(f"loss_{c}", 0) or 0),
                     **({"pf": int(p.get(f"pf_{c}") or p.get(f"gf_{c}")), "pa": int(p.get(f"pa_{c}") or p.get(f"ga_{c}"))} if (p.get(f"pf_{c}") or p.get(f"gf_{c}")) not in (None, "", "0") else {})})
    if rows and all(set(r) == {"code", "name", "w", "l"} for r in rows) and len({r["w"] for r in rows}) > 1:
        rows.sort(key=lambda r: -r["w"])                                   # a few pages list the codes in another order than the table: wins decide
    return rows


def wiki_table(body):
    """A plain wikitable of standings: Pos / Team / Pts / P / W / L / PF / PA."""
    rows = []
    for line in re.findall(r"^\|\s*\d+\s*\|\|.*$", body, re.M):
        cells = [c.strip() for c in line.strip("|").split("||")]
        nums = [re.sub(r"[^\d+\-–]", "", c).replace("–", "-") for c in cells[2:9]]
        try:
            pts, gp, w, l, pf, pa = (int(x) for x in nums[:6])
        except ValueError:
            continue
        rows.append({**team(re.sub(r"^style=\"[^\"]*\"\|", "", cells[1])), "w": w, "l": l, "pf": pf, "pa": pa, "pts": pts})
    return rows or None


def brackets(body):
    """The series of a {{4TeamBracket}} / {{Team bracket}}: [{round, a, b, games:[[sa, sb]]}]."""
    tpl = template(body, r"\{\{(?:4TeamBracket|#invoke:Team bracket\|main)")
    if not tpl:
        return None
    p = dict(re.findall(r"\|\s*(RD\d-[a-z]+\d(?:-\d)?)\s*=\s*([^|\n]*)", tpl))
    out = []
    for rd in (1, 2, 3):
        for a, b in ((1, 2), (3, 4)):
            ta, tb = p.get(f"RD{rd}-team{a}"), p.get(f"RD{rd}-team{b}")
            if not ta or not tb:
                continue
            games = []
            for g in range(1, 8):
                sa, sb = p.get(f"RD{rd}-score{a}-{g}", "").strip(), p.get(f"RD{rd}-score{b}-{g}", "").strip()
                if sa.isdigit() and sb.isdigit():
                    games.append([int(sa), int(sb)])
            if games:
                s = {"round": {1: "Semi-finals", 2: "Final", 3: "Third place"}[rd] if "RD3-team1" in p or rd < 3 else "Final", "a": team(ta), "b": team(tb), "games": games}
                if len(games) == 1 and max(games[0]) > 130:                 # one box for a two-legged tie: the page gives the aggregate (2023-24 third place, 144-74), not a game
                    s["games"], s["aggregate"] = [], games[0]
                out.append(s)
    return out or None


def three_leg(body):
    out = []
    for m in re.finditer(r"\{\{ThreeLegResult\|([^|]*)\|\|[^|]*\|([^|]*)\|\|([^}]*)\}\}", body):
        a, b = team(m.group(1)), team(m.group(2))
        games = [[int(x), int(y)] for x, y in re.findall(r"(\d+)–(\d+)", m.group(3))]
        out.append({"a": a, "b": b, "games": games})
    return out or None


def round_n(body):
    out = []
    tpl = template(body, r"\{\{#invoke:RoundN\|main")
    if not tpl:
        return None
    block = 0
    seen_row = False
    for line in tpl.split("\n")[1:]:
        if not line.strip():
            block += seen_row
            seen_row = False
            continue
        f = line.split("|")
        if len(f) < 14:
            continue
        a, sa, b, sb = f[2], f[3:8], f[8], f[9:14]
        if not re.search(r"\(\d\)", a):
            continue
        seen_row = True
        games = [[int(x), int(y)] for x, y in zip(sa, sb) if x.strip().isdigit() and y.strip().isdigit()]
        out.append({"a": team(a), "b": team(b), "games": games, "block": block})
    if len(out) == 4 and all(x["block"] == 0 for x in out):                     # no blank lines: semi-finals, final, third place in that order
        for x, b in zip(out, (0, 0, 1, 1)):
            x["block"] = b
    # block 0 = semi-finals; block 1 = final (first row) and third-place game (second row)
    later = 0
    for x in out:
        if x.pop("block") == 0:
            x["round"] = "Semi-finals"
        else:
            x["round"] = ("Final", "Third place")[min(later, 1)]
            later += 1
    return out or None


def basketball_boxes(body):
    """Games with their date and score from {{Basketballbox}}: [{date, home, away, hs, as}]."""
    out = []
    for m in re.finditer(r"\{\{Basketballbox(.*?)\n\}\}", body, re.S):
        b = m.group(1)
        g = lambda k: (re.search(r"\|\s*%s\s*=\s*([^|\n]*)" % k, b) or [None, ""])[1].strip()
        date, t1, t2, s1, s2 = g("date"), g("team1"), g("team2"), g("score1"), g("score2")
        if t1 and t2 and s1.isdigit() and s2.isdigit():
            out.append({"date": date, "home": team(t1), "away": team(t2), "hs": int(s1), "as": int(s2)})
    return out or None


def infobox(t):
    t = clean(t)

    def f(*keys):
        for k in keys:
            m = re.search(r"\|\s*%s\s*=\s*([^\n|]*(?:\|[^\n=]*(?=\n))?)" % k, t)
            if m and m.group(1).strip():
                return re.sub(r"<br\s*/?>.*|\(\d+(?:st|nd|rd|th) title\)|\{\{.*|\}\}.*|\(basketball\)|\[\[|\]\]", "", m.group(1)).strip()
    return {"champion": f("champions", "finals_champ", "winners"), "runner_up": f("runners_up", "finals_runner-up"), "third": f("third_place"), "relegated": f("relegated", "relegate"),
            "teams": f("teams"), "dates": f("dates")}


def convert(stem, season, text):
    t = clean(text)
    phases = []
    for path, body in sections(t):
        name = " · ".join(path)
        if not path or path[0] in ("References", "Individual awards", "Foreign players", "Winning roster", "Teams", "External links"):
            continue
        entry = None
        rows = sports_table(body) or wiki_table(body)
        if rows:
            entry = {"name": name, "kind": "table", "rows": rows}
        series = brackets(body) or round_n(body) or three_leg(body)
        if series:
            entry = {"name": name, "kind": "series", "series": series}
        boxes = basketball_boxes(body)
        if boxes and not entry:
            entry = {"name": name, "kind": "games", "games": boxes}
        if entry:
            phases.append(entry)
    return {"season": season, "league": TITLE[season], "source": {"wikipedia": TITLE[season]}, **{k: v for k, v in infobox(text).items() if v}, "phases": phases}


def champions(text):
    t = clean(text)
    seasons = re.findall(r"^\*\s*(\d{4})–(\d{2,4}):\s*([^\n(]+?)\s*\((\d+)\)", t, re.M)
    finals = {}
    i = t.find("== Finals ==")
    for row in re.findall(r"\| align=\"center\" \|\s*(\d{4})–(\d{2})\s*\n\|\s*([^\n(|]+?)\s*(?:\(\d+\))?\s*\n\|\s*([^\n|]+?)\s*\n\| align=\"center\" \|\s*([\d–]+)", t[i:] if i > 0 else ""):
        finals[f"{row[0]}-{int(row[0]) + 1}"] = {"runner_up": row[3], "score": row[4].replace("–", "-")}
    out = []
    for y, _, name, _n in seasons:
        s = f"{y}-{int(y) + 1}"
        out.append({"season": s, "champion": team(name)["name"], "champion_code": team(name)["code"], **({"final": finals[s]} if s in finals else {})})
    return out


def main():
    src = Path(sys.argv[1])
    (OUT / "seasons").mkdir(parents=True, exist_ok=True)
    for stem, season in PAGES.items():
        f = src / f"{stem}.txt"
        if f.exists():
            d = convert(stem, season, f.read_text())
            (OUT / "seasons" / f"{season}.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))
            print(season, len(d["phases"]), "phases:", [p["name"] for p in d["phases"]])
    c = src / "Championnat_Pro_A.txt"
    if c.exists():
        ch = champions(c.read_text())
        (OUT / "champions.json").write_text(json.dumps(ch, indent=1, ensure_ascii=False))
        print(len(ch), "champions;", sum(1 for x in ch if "final" in x), "with the final's score")


if __name__ == "__main__":
    main()
