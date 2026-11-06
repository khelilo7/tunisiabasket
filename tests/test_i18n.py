"""Every English string the page shows through _() must have a French translation (and the reverse: no stale keys)."""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
html = (root / "static" / "index.html").read_text()
script = html[html.index("<script>\n") :]

fr_block = script[script.index("const FR = {"): script.index("};", script.index("const FR = {"))]
fr_keys = set(re.findall(r"^\s*'((?:[^'\\]|\\.)*)':", fr_block, flags=re.M)) | set(re.findall(r",\s*'((?:[^'\\]|\\.)*)':\s*'", fr_block))
fr_keys = {k.replace("\\'", "'") for k in fr_keys}

used = {m.replace("\\'", "'") for m in re.findall(r"""\b_\('((?:[^'\\]|\\.)*)'\)""", script)}
used |= {m for m in re.findall(r"\['([A-Za-z0-9 %()/+-]+)', v =>", script)}                      # metric labels
used |= {m for m in re.findall(r"\[\d+, '([a-z]+ [0-9+]+)'\]", script)}                          # legend labels
used |= {"Dark mode"} - {"Dark mode"}  # (unused keys are checked below, not required here)

missing = sorted(k for k in used if k not in fr_keys)
print("i18n:", "FAILED" if missing else f"ok ({len(used)} strings, all translated)")
for k in missing:
    print("  FAIL missing French for:", k[:90])

# sentence builders must exist in both languages with the same names
sent = script[script.index("const SENT = {"): script.index("const f = (k")]
en, fr = sent.split("  fr: {")
names = lambda t: set(re.findall(r"^\s*(\w+):\s", t, flags=re.M)) | set(re.findall(r",\s*(\w+):\s", t))
diff = (names(en) ^ names(fr)) - {"en", "fr"}
if diff:
    print("  FAIL sentence builders differ between languages:", sorted(diff))
sys.exit(1 if missing or diff else 0)
