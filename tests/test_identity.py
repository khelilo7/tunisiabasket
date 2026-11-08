"""One person, one profile: a 'did not play' row printed with a wrong jersey number must not create a second player (or steal another player's number)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import stats  # noqa: E402

def row(number, name, dnp=False):
    return {"number": number, "name": name, "dnp": dnp, **({} if dnp else {"min": 10})}

def game(*players):
    return {"source": "text", "teams": [{"code": "ESR", "name": "ES Rades", "players": list(players)}, {"code": "CA", "name": "Club Africain", "players": []}]}

games = [game(row(77, "NAIM DHIFALLAH"), row(5, "ALI BEN SALAH")),
         game(row(77, "NAIM DHIFALLAH"), row(5, "ALI BEN SALAH")),
         game(row(7, "NAIM DHIFALLAH", dnp=True), row(5, "ALI BEN SALAH"))]     # the sheet prints his number as 7 and says he did not play
stats._canonicalise(games)
pids = {p["pid"] for g in games for t in g["teams"] for p in t["players"] if "NAIM" in p["name"].upper()}
print("identity:", "ok" if pids == {"esr-77"} else f"FAILED {pids}")

# an unnamed row (the federation prints XX) must not outvote a real name, create a profile, or win the game MVP
games = [game(row(20, "CHEBAANE NIDHAL"), row(5, "ALI BEN SALAH")), game(row(20, "NIDHAL CHEBAANE"), row(5, "ALI BEN SALAH")),
         game(row(20, "XX"), row(5, "ALI BEN SALAH")), game(row(20, "XX"), row(5, "ALI BEN SALAH")), game(row(20, "XX"), row(0, "X X"))]
stats._canonicalise(games)
named = {p["name"] for g in games for t in g["teams"] for p in t["players"] if p["number"] == 20 and not p.get("unnamed")}
unnamed = [p for g in games for t in g["teams"] for p in t["players"] if p.get("unnamed")]
ok2 = len(named) == 1 and "Xx" not in named and len(unnamed) == 4 and all(p["pid"].startswith("esr-x") for p in unnamed)
print("unnamed:", "ok" if ok2 else f"FAILED {named} {len(unnamed)}")
sys.exit(0 if pids == {"esr-77"} and ok2 else 1)
