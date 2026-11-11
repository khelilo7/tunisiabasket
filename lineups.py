"""Expected starting five of a team, from the box scores the site has. A prediction, nothing more.

The five are the players with the highest "starter score": 1 point per start this season + 2 more per start in the team's last 5 games. Players the admin marked as absent
(absences.py) never appear: the next ones move up. They are listed guards first (PG, SG, SF, PF, C), with the position the site shows for them (the admin's correction if any).
"""
import absences
import stats

POS_ORDER = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}


def expected_five(d, code, exclude=None, pos=None):
    """[player dict of stats.build()] (at most 5), guards first. `exclude`: extra player ids to leave out (on top of the admin's absences); `pos`: {id: position} to show instead."""
    out = set(absences.ids()) | set(exclude or ())
    games = sorted((g for g in d["games"] if code in [t["code"] for t in g["teams"]]), key=lambda g: (g["date"], g["id"]))
    last5 = {g["id"] for g in games[-5:]}
    score = {}
    for g in games:
        for t in g["teams"]:
            if t["code"] != code:
                continue
            for p in t["players"]:
                if p.get("dnp") or not p.get("starter") or p["pid"] in out:
                    continue
                score[p["pid"]] = score.get(p["pid"], 0) + 1 + (2 if g["id"] in last5 else 0)
    byid = {p["id"]: p for p in d["players"]}
    best = sorted((i for i in score if i in byid), key=lambda i: (-score[i], -byid[i]["min"], i))[:5]
    five = [{**byid[i], "pos": (pos or {}).get(i, byid[i]["pos"])} for i in best]
    return sorted(five, key=lambda p: (POS_ORDER.get(p["pos"], 9), -p["min"]))


def view(d, home, away):
    """JSON for the site: both clubs with their expected five (id, name, number, position, per-game points / rebounds / assists, photo)."""
    photos = stats.load_photos()
    names = {}
    for g in d["games"]:
        for t in g["teams"]:
            names.setdefault(t["code"], t["name"])

    def side(code):
        return {"code": code, "name": names.get(code, code),
                "five": [{"id": p["id"], "name": p["name"], "team": code, "number": p["number"], "pos": p["pos"], "pts": p["pts"], "reb": p["reb"], "ast": p["ast"],
                          "photo": photos.get(p["id"])} for p in expected_five(d, code)]}
    return {"home": side(home), "away": side(away)}
