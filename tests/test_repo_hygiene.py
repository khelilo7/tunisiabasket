"""The repository is PUBLIC: nothing private may be committed. Scans every file tracked by git."""
import re
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split("\n")
PATTERNS = {
    "Google Drive id (33 characters starting with 1)": re.compile(r"(?<![A-Za-z0-9_-])1[A-Za-z0-9_-]{32}(?![A-Za-z0-9_-])"),
    "Drive/Docs link": re.compile(r"(drive|docs)\.google\.com/(drive/folders|file/d|document/d)/[A-Za-z0-9_-]{10,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "AWS key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "admin token (XXXX-XXXX-XXXX-XXXX; the documented examples are allowed)": re.compile(r"\b(?!TEST-TOKEN|K7QD-M2XR-9TWB-HC4N|XXXX-XXXX-XXXX-XXXX)[A-HJ-NP-Z2-9]{4}(-[A-HJ-NP-Z2-9]{4}){3}\b"),
    "local user path": re.compile(r"/Users/[A-Za-z0-9_.-]+/"),
}
SKIP_SUFFIX = (".jpg", ".png", ".pdf", ".npz")
bad = []
for f in files:
    if not f or f.endswith(SKIP_SUFFIX) or f == "tests/test_repo_hygiene.py":
        continue
    text = (root / f).read_text(errors="ignore")
    for label, pat in PATTERNS.items():
        m = pat.search(text)
        if m:
            bad.append(f"{f}: {label}: {m.group(0)[:12]}...")
forbidden = [f for f in files if f.startswith("data/") or f.endswith((".env", ".pem")) or "admin_token" in f]
bad += [f"{f}: must not be tracked" for f in forbidden]
print("repo hygiene:", "FAILED" if bad else f"ok ({len(files) - 1} files scanned)")
for b in bad:
    print("  FAIL", b)
sys.exit(1 if bad else 0)
