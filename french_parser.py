"""Box scores printed by the French-language scorer software the FTBB used in 2017-19 ("Tirs / 2 Points / 3 Points / Lancers / Rebonds", teams marked 123 and 456).

A player row reads  `*4 MABROUK Mourad 24:50 2/11 18,18 1/3 33,33 1/8 12,5 0/0 0 0 0 0 0 1 1 0 2 0 11 5`:
minutes, FG, 2P, 3P, FT (each "made/attempted percent"), then OR DR TOT, AS, TO, ST, BS, PF, FD, +/-, PTS.
The sheet gives the date as "mer. 03 oct. 2018", the score as "123 82-62 456" and the quarters as "(20-10, 18-17, 25-15, 19-20)".
"""
import datetime
import re

import pdfplumber

MONTHS = {"janv": 1, "jan": 1, "févr": 2, "fevr": 2, "fév": 2, "fev": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}
NUM = r"-?\d+"
MA = r"(\d+)/(\d+)\s+[\d.,]+"
ROW = re.compile(rf"^(\*?)(\d{{1,2}})\s+(.+?)\s+(\d{{1,3}}):(\d{{2}})\s+{MA}\s+{MA}\s+{MA}\s+{MA}\s+((?:{NUM}\s+){{10,11}}{NUM})\s*$")
# the third French sheet has no 2-point column: "4 HADIDDANE ANIS 15:58 0/2 0 0/2 0 0/0 0 | 0 5 5 | 0 1 0 0 0 2 1 -11 0 1" = FG, 3P, FT, OR DR TOT, AS TO ST BS BS-against PF FD +/- PTS EF
# (its EF is the usual one plus the fouls drawn minus the personal fouls and the blocks against; its "Totaux" line ends with the sum of EF, so the team's points are read from the score line)
ROW_C = re.compile(rf"^(\*?)(\d{{1,2}})\s+(.+?)\s+(\d{{1,3}}):(\d{{2}})\s+{MA}\s+{MA}\s+{MA}\s+((?:{NUM}\s+){{12}}{NUM})\s*$")
SCORE_LINE = re.compile(r"^(?!.*Match)(.+?)\s+(\d{2,3})\s*-\s*(\d{2,3})\s+(.+?)\s*$")
TEAM = re.compile(r"^([123456]{3}|[A-Z][A-Z .]{1,5}?)\s+-\s+(.+?)\s*$")                                                   # "123 - Etoile sportive de radès"
TEAM_CODE = re.compile(r"^(.+?)\s*\(([A-Za-z0-9 ]{2,6})\)\W*\s*Entra[iî]neur\(s\)")                           # "Ez-zahra Sport (EZS) Entraîneur(s) Adjoints(s):"
DNP = re.compile(r"^(\*?)(\d{1,2})\s+(.+?)\s+(?:NPJ|DNP)$")
# a long name wraps around its row: "MARMOUCH MOHAMED" / "*6 36:30 7/11 ..." / "YASSINE (C)"
NAMELESS = re.compile(r"^(\*?)(\d{1,2})\s+(\d{1,3}:\d{2})\s+(.*)$")
NAMEPART = re.compile(r"^[A-Za-zÀ-ÿ'.()\- ]{1,40}$")
NOT_NAME = ("Equipe", "Totaux", "Entraîneur", "Tirs", "No ", "R/T")


def unwrap(lines):
    """The lines with every wrapped name put back in its row."""
    out, skip = [], False
    part = lambda l: bool(NAMEPART.match(l)) and not l.startswith(NOT_NAME)
    for i, ln in enumerate(lines):
        if skip:
            skip = False
            continue
        m = NAMELESS.match(ln)
        if m:
            before = out.pop() if out and part(out[-1]) else ""
            after = lines[i + 1] if i + 1 < len(lines) and part(lines[i + 1]) else ""
            skip = bool(after)
            name = f"{before} {after}".strip()
            if name:
                ln = f"{m.group(1)}{m.group(2)} {name} {m.group(3)} {m.group(4)}"
        out.append(ln)
    return out
CODES = [("monastir", "USM"), ("sahel", "ESS"), ("rad", "ESR"), ("africain", "CA"), ("kairouan", "JSK"), ("nabeul", "SN"), ("ezzahra", "EZS"), ("grombalia", "DSG"), ("menzah", "JSM"),
         ("menazeh", "JSM"), ("manzah", "JSM"), ("manazeh", "JSM"), ("ansar", "USA"), ("goulet", "ESG"), ("mahdia", "BCM"), ("hammamet", "ASH"), ("bizert", "CAB"), ("gab", "SG"), ("sfax", "SSS"), ("marsa", "ASM"), ("cheminot", "CSC")]
