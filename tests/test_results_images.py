"""Reads the 12 federation images in tests/results_images and compares with seed/official.json. Run: python tests/test_results_images.py"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from results_parser import parse_results_image  # noqa: E402

off = json.loads((root / "seed" / "official.json").read_text())
truth = {(r["matchday"], r["home"], r["away"]): (r["home_score"], r["away_score"]) for r in off["results"]}
bad = total = 0
for i in range(1, 13):
    r = parse_results_image(str(root / "tests" / "results_images" / f"{i}.jpg"), list(off["teams"]))
    if r["kind"] != "results":
        print(i, r["kind"], r["warnings"])
        continue
    for g in r["games"]:
        total += 1
        exp = truth.get((r["matchday"], g["home"], g["away"]))
        if exp != (g["home_score"], g["away_score"]):
            bad += 1
            print(f"image {i} matchday {r['matchday']}: read {g['home']} {g['home_score']}-{g['away_score']} {g['away']} (raw {g['raw']!r}) expected {exp}")
    if r["warnings"]:
        print(f"image {i} matchday {r['matchday']} warnings:", r["warnings"])
print(f"{total - bad}/{total} games read correctly")
sys.exit(1 if bad else 0)
