"""Build assets/digit_templates.npz from the labelled federation images (tests/results_images + seed/official.json).
Run after adding more labelled images:  python tools/train_digits.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import results_parser as rp  # noqa: E402


def samples(leave_out=None):
    off = json.loads((root / "seed" / "official.json").read_text())
    X, y = [], []
    for md in range(1, 12):
        if md == leave_out:
            continue
        path = root / "tests" / "results_images" / f"{md}.jpg"
        rgb = Image.open(path).convert("RGB")
        arr = np.array(rgb)
        bars = rp.find_bars(rgb)
        truth = [r for r in off["results"] if r["matchday"] == md]
        assert len(bars) == len(truth) == 6, (md, len(bars), len(truth))
        for band, r in zip(bars, truth):
            crops = rp.bar_crops(rgb, arr, band)
            for crop, val in ((crops[0], r["home_score"]), (crops[1], r["away_score"])):
                gl = rp.split_glyphs(crop)
                if len(gl) != len(str(val)):
                    print(f"skip: matchday {md} score {val}: found {len(gl)} glyphs")
                    continue
                for g, ch in zip(gl, str(val)):
                    X.append(rp._glyph_features(g))
                    y.append(int(ch))
    return np.array(X), np.array(y)


if __name__ == "__main__":
    if "--cv" in sys.argv:  # leave-one-matchday-out accuracy
        ok = tot = 0
        off = json.loads((root / "seed" / "official.json").read_text())
        for md in range(1, 12):
            X, y = samples(leave_out=md)
            rgb = Image.open(root / "tests" / "results_images" / f"{md}.jpg").convert("RGB")
            arr = np.array(rgb)
            for band, r in zip(rp.find_bars(rgb), [r for r in off["results"] if r["matchday"] == md]):
                crops = rp.bar_crops(rgb, arr, band)
                for crop, val in ((crops[0], r["home_score"]), (crops[1], r["away_score"])):
                    gl = rp.split_glyphs(crop)
                    pred = "".join(str(int(y[np.argmin(((X - rp._glyph_features(g)) ** 2).sum(1))])) for g in gl)
                    tot += 1
                    ok += pred == str(val)
                    if pred != str(val):
                        print(f"  matchday {md}: predicted {pred}, truth {val}")
        print(f"leave-one-matchday-out: {ok}/{tot} scores correct")
    else:
        X, y = samples()
        out = root / "assets" / "digit_templates.npz"
        np.savez_compressed(out, X=X, y=y)
        print(f"saved {len(y)} digit samples to {out} (per digit: {np.bincount(y, minlength=10).tolist()})")
