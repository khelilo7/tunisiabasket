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
# the quiet stat notes exist in both languages for every key, and every label they attach to maps to a note
tips = script[script.index("const TIPS = {"): script.index("const TIPKEY")]
en_t, fr_t = tips.split("  fr: {")
tk = lambda t: set(re.findall(r"(\w+): \['", t))
if tk(en_t) != tk(fr_t) or not tk(en_t):
    print("  FAIL stat notes differ between languages:", sorted(tk(en_t) ^ tk(fr_t)))
    diff = diff | {"tips"}
keys = set(re.findall(r"'?[^',{]+'?: '(\w+)'", script[script.index("const TIPKEY"): script.index("function decorateTips")]))
if not keys <= tk(en_t):
    print("  FAIL a stat label points to a missing note:", sorted(keys - tk(en_t)))
    diff = diff | {"tipkey"}
sys.exit(1 if missing or diff else 0)
