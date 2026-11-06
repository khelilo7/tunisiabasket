"""Consistency checks for an extracted game. An empty list means every check passed."""


def validate(game):
    problems = []
    if len(game["teams"]) != 2:
        return [f"expected 2 teams, got {len(game['teams'])}"]
    for t in game["teams"]:
        c = t["code"]
        played = [p for p in t["players"] if not p.get("dnp")]
        if not played:
            problems.append(f"{c}: no players")
            continue
        nums = [p["number"] for p in played]  # DNP rows never enter the stats, so their numbers don't matter
        if any(n < 0 for n in nums) or len(set(nums)) != len(nums):
            problems.append(f"{c}: jersey numbers unreadable or duplicated {sorted(nums)}")
        if sum(p["pts"] for p in played) != t["points"]:
            problems.append(f"{c}: player points {sum(p['pts'] for p in played)} != team total {t['points']}")
        for p in played:
            who = f"{c} #{p['number']} {p['name']}"
            if p["reb"] != p["oreb"] + p["dreb"]:
                problems.append(f"{who}: REB != OR+DR")
            if p["fgm"] != p["p2m"] + p["p3m"] or p["fga"] != p["p2a"] + p["p3a"]:
                problems.append(f"{who}: FG != 2P+3P")
            if p["pts"] != 2 * p["p2m"] + 3 * p["p3m"] + p["ftm"]:
                problems.append(f"{who}: PTS != 2*2P + 3*3P + FT")
            if p["fgm"] > p["fga"] or p["ftm"] > p["fta"] or p["p3m"] > p["p3a"]:
                problems.append(f"{who}: made > attempted")
            if "_ef" in p:
                ef = (p["pts"] + p["reb"] + p["ast"] + p["stl"] + p["blk"]
                      - (p["fga"] - p["fgm"]) - (p["fta"] - p["ftm"]) - p["tov"])
                if ef != p["_ef"]:
                    problems.append(f"{who}: EF {p['_ef']} != computed {ef}")
        if not 195 <= sum(p["min"] for p in played) <= 330:
            problems.append(f"{c}: minutes total {sum(p['min'] for p in played):.0f} out of range")
    return problems
