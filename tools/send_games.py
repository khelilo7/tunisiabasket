"""Send box scores transcribed by hand (JSON files in exports/games_inbox/) to a running site through its admin panel.

    python tools/send_games.py --site https://tunisiabasket.com [--dry-run]

For sheets the OCR cannot read (for example phone screenshots). Each game is checked by the site (points add up, rebounds, shooting, minutes...) and linked to the official result of
its matchday. Sending a game twice only rewrites it. The admin token is typed, never shown or stored.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _site import login  # noqa: E402

INBOX = Path(__file__).resolve().parent.parent / "exports" / "games_inbox"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    site = a.site.rstrip("/")
    files = sorted(INBOX.glob("*.json"))
    if not files:
        sys.exit(f"No game files in {INBOX}.")
    games = [json.loads(f.read_text()) for f in files]
    line = lambda g: f"{g['teams'][0]['code']} {g['teams'][0]['points']}-{g['teams'][1]['points']} {g['teams'][1]['code']} ({g['date']}, J{g.get('matchday_no')})"
    if a.dry_run:
        print(f"{len(games)} game(s) would be sent to {site}: " + "; ".join(line(g) for g in games))
        return
    s = login(site)
    for g in games:
        r = s.post(f"{site}/admin/api/game", json={"game": g}, timeout=60)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        print(("ok   " if r.status_code == 200 else f"FAIL ({r.status_code}) ") + line(g) + " " + (body.get("message") or body.get("error") or "") + (" " + "; ".join(body.get("problems", [])) if body.get("problems") else ""))


if __name__ == "__main__":
    main()
