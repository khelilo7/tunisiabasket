"""Build the Nationale 1 data file (season 2026-2027) from the federation's calendar grid, its table of 15 November and the results we know.

    python tools/build_nat1_seed.py [OUT.json]        (default exports/nat1_2026-2027.json)
    python tools/send_nat1.py --site https://tunisiabasket.com exports/nat1_2026-2027.json

The calendar (CALENDRIER-DE-COMPETITIONS-NATIONALE-1-SENIORS-GARCONS.pdf) is a grid: one row per round, six boxes, each box two clubs, the upper one at home (first leg, rounds 1-11);
the second leg (rounds 12-22) has its own dates, and its pairings are the first leg's with home and away swapped: that part is flagged "projected" until the federation publishes it.
A "-" is a rest (11 clubs: one club rests every round). Results: only scores we really have (FTBB, SportScore, or told to us); a game without a score is shown as "score missing"; nothing is guessed.
"""
import json
import sys
from pathlib import Path

TEAMS = {"EZS": "Ezzahra Sport", "CAK": "Club Athletique Keffois", "ASM": "Avenir Sportif de La Marsa", "BCM": "Basket Club Mahdia", "SSS": "Stade Sportif Sfaxien", "JAB": "JA Bougatfa",
         "AMS": "AS Megrine", "CAB": "Club Athletique Bizertin", "CSGN": "Club Sportif de la Garde Nationale", "BS": "Bardo Sport", "CBM": "Club Basket M'saken"}
# round: (date, [(home, away) x 6 boxes])
FIRST_LEG = {
    1: ("2026-10-24", [("EZS", "CAK"), ("ASM", "BCM"), ("SSS", "JAB"), ("AMS", "CAB"), ("CSGN", "BS"), ("CBM", "-")]),
    2: ("2026-10-31", [("BCM", "EZS"), ("CAK", "ASM"), ("JAB", "AMS"), ("CAB", "SSS"), ("BS", "CBM"), ("-", "CSGN")]),
    3: ("2026-11-07", [("EZS", "JAB"), ("ASM", "CAB"), ("SSS", "BS"), ("AMS", "-"), ("CSGN", "CAK"), ("CBM", "BCM")]),
    4: ("2026-11-14", [("CAB", "EZS"), ("JAB", "ASM"), ("BCM", "AMS"), ("CAK", "SSS"), ("-", "BS"), ("CBM", "CSGN")]),
    5: ("2026-11-21", [("BS", "EZS"), ("ASM", "-"), ("SSS", "BCM"), ("AMS", "CBM"), ("CSGN", "CAB"), ("JAB", "CAK")]),
    6: ("2026-11-28", [("EZS", "-"), ("ASM", "BS"), ("CBM", "SSS"), ("AMS", "CSGN"), ("CAB", "CAK"), ("BCM", "JAB")]),
    7: ("2026-12-05", [("EZS", "CBM"), ("CSGN", "ASM"), ("-", "SSS"), ("BS", "AMS"), ("JAB", "CAB"), ("CAK", "BCM")]),
    8: ("2026-12-12", [("SSS", "EZS"), ("AMS", "ASM"), ("CAB", "CBM"), ("BCM", "-"), ("CAK", "BS"), ("JAB", "CSGN")]),
    9: ("2026-12-26", [("EZS", "AMS"), ("ASM", "SSS"), ("-", "JAB"), ("BS", "CAB"), ("CSGN", "BCM"), ("CBM", "CAK")]),
    10: ("2027-01-02", [("EZS", "CSGN"), ("CBM", "ASM"), ("SSS", "AMS"), ("CAB", "BCM"), ("BS", "JAB"), ("CAK", "-")]),
    11: ("2027-01-09", [("ASM", "EZS"), ("CSGN", "SSS"), ("JAB", "CBM"), ("-", "CAB"), ("BCM", "BS"), ("AMS", "CAK")]),
}
SECOND_LEG_DATES = ["2027-01-23", "2027-01-30", "2027-02-06", "2027-02-13", "2027-02-27", "2027-03-13", "2027-03-20", "2027-03-27", "2027-04-03", "2027-04-10", "2027-04-17"]
# (round, home, away, home score, away score, date or "")
RESULTS = [
    (1, "EZS", "CAK", 107, 47, "2026-10-23"), (1, "AMS", "CAB", 60, 78, "2026-10-23"), (1, "ASM", "BCM", 58, 45, "2026-10-24"), (1, "CSGN", "BS", 86, 57, "2026-10-24"), (1, "SSS", "JAB", 69, 66, "2026-10-25"),
    (2, "BS", "CBM", 56, 61, "2026-11-01"), (2, "CAB", "SSS", 55, 40, "2026-10-31"),
    (3, "ASM", "CAB", 56, 57, "2026-11-07"),
    (4, "CAB", "EZS", 64, 66, ""), (4, "JAB", "ASM", 28, 62, ""), (4, "BCM", "AMS", 78, 58, ""),
]
# the federation's table of 15 November 2026 (first phase): code, played, won, lost, difference, points
OFFICIAL = [("EZS", 4, 4, 0, 97, 8), ("ASM", 4, 3, 1, 85, 7), ("CAB", 4, 3, 1, 32, 7), ("CSGN", 3, 3, 0, 94, 6), ("BCM", 4, 2, 2, 12, 6), ("SSS", 4, 2, 2, -6, 6), ("CAK", 4, 1, 3, -145, 5),
            ("AMS", 3, 1, 2, -28, 4), ("CBM", 3, 1, 2, -28, 4), ("JAB", 4, 0, 4, -78, 4), ("BS", 3, 0, 3, -35, 3)]


def build():
    fixtures = []
    for rd, (date, boxes) in FIRST_LEG.items():
        for h, a in boxes:
            if "-" not in (h, a):
                fixtures.append({"matchday": rd, "home": h, "away": a, "date": date, "projected": False})
                fixtures.append({"matchday": rd + 11, "home": a, "away": h, "date": SECOND_LEG_DATES[rd - 1], "projected": True})
    fixtures.sort(key=lambda f: (f["matchday"], f["home"]))
    results = [{"matchday": r, "home": h, "away": a, "home_score": hs, "away_score": as_, **({"date": d} if d else {})} for r, h, a, hs, as_, d in RESULTS]
    return {"season": "2026-2027", "teams": TEAMS, "fixtures": fixtures, "results": results,
            "official": {"published": "2026-11-15", "source": "FTBB", "rows": [{"code": c, "j": j, "w": w, "l": l, "diff": d, "pts": p} for c, j, w, l, d, p in OFFICIAL]}}


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "exports" / "nat1_2026-2027.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"{len(data['teams'])} teams, {len(data['fixtures'])} calendar games, {len(data['results'])} results, official table of {data['official']['published']} -> {out}")
