"""Fill a LOCAL data folder with DEMONSTRATION data for the Cup and for the play-off / play-out, so the pages can be looked at before the real draw and the real phase exist.

    DATA_DIR=/some/local/folder python tools/demo_cup_finals.py

Everything it writes is marked "demo": the pages show a banner saying so. Never run it against production data (it refuses when the folder already holds a real cup or finals file).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import cup  # noqa: E402
import finals  # noqa: E402


def main():
    for f in (cup.FILE, finals.FILE):
        if f.exists() and not json.loads(f.read_text()).get("demo"):
            sys.exit(f"{f} holds real data: refusing to overwrite it with a demonstration.")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    # ------------------------------------------------------------------ the Cup: 8 Pro A clubs, 8 Nationale 1 clubs would not exist yet: 10 + 6
    # Pro A clubs: CA, CSS, USM, ESG, JSK, ESS, JSM, DSG, SN; Nationale 1 clubs: CAK, EZS, BCM, CAB, SSS, ASM, CSGN
    cup.draw("1/8 de finale", "\n".join(["CA, CAK, 2026-12-19", "EZS, CSS, 2026-12-19", "USM, BCM, 2026-12-19", "CAB, ESG, 2026-12-20", "JSK, SSS, 2026-12-20", "ESS, JSM, 2026-12-20",
                                         "DSG, ASM, 2026-12-21", "CSGN, SN, 2026-12-21"]), "2026-12-19", demo=True)
    for tie, hs, as_ in (("r1-1", 94, 61), ("r1-2", 77, 70), ("r1-3", 88, 63), ("r1-4", 79, 72), ("r1-5", 91, 75), ("r1-6", 84, 80), ("r1-7", 82, 71), ("r1-8", 74, 69)):
        cup.set_result(tie, hs, as_)
    for tie, hs, as_ in (("r2-1", 85, 66), ("r2-2", 79, 83)):
        cup.set_result(tie, hs, as_)                        # quarter-finals: two played, two still to come
    cup.set_round("r2", None, "2027-01-16")
    cup.set_round("r3", None, "2027-02-13")
    cup.set_round("r4", None, "2027-03-20")
    cup.set_title("Coupe de Tunisie", "2026-2027")
    # ------------------------------------------------------------------ the play-off (mini league, points carried over), the super play-off (best of 5) and the play-out (mini league), from the table as it stands
    rows = finals._regular_standings()
    top, low = [r["code"] for r in rows[:finals.ZONE]], [r["code"] for r in rows[finals.ZONE:]]
    finals.configure(season="2026-2027", carry="full", preview=True, formats={"playoff": "league", "super": "series", "playout": "league"}, qualify=4, relegation=2,
                     stakes={"playoff": "The first four go to the super play-off.", "super": "Best-of-five series: 1 v 4, 2 v 3, then the final.", "playout": "The last two clubs go down to the Nationale 1."})
    finals.set_teams("playoff", top)
    finals.set_teams("playout", low)

    def round_robin(teams):
        """Home-and-away rounds by the circle method: [(round, home, away)]; the second half is the first one with home and away swapped."""
        ts, out = list(teams), []
        for r in range(len(ts) - 1):
            pairs = [(ts[k], ts[len(ts) - 1 - k]) for k in range(len(ts) // 2)]
            out += [(r + 1, a, b) if r % 2 == 0 else (r + 1, b, a) for a, b in pairs]
            ts = [ts[0]] + [ts[-1]] + ts[1:-1]
        back = [(r + len(ts) - 1, b, a) for r, a, b in out]
        return out + back

    def score(home, away, k):
        """A repeatable, plausible score: the better regular-season rank is favoured, the host gets a few points."""
        sh = {r["code"]: r["rank"] for r in rows}
        edge = (sh[away] - sh[home]) * 1.4 + 4 + ((k * 7 + sh[home] * 3 + sh[away]) % 13 - 6)
        a = 74 + (k * 5) % 11
        return (a + max(2, int(edge)), a) if edge > 0 else (a, a + max(2, int(-edge)))

    lines = []
    for k, (r, h, a) in enumerate(round_robin(top)):                  # the whole play-off is played: 30 games, 10 rounds
        hs, as_ = score(h, a, k)
        lines.append(f"{r}, {h}, {a}, {hs}, {as_}, 2027-04-{10 + r:02d}" if r <= 5 else f"{r}, {h}, {a}, {hs}, {as_}, 2027-05-{r - 4:02d}")
    finals.put_league_games("playoff", "\n".join(lines))
    lines = []
    for k, (r, h, a) in enumerate(round_robin(low)):                  # the play-out is at round 7 of 10
        if r <= 7:
            hs, as_ = score(h, a, k + 3)
            lines.append(f"{r}, {h}, {a}, {hs}, {as_}, 2027-04-{10 + r:02d}" if r <= 5 else f"{r}, {h}, {a}, {hs}, {as_}, 2027-05-{r - 4:02d}")
        else:
            lines.append(f"{r}, {h}, {a}")
    finals.put_league_games("playout", "\n".join(lines))
    finals.scaffold_super()
    finals.configure(announced=True)               # the demo is shown as announced (a real play-off is only shown once the admin announces it)
    tp = finals.view()["groups"]["playoff"]["table"]
    s1, s2, s3, s4 = (t["code"] for t in tp[:4])
    finals.put_series("super", "\n".join([f"GAME, sf1, {s1}, 88, 76, 2027-05-20", f"GAME, sf1, {s1}, 84, 80, 2027-05-22", f"GAME, sf1, {s4}, 79, 77, 2027-05-25", f"GAME, sf1, {s4}, 70, 75, 2027-05-27",
                                          f"GAME, sf2, {s2}, 80, 82, 2027-05-20", f"GAME, sf2, {s2}, 78, 72, 2027-05-22", f"GAME, sf2, {s3}, 74, 70, 2027-05-25"]))
    d = finals.load()
    raw = json.loads(finals.FILE.read_text())
    raw["demo"] = True
    finals.FILE.write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    print(f"demo cup ({len(cup.view()['rounds'])} rounds) and finals ({d['carry']} carry) written in {config.DATA_DIR}", "(DATA_DIR=%s)" % os.environ.get("DATA_DIR"))


if __name__ == "__main__":
    main()