KNOWN = {c for _, c in CODES} | {"SN", "CA", "ESS", "ESR", "USM"}      # the clubs of the league: a game with another team (a national U23 side, a misread code) is never stored
ALIAS = {"SNN": "SN", "DGS": "DSG", "USMO": "USM", "JM": "JSM", "SN": "SN", "ENU23": "EN", "ENT": "EN"}


def code_of(name):
    low = name.lower()
    for key, code in CODES:
        if key in low:
            return code
    return re.sub(r"[^A-Z]", "", name.upper())[:3] or "UNK"


def is_french(text):
    return "Rebonds" in text and "Tirs" in text and "Totaux" in text and (bool(re.search(r"^123\s*-", text, re.M)) or bool(TEAM_CODE.search(text.replace("\u200b", ""))) or "Entraîneur(s)" in text or bool(re.search(r"^[A-Z][A-Z .]{1,5} - ", text, re.M)))


# the 2016-17 "Statistiques-Match Entier" sheet: FG, 3P, FT, OR DR TOT, AS TO ST, blocks made / against, fouls committed / drawn, PTS, EF (its EF column is not fully consistent with its own columns, so it is not used as a check)
ROW_E = re.compile(rf"^(\*?)\s*(\d{{1,2}})\s+(.+?)\s+(\d{{1,3}}):(\d{{2}})\s+{MA}\s+{MA}\s+{MA}\s+((?:{NUM}\s+){{11}}{NUM})\s*$")
DNP_E = re.compile(r"^(\*?)\s*(\d{1,2})\s+(.+?)\s+DNP\b")


def parse_match_entier(text):
    lines = [l.strip() for l in text.splitlines()]
    dm = re.search(r"Date:\s*(\d{2})/(\d{2})/(20\d\d)", text)
    date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else None
    teams, cur = [], None
    for i, ln in enumerate(lines):
        if re.fullmatch(r"[A-Z][A-Z0-9. ]{1,7}", ln) and i + 1 < len(lines) and lines[i + 1].startswith("Tirs"):
            cur = {"code": canon(ln, ln), "name": ln, "coach": "", "players": [], "points": None}
            teams.append(cur)
            continue
        if cur is None:
            continue
        if ln.startswith("Total ") and "Equipe" not in ln:
            cur["points"] = int(ln.split()[-2])
            cur = None
            continue
        d = DNP_E.match(ln)
        if d and "(" not in ln.split("DNP")[0][-1:]:
            cur["players"].append({"number": int(d.group(2)), "name": re.sub(r"\s*\(C\)\s*", " ", d.group(3)).strip(), "starter": bool(d.group(1)), "captain": "(C)" in d.group(3), "dnp": True})
            continue
        m = ROW_E.match(ln.replace(",", "."))
        if not m:
            continue
        g = m.groups()
        fgm, fga, p3m, p3a, ftm, fta = (int(x) for x in g[5:11])
        oreb, dreb, reb, ast, tov, stl, blk, blk_ag, pf, fd, pts, ef = (int(x) for x in g[11].split())
        cur["players"].append({"number": int(g[1]), "name": re.sub(r"\s*\(C\)\s*", " ", g[2]).strip(), "starter": bool(g[0]), "captain": "(C)" in g[2], "dnp": False, "min": round(int(g[3]) + int(g[4]) / 60, 2),
                               "fgm": fgm, "fga": fga, "p2m": fgm - p3m, "p2a": fga - p3a, "p3m": p3m, "p3a": p3a, "ftm": ftm, "fta": fta, "oreb": oreb, "dreb": dreb, "reb": reb, "ast": ast, "tov": tov,
                               "stl": stl, "blk": blk, "pf": pf, "fd": fd, "pm": None, "pts": pts})
    if len(teams) != 2:
        raise ValueError(f"expected 2 teams, found {len(teams)}")
    return {"competition": "", "date": date, "teams": teams}


