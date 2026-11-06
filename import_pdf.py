"""Import PDFs from disk (no Drive): python import_pdf.py game1.pdf game2.pdf [--matchday "J3 PHASE ALLER"]"""
import argparse
import hashlib
import json
from pathlib import Path

import config
from extractor import extract

ap = argparse.ArgumentParser()
ap.add_argument("pdfs", nargs="+")
ap.add_argument("--matchday", default="")
a = ap.parse_args()
out_dir = config.DATA_DIR / "games"
rev_dir = config.DATA_DIR / "review"
for d in (out_dir, rev_dir):
    d.mkdir(parents=True, exist_ok=True)
for f in a.pdfs:
    game, problems = extract(f, filename=Path(f).name, matchday=a.matchday)
    gid = hashlib.sha1(Path(f).read_bytes()).hexdigest()[:16]
    game.update(id=gid, matchday=a.matchday, source_file=Path(f).name)
    if problems:
        game["problems"] = problems
    (rev_dir if problems else out_dir).joinpath(f"{gid}.json").write_text(json.dumps(game, indent=1, ensure_ascii=False))
    print(("REVIEW" if problems else "ok    "), game["source"], game["date"], [(t["code"], t["points"]) for t in game["teams"]], problems or "")
