"""The league-table rules of the Tunisian Basketball Federation (FTBB), as the Règlements Généraux of 10/08/2024 write them (articles 182 to 184, and 194 for penalties).

  Art. 182  a win gives 2 points, a loss 1 point, a loss by forfeit or penalty 0 point.
  Art. 183  the table takes into account: the points, the "goal différence" (points for minus points against), the "goal average" (points for divided by points against).
  Art. 184  when teams are level on points:
    1. two teams: only the games between them count: their goal différence (the one with the higher one is ahead);
    2. level again: the goal différence of all the games they played in the group;
    3. more than two teams: a second table, with only the goal différence of the games played among them;
    4. still level: the goal average (a division, never a subtraction) of the games that opposed them directly;
    5. still level: the goal différence of all the games they played in the group, over the whole competition;
    6. whenever, after one of these steps, only two teams are still level, steps 1 and 2 are applied to those two.
  Art. 194  a team that lost a game by penalty has the worst "point average" of the teams level on points.

The law gives nothing after step 2 for two teams that are still level, or after step 5 for several: the games between them are compared as a goal average, then all the points scored,
then the club code (so that the table never changes order between two reloads). Source: https://www.ftbb.org.tn/wp-content/uploads/2025/11/Reglements-Generaux-de-la-FTBB_2024-2.pdf
"""
LAW_URL = "https://www.ftbb.org.tn/wp-content/uploads/2025/11/Reglements-Generaux-de-la-FTBB_2024-2.pdf"


def rank(rows, results):
    """The rows in table order. rows: dicts with code, pts, pf, pa (all the games of the group); results: every game of the group, {home, away, home_score, away_score}, plus
    "forfeit": the code of the team that lost it by forfeit or penalty (optional)."""
    by = {r["code"]: r for r in rows}
    penalised = {g["forfeit"] for g in results if g.get("forfeit")}

    def mutual(codes):
        return [g for g in results if g["home"] in codes and g["away"] in codes]

    def score(c, codes):
        f = a = 0
        for g in mutual(codes):
            if g["home"] == c:
                f, a = f + g["home_score"], a + g["away_score"]
            elif g["away"] == c:
                f, a = f + g["away_score"], a + g["home_score"]
        return f, a

    diff = lambda c, codes: score(c, codes)[0] - score(c, codes)[1]
    overall = lambda c: by[c]["pf"] - by[c]["pa"]

    def average(c, codes):                                    # a division; a team beaten by penalty has the worst one
        if c in penalised:
            return -1.0
        f, a = score(c, codes)
        return f / a if a else (float("inf") if f else 0.0)

    def split(group, key):
        keys = sorted({key(c) for c in group}, reverse=True)
        return [[c for c in group if key(c) == k] for k in keys]

    def settle(parts, after):                                 # sub-groups in order; a pair starts again at steps 1-2, three or more go on to the next step
        out = []
        for p in parts:
            out += p if len(p) == 1 else two(p) if len(p) == 2 else after(p)
        return out

    def two(pair):
        a, b = pair
        for key in (lambda c: diff(c, set(pair)), overall, lambda c: average(c, set(pair)), lambda c: by[c]["pf"]):
            parts = split(pair, key)
            if len(parts) == 2:
                return parts[0] + parts[1]
        return sorted(pair)

    def step5(group):
        parts = split(group, overall)
        return settle(parts, lambda p: sorted(p, key=lambda c: (-by[c]["pf"], c)))

    def step4(group):
        parts = split(group, lambda c: average(c, set(group)))
        return step5(group) if len(parts) == 1 else settle(parts, step5)

    def step3(group):
        parts = split(group, lambda c: diff(c, set(group)))
        return step4(group) if len(parts) == 1 else settle(parts, step4)

    out = []
    for pts in sorted({r["pts"] for r in rows}, reverse=True):
        group = [r["code"] for r in rows if r["pts"] == pts]
        out += group if len(group) == 1 else two(group) if len(group) == 2 else step3(group)
    return [by[c] for c in out]
