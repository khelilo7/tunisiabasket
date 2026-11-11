"""Box score compiled by hand from a broadcast video ("FULL TIME ... (from video).pdf", written by Tunisia Basket).

Same columns as an official FIBA sheet, with three differences: no date (only "Journée N"), minutes and +/- are estimates, and two extra rows hold what could not be
given to a player: "Player unknown" (shots whose shooter was not identified, turnovers) and "Team/Coach" (team rebounds). Those rows are not players: they never
enter a profile, so a team's totals on the site are the sum of its named players (a few misses and team rebounds short of the sheet's own totals line, and in rare cases
a few points: they are kept as not_attributed["pts"], and the points check of validate.py counts them).
The game is stored with source "video": a real box score of the same game (text or OCR) replaces it, and the match page says where it comes from.
"""
import re

import pdfplumber

from text_parser import ROW, STATS

MARKER = re.compile(r"compiled by tunisia basket|\(from video\)|broadcast video", re.I)
TEAM = re.compile(r"^(.+?)\s*\(\s*([A-Za-z]{2,5})\s*\)\s+Coach:\s*(.*)$")
NOTE = ("Compiled by Tunisia Basket from the broadcast video, not from the official table sheet: minutes and +/- are estimates, "
        "and a few missed shots, turnovers and team rebounds could not be given to a player.")


def is_video_sheet(path, page=0):
    with pdfplumber.open(path) as pdf:
        return bool(MARKER.search(pdf.pages[page].extract_text() or ""))


def _row_stats(rest):
    s = STATS.match(rest.replace(",", "."))
    if not s:
        raise ValueError(f"unparsable stats row: {rest}")
    g = [int(x) for x in s.groups()[:8]]
    tail = [int(x) for x in s.group(9).split()]
    if len(tail) != 12:                       # OR DR TOT AS TO ST BS PF FD +/- EF PTS
        raise ValueError(f"unexpected column count {len(tail)}: {rest}")
    return g, tail


def parse_video_sheet(path, page=0):
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[page].extract_text() or ""
    lines = [l.strip() for l in text.splitlines()]
    md = re.search(r"Journ[ée]e\s+(\d+)", text)
    comp = re.sub(r"\s*FIBA Box Score.*$", "", lines[0]).strip()
    teams, cur = [], None
    for ln in lines:
        h = TEAM.match(ln)
        if h:
            cur = {"code": h.group(2).upper(), "name": h.group(1).strip().title(), "coach": h.group(3).strip().title(), "players": [], "points": None,
                   "not_attributed": {"fga": 0, "pts": 0, "tov": 0, "team_reb": 0}}
            teams.append(cur)
            continue
        if cur is None:
            continue
        if ln.startswith("Totals"):
            cur["points"] = int(ln.split()[-1])
            cur = None
            continue
        if ln.startswith("Player unknown"):                      # "Player unknown (see notes) FG 2P 3P FT (made/att %) OR DR TOT AS TO ST BS PF FD +/-"
            ma = r"(\d+)/(\d+)\s+[\d.]+\s+"
            m = re.search(r"\)\s+" + ma * 4 + r"(.*)$", ln)
            if not m:
                raise ValueError(f"unparsable row: {ln}")
            fgm, fga, p2m, p2a, p3m, p3a, ftm, fta = (int(x) for x in m.groups()[:8])
            tail = [int(x) for x in m.group(9).split()]
            na = cur["not_attributed"]
            na["fga"] += fga
            na["pts"] += 2 * p2m + 3 * p3m + ftm                  # points scored by someone the video could not identify (they still count for the team)
            na["tov"] += tail[4]
            continue
        if ln.startswith("Team/Coach"):                           # "Team/Coach OR DR TOT TO"
            nums = [int(x) for x in ln.split()[1:]]
            cur["not_attributed"]["team_reb"] = nums[2] if len(nums) > 2 else 0
            cur["not_attributed"]["tov"] += nums[3] if len(nums) > 3 else 0
            continue
        m = ROW.match(ln)
        if not m:
            continue
        star, no, name, mins, rest = m.groups()
        captain = bool(re.search(r"\(C\)", name))
        name = re.sub(r"\s*\(C\)\s*", " ", name).strip()
        p = {"number": int(no), "name": name, "starter": bool(star), "captain": captain, "dnp": mins is None}
        if mins:
            g, tail = _row_stats(rest)
            oreb, dreb, reb, ast, tov, stl, blk, pf, fd, pm, ef, pts = tail
            mm, ss = mins.split(":")
            p.update(min=round(int(mm) + int(ss) / 60, 2), fgm=g[0], fga=g[1], p2m=g[2], p2a=g[3], p3m=g[4], p3a=g[5], ftm=g[6], fta=g[7], oreb=oreb,
                     dreb=dreb, reb=reb, ast=ast, tov=tov, stl=stl, blk=blk, pf=pf, fd=fd, pm=pm, pts=pts, _ef=ef)
        cur["players"].append(p)
    if len(teams) != 2 or any(t["points"] is None for t in teams):
        raise ValueError(f"expected 2 teams with a totals line, found {len(teams)}")
    game = {"competition": comp, "date": None, "teams": teams, "source": "video", "note": NOTE}
    if md:
        game["matchday_no"], game["matchday"] = int(md.group(1)), f"J{int(md.group(1))}"
    return game
