"""Send a Nationale 1 data file (see build_nat1_seed.py) to a running site through its admin panel:  python tools/send_nat1.py --site https://tunisiabasket.com FILE.json [--dry-run]

It adds the teams, the calendar, the results and the federation's table, the same way the admin tab "Nationale 1" does (so every check of the site runs). Sending it twice only rewrites.
The admin token is typed, never shown or stored.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _site import login  # noqa: E402


def lines(rows, keys):
    return "\n".join(", ".join(str(r.get(k, "")) if not isinstance(r.get(k), bool) else str(int(r[k])) for k in keys) for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("file")
    a = ap.parse_args()
    d = json.loads(Path(a.file).read_text())
    ops = [{"op": "season", "season": d["season"]}] + [{"op": "team", "code": c, "name": n} for c, n in d["teams"].items()]
    ops.append({"op": "fixtures", "text": lines(d.get("fixtures", []), ("matchday", "home", "away", "date", "projected"))})
    ops.append({"op": "paste", "text": lines(d.get("results", []), ("matchday", "home", "away", "home_score", "away_score", "date"))})
    if d.get("official"):
        o = d["official"]
        ops.append({"op": "official", "text": f"date: {o.get('published', '')}\n" + lines(o["rows"], ("code", "j", "w", "l", "diff", "pts"))})
    if a.dry_run:
        print(f"{len(ops)} operations would be sent to {a.site}: season, {len(d['teams'])} teams, {len(d.get('fixtures', []))} calendar games, {len(d.get('results', []))} results, official table")
        return
    s = login(a.site.rstrip("/"))
    for op in ops:
        r = s.post(a.site.rstrip("/") + "/admin/api/nat1", json=op)
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        print(("ok   " if r.ok else "FAIL ") + (j.get("message") or j.get("error") or r.text[:120]))
        if not r.ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
