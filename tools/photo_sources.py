"""List every player with places to look for a photo you may use, as exports/player_photo_sources.csv and a clickable .html.

    python tools/photo_sources.py            ready-made search links only (no network)
    python tools/photo_sources.py --commons  also asks Wikimedia Commons (freely licensed files) for each name; takes a few minutes

Nothing here is a licence: a link only says where to look. Check the licence and the credit on each file page before you publish a photo,
then upload it from the admin panel (Players tab, 📷 on the player's row).
"""
import argparse
import csv
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import stats  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "exports"
UA = {"User-Agent": "TunisiaBasketPhotoLookup/1.0 (site owner; one request per second)"}
q = urllib.parse.quote_plus


def google(name, team_name, free=False):
    return "https://www.google.com/search?tbm=isch&q=" + q(f'"{name}" basketball {team_name}') + ("&tbs=sur:fmc" if free else "")


def commons_files(name):
    """Files on Wikimedia Commons whose title or description mentions the name: [(title, page url)]. Candidates only: check it is the right person."""
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "list": "search", "srnamespace": 6, "srsearch": f'"{name}"', "srlimit": 5, "format": "json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                hits = json.load(r)["query"]["search"]
            return [(h["title"], "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(h["title"].replace(" ", "_"))) for h in hits]
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return []
            time.sleep(8 * (attempt + 1))
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            return []
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commons", action="store_true")
    a = ap.parse_args()
    d = stats.build()
    photos = stats.load_photos()
    teams = stats.load_official()["teams"]
    rows = []
    for p in sorted(d["players"], key=lambda p: (p["team"], p["number"])):
        name = " ".join(w.capitalize() for w in p["name"].split())
        tn = teams.get(p["team"], p["team"])
        r = {"id": p["id"], "name": name, "team": p["team"], "team_name": tn, "number": p["number"], "has_photo": "yes" if photos.get(p["id"]) else "no",
             "google_images": google(name, tn), "google_free_licence": google(name, tn, free=True),
             "commons_search": "https://commons.wikimedia.org/w/index.php?search=" + q(name) + "&ns6=1",
             "fiba_search": "https://www.fiba.basketball/en/search?q=" + q(name), "commons_candidates": []}
        if a.commons:
            r["commons_candidates"] = commons_files(name)
            time.sleep(1.2)
            print(f"{len(rows) + 1}/{len(d['players'])} {name}: {len(r['commons_candidates'])} Commons file(s)", flush=True)
        rows.append(r)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "player_photo_sources.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["player id", "name", "team", "number", "has photo", "Google Images", "Google Images (free-to-use filter)", "Wikimedia Commons search", "FIBA search", "Commons candidates (check it is him)"])
        for r in rows:
            w.writerow([r["id"], r["name"], r["team_name"], r["number"], r["has_photo"], r["google_images"], r["google_free_licence"], r["commons_search"], r["fiba_search"],
                        " | ".join(f"{t} {u}" for t, u in r["commons_candidates"])])
    cells = []
    cur = None
    for r in rows:
        if r["team"] != cur:
            cur = r["team"]
            cells.append(f'<tr class="t"><td colspan="5">{html.escape(r["team_name"])} ({cur})</td></tr>')
        cand = "<br>".join(f'<a href="{html.escape(u)}">{html.escape(t.replace("File:", ""))}</a>' for t, u in r["commons_candidates"]) or "–"
        cells.append(f'<tr><td>#{r["number"]}</td><td><b>{html.escape(r["name"])}</b><br><small>{r["id"]}{" · has photo" if r["has_photo"] == "yes" else ""}</small></td>'
                     f'<td><a href="{html.escape(r["google_images"])}">Google Images</a><br><a href="{html.escape(r["google_free_licence"])}">free-to-use filter</a></td>'
                     f'<td><a href="{html.escape(r["commons_search"])}">Commons</a> · <a href="{html.escape(r["fiba_search"])}">FIBA</a></td><td>{cand}</td></tr>')
    (OUT / "player_photo_sources.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Player photo sources</title><style>body{font:15px system-ui;max-width:1000px;margin:24px auto;padding:0 12px}'
        'table{border-collapse:collapse;width:100%}td{border-bottom:1px solid #ddd;padding:6px 8px;vertical-align:top}tr.t td{background:#f3f3f3;font-weight:700}small{color:#777}</style>'
        '<h1>Player photo sources</h1><p>Links only say where to look. Check the licence and credit on each file page before publishing, then upload from the admin panel (Players tab, 📷).</p>'
        f'<table>{"".join(cells)}</table>')
    print(f"{len(rows)} players -> {OUT}/player_photo_sources.csv and .html")


if __name__ == "__main__":
    main()
