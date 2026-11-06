"""Exact, free parser for box-score PDFs that have a real text layer (most Genius Sports exports)."""
import datetime
import re

import pdfplumber

MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
ROW = re.compile(r"^(\*?)(\d{1,2})\s+(.+?)\s+(?:(\d{1,3}:\d{2})\s+(.*)|DNP)$")
MA = r"(\d+)/(\d+)\s+[\d.,]+"
STATS = re.compile(rf"^{MA}\s+{MA}\s+{MA}\s+{MA}\s+(.*)$")
# Long names wrap: "SURNAME Given" / "*6 10:50 stats..." / "Second Given". Row line has no name.
NAMELESS = re.compile(r"^(\*?)(\d{1,2})\s+(\d{1,3}:\d{2})\s+(.*)$")
NAMEPART = re.compile(r"^[A-Za-zÀ-ÿ'.()\- ]{1,40}$")
NOT_NAME = ("Team/Coach", "Totals", "Coach", "Field", "Legend", "No Name")
HEAD = re.compile(r"^(.+?)\s*\(\s*([A-Za-z0-9 ]{2,6}?)\s*\)​?\s+Assistant Coach")


def parse_text_pdf(path, page=0):
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[page].extract_text() or ""
    if len(text) < 300:
        return None
    lines = [l.strip() for l in text.splitlines()]

    dm = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(20\d\d)", text)
    if not dm:
        return None
    date = datetime.date(int(dm.group(3)), MONTHS[dm.group(2)], int(dm.group(1))).isoformat()
    comp = lines[0].replace("FIBA Box Score", "").strip()

    teams, cur = [], None
    prev_coach = ""
    skip = set()
    for i, ln in enumerate(lines):
        if i in skip:
            continue
        nl = NAMELESS.match(ln)
        if nl and cur is not None:
            before = lines[i - 1] if i and NAMEPART.match(lines[i - 1]) and not lines[i - 1].startswith(NOT_NAME) else ""
            after = ""
            if i + 1 < len(lines) and NAMEPART.match(lines[i + 1]) and not lines[i + 1].startswith(NOT_NAME):
                after = lines[i + 1]
                skip.add(i + 1)
            nm = f"{before} {after}".strip()
            if nm:
                ln = f"{nl.group(1)}{nl.group(2)} {nm} {nl.group(3)} {nl.group(4)}"
        if ln.startswith("Coach:"):
            prev_coach = re.sub(r"\(.*?\)", "", ln[6:]).strip()
            continue
        h = HEAD.match(ln)
        if h:
            cur = {"code": re.sub(r"\s+", "", h.group(2)).upper(), "name": h.group(1).strip().title(),
                   "coach": prev_coach.title(), "players": [], "points": None}
            teams.append(cur)
            continue
        if cur is None:
            continue
        if ln.startswith("Totals"):
            cur["points"] = int(ln.split()[-1])
            cur = None
            continue
        m = ROW.match(ln)
        if not m:
            continue
        star, no, name, mins, rest = m.groups()
        captain = bool(re.search(r"\(C\)", name))
        name = re.sub(r"\s*\(C\)\s*", " ", name).strip()
        # "DNP" rows may carry (C) after the name, e.g. "8 OMAR MOUHLI (C) DNP"
        p = {"number": int(no), "name": name, "starter": bool(star), "captain": captain, "dnp": mins is None}
        if mins:
            s = STATS.match(rest.replace(",", "."))
            if not s:
                raise ValueError(f"unparsable stats row: {ln}")
            g = [int(x) for x in s.groups()[:8]]
            tail = [int(x) for x in s.group(9).split()]
            if len(tail) == 12:      # OR DR TOT AS TO ST BS PF FD +/- EF PTS
                oreb, dreb, reb, ast, tov, stl, blk, pf, fd, pm, ef, pts = tail
            elif len(tail) == 11:    # same without EF
                oreb, dreb, reb, ast, tov, stl, blk, pf, fd, pm, pts = tail
                ef = None
            else:
                raise ValueError(f"unexpected column count {len(tail)}: {ln}")
            mm, ss = mins.split(":")
            p.update(min=round(int(mm) + int(ss) / 60, 2), fgm=g[0], fga=g[1], p2m=g[2], p2a=g[3], p3m=g[4], p3a=g[5],
                     ftm=g[6], fta=g[7], oreb=oreb, dreb=dreb, reb=reb, ast=ast, tov=tov, stl=stl, blk=blk,
                     pf=pf, fd=fd, pm=pm, pts=pts)
            if ef is not None:
                p["_ef"] = ef
        cur["players"].append(p)

    if len(teams) != 2:
        raise ValueError(f"expected 2 teams, found {len(teams)}")
    return {"competition": comp, "date": date, "teams": teams}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(parse_text_pdf(sys.argv[1]), indent=1, ensure_ascii=False))
