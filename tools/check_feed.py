"""Does a data provider cover the Tunisian Pro A? Run it with your own free key; the key stays in your terminal, never in the repo.

    APISPORTS_KEY=xxxxxxxx .venv/bin/python tools/check_feed.py

Asks API-Basketball (api-sports.io, free plan: 100 requests a day) for its Tunisian competitions and, if it lists the Pro A,
for the current season's games, so you can see how complete the data is before anything is built on it. Uses 3 requests.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

KEY = os.environ.get("APISPORTS_KEY", "").strip()
BASE = "https://v1.basketball.api-sports.io"


def get(path, **params):
    req = urllib.request.Request(f"{BASE}/{path}?{urllib.parse.urlencode(params)}", headers={"x-apisports-key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"The provider answered HTTP {e.code} for /{path}. Check the key.")


if not KEY:
    sys.exit("Set APISPORTS_KEY first (free key: https://dashboard.api-football.com/register).")
leagues = get("leagues", country="Tunisia")
if leagues.get("errors"):
    sys.exit(f"The provider refused the request: {leagues['errors']}")
found = leagues.get("response") or []
print(f"{len(found)} Tunisian competition(s) listed:")
for lg in found:
    seasons = [str(s.get("season")) for s in lg.get("seasons", [])][-3:]
    print(f"  id {lg['id']}: {lg['name']} ({lg.get('type')}), recent seasons: {', '.join(seasons)}")
pro = next((lg for lg in found if any(w in lg["name"].lower() for w in ("pro a", "national a", "division 1", "ligue 1", "championnat"))), None)
if not pro:
    sys.exit("No Pro A style competition found: this provider does not cover the league.")
season = pro["seasons"][-1]
cov = season.get("coverage", {})
print(f"\nCoverage claimed for {pro['name']} {season.get('season')}: {json.dumps(cov)}")
games = get("games", league=pro["id"], season=season["season"]).get("response") or []
done = [g for g in games if (g.get("status") or {}).get("short") in ("FT", "AOT")]
print(f"{len(games)} games listed, {len(done)} finished. Compare with the {os.environ.get('OUR_GAMES', '66')} matches in our own results.")
for g in done[-3:]:
    t = g["teams"]
    print(f"  {g['date'][:10]}  {t['home']['name']} {g['scores']['home']['total']}-{g['scores']['away']['total']} {t['away']['name']}")