def parse_french_pdf(path, page=0):
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[page].extract_text() or ""
    if "Statistiques-Match Entier" in text:
        return parse_match_entier(text)
    if not is_french(text):
        return None
    lines = unwrap([l.strip().replace("\u200b", "") for l in text.splitlines()])
    dm = re.search(r"(\d{1,2})\s+([A-Za-zéûô]+)\.?\s+(20\d\d)", text)
    date = None
    if dm and dm.group(2).lower() in MONTHS:
        date = datetime.date(int(dm.group(3)), MONTHS[dm.group(2).lower()], int(dm.group(1))).isoformat()
    score = re.search(r"123\s+(\d+)-(\d+)\s+456", text)
    teams, cur = [], None
    prev_coach = ""
    for ln in lines:
        t = TEAM.match(ln)
        tc = None if t else TEAM_CODE.match(ln)
        if t or tc:
            name = (t.group(2) if t else tc.group(1)).strip()
            code = (code_of(name) if t.group(1).isdigit() else re.sub(r"[\s.]+", "", t.group(1)).upper()) if t else re.sub(r"[\s.]+", "", tc.group(2)).upper()
            cur = {"code": code, "name": name.title(), "coach": prev_coach if tc else "", "players": [], "points": None}
            teams.append(cur)
            continue
        if ln.startswith("Entraîneur:") and cur is None:
            prev_coach = ln.split(":", 1)[1].strip().title()
        if cur is None:
            continue
        if ln.startswith("Entraîneur:") and not cur["coach"]:
            cur["coach"] = ln.split(":", 1)[1].strip().title()
        if ln.startswith("Totaux"):
            cur["points"] = int(ln.split()[-1])
            cur = None
            continue
        d = DNP.match(ln)
        if d:
            cur["players"].append({"number": int(d.group(2)), "name": re.sub(r"\s*\(C\)\s*", " ", d.group(3)).strip(), "starter": bool(d.group(1)), "captain": "(C)" in d.group(3), "dnp": True})
            continue
        m = ROW.match(ln.replace(",", "."))
        if not m:
            mc = ROW_C.match(ln.replace(",", "."))
            if mc:
                gc = mc.groups()
                fgm, fga, p3m, p3a, ftm, fta = (int(x) for x in gc[5:11])
                oreb, dreb, reb, ast, tov, stl, blk, blk_against, pf, fd, pm, pts, ef = (int(x) for x in gc[11].split())
                cur["layout_c"] = True
                cur["players"].append({"number": int(gc[1]), "name": re.sub(r"\s*\(C\)\s*", " ", gc[2]).strip(), "starter": bool(gc[0]), "captain": "(C)" in gc[2], "dnp": False,
                                       "min": round(int(gc[3]) + int(gc[4]) / 60, 2), "fgm": fgm, "fga": fga, "p2m": fgm - p3m, "p2a": fga - p3a, "p3m": p3m, "p3a": p3a, "ftm": ftm, "fta": fta,
                                       "oreb": oreb, "dreb": dreb, "reb": reb, "ast": ast, "tov": tov, "stl": stl, "blk": blk, "pf": pf, "fd": fd, "pm": pm, "pts": pts, "_ef": ef + pf - fd + blk_against})
            continue
        g = m.groups()
        star, no, name, mm, ss = g[0], int(g[1]), g[2], int(g[3]), int(g[4])
        fgm, fga, p2m, p2a, p3m, p3a, ftm, fta = (int(x) for x in g[5:13])
        tail = [int(x) for x in g[13].split()]
        ef = tail.pop(-2) if len(tail) == 12 else None                 # "... +/- EF PTS" on the sheets that print the evaluation
        oreb, dreb, reb, ast, tov, stl, blk, pf, fd, pm, pts = tail
        captain = bool(re.search(r"\(C\)", name))
        cur["players"].append({"number": no, "name": re.sub(r"\s*\(C\)\s*", " ", name).strip(), "starter": bool(star), "captain": captain, "dnp": False,
                               "min": round(mm + ss / 60, 2), "fgm": fgm, "fga": fga, "p2m": p2m, "p2a": p2a, "p3m": p3m, "p3a": p3a, "ftm": ftm, "fta": fta,
                               "oreb": oreb, "dreb": dreb, "reb": reb, "ast": ast, "tov": tov, "stl": stl, "blk": blk, "pf": pf, "fd": fd, "pm": pm, "pts": pts, **({"_ef": ef} if ef is not None else {})})
    if len(teams) != 2:
        raise ValueError(f"expected 2 teams, found {len(teams)}")
    if any(t.pop("layout_c", False) for t in teams):
        sl = next((SCORE_LINE.match(l) for l in lines[:14] if SCORE_LINE.match(l) and "Durée" not in l and "Tirs" not in l), None)
        if sl:
            teams[0]["points"], teams[1]["points"] = int(sl.group(2)), int(sl.group(3))
    if score and teams[0]["points"] is None:
        teams[0]["points"], teams[1]["points"] = int(score.group(1)), int(score.group(2))
    game = {"competition": lines[1] if len(lines) > 1 else "", "date": date, "teams": teams}
    q = re.search(r"\((\d+-\d+(?:,\s*\d+-\d+)+)\)", text)
    if q:
        game["quarters"] = [[int(a), int(b)] for a, b in (x.strip().split("-") for x in q.group(1).split(","))]
    return game


def canon(code, name):
    """The site's code for a club: found from its name when the name is a known club, else the printed code (dots and spaces removed, a few misprints mapped)."""
    low = (name or "").lower()
    for key, c in CODES:
        if key in low:
            return c
    c = re.sub(r"[\s.]+", "", code or "").upper()
    return ALIAS.get(c, c)
