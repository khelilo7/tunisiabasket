"""The team lines of a box score: points in the paint, second-chance points, fast-break points, points off turnovers, bench points.

They are printed under the player tables of a federation sheet and of the sheets Tunisia Basket compiles ("Points in the Paint 24 (12/25) 48,0  34 (17/35) 48,6", the first number
is the first team of the sheet). A game keeps them per team as `team["extra"]`:  {"paint": 24, "second": 6, "fast": 5, "tov_pts": 18, "bench": 25}  (a key is left out when
the sheet does not give it). The analyst board produces the same five numbers from its tags (analytics.team_extra), so every source ends in one shape.
"""
import re

KEYS = ("paint", "second", "fast", "tov_pts", "bench")
LABEL = {"paint": "Points in the paint", "second": "Second-chance points", "fast": "Fast-break points", "tov_pts": "Points off turnovers", "bench": "Bench points"}
# one pattern per line; the line must START with its label (a "Fast Break Points from Turnovers" line is another statistic, never read as "Points from Turnovers")
_LINES = {
    "paint": r"^Points in the Paint\s+(\d+)(?:\s*\(\d+/\d+\)\s*[\d,.]+%?)?\s+(\d+)",
    "second": r"^Second Chance Points\s+(\d+)\s+(\d+)",
    "fast": r"^Fast Break Points\s+(\d+)\s+(\d+)",
    "tov_pts": r"^Points from Turnovers\s+(\d+)\s+(\d+)",
    "bench": r"^Bench Points\s+(\d+)\s+(\d+)",
}


def parse(text, codes=None):
    """{first team: {...}, second team: {...}} from the text of a sheet (empty when the sheet has none of the lines). `codes` are the two team codes in the order of the player
    tables; when None, the order is kept as ("first", "second")."""
    first, second = {}, {}
    for key, pat in _LINES.items():
        m = re.search(pat, text, re.M)
        if m:
            first[key], second[key] = int(m.group(1)), int(m.group(2))
    if not first:
        return {}
    a, b = codes or ("first", "second")
    return {a: first, b: second}


def attach(game, text):
    """Put the lines of `text` on the two teams of `game` (same order as the player tables). Returns how many teams got something."""
    found = parse(text, [t["code"] for t in game["teams"]])
    for t in game["teams"]:
        if found.get(t["code"]):
            t["extra"] = found[t["code"]]
    return len(found)


def clean(extra):
    """A trusted copy of a team's extra lines: only the five known keys, whole numbers 0-250."""
    out = {}
    for k in KEYS:
        v = (extra or {}).get(k)
        if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 250:
            out[k] = v
    return out
