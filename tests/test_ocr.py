"""Accuracy check: OCR of the scanned J1 PDF vs the hand-transcribed truth. Run: python tests/test_ocr.py"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from extractor import extract  # noqa: E402

game, problems = extract(str(root / "tests" / "jsk_usm.pdf"), filename="JSK vsUSM.pdf", matchday="J1 PHASE ALLER")
truth = json.loads((root / "tests" / "truth_jsk_usm.json").read_text())
bad = total = 0
for t, tt in zip(game["teams"], truth["teams"]):
    for p, q in zip(t["players"], tt["players"]):
        for k, v in q.items():
            if k in ("captain", "name"):  # names are fixed later by cross-game majority voting
                continue
            total += 1
            if p.get(k) != v:
                bad += 1
                print("MISMATCH", t["code"], q["number"], k, p.get(k), "!=", v)
print(f"validation problems: {problems or 'none'}; stat field errors: {bad}/{total}")
sys.exit(1 if bad or problems else 0)
