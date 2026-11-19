"""Download the box scores the FTBB once published on its old "Statistiques" pages (kept by the Internet Archive).

    python tools/archive_ftbb.py [--out exports/history_raw] [--page URL] [--pause 6]

Reads the archived page (default: the National A statistics page saved on 2020-10-27), lists every PDF it links with its label (date and teams), and downloads them one by one into
OUT/<season>/, slowly: the Internet Archive refuses fast bulk downloads. It can be stopped and started again (files already there are skipped). Writes OUT/manifest.json.
"""
import argparse
import html
import json
import re
import subprocess
import time
from pathlib import Path

PAGE = "https://web.archive.org/web/20201027120915id_/http://ftbb.org.tn/la-competition/championnat-national-a/statistiques/"


def curl(url, out=None, timeout=90):
    cmd = ["curl", "-sL", "-m", str(timeout), "-A", "Mozilla/5.0 (research; Tunisia Basket archive)", "-w", "%{http_code}"]
    if out:
        cmd += ["-o", str(out)]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    return r.stdout if not out else r.stdout[-3:]


def season_of(label, url):
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", label) or re.search(r"(\d{2})/(\d{2})/(20\d{2})", label)
    if not m:
        return "unknown"
    if m.re.pattern.startswith("(20"):
        y, mo = int(m.group(1)), int(m.group(2))
    else:
        y, mo = int(m.group(3)), int(m.group(2))
    return f"{y}-{y + 1}" if mo >= 8 else f"{y - 1}-{y}"


def manifest(page):
    t = curl(page)
    items, seen = [], set()
    for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        if "uploads" in href and re.search(r"\.(pdf|jpg|png)$", href, re.I):
            label = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            key = (href, label)
            if key in seen:
                continue
            seen.add(key)
            items.append({"url": href.replace(":80/", "/"), "label": label, "season": season_of(label, href)})
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="exports/history_raw")
    ap.add_argument("--page", default=PAGE)
    ap.add_argument("--pause", type=float, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    items = manifest(a.page)
    (out / "manifest.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
    print(len(items), "files listed")
    for n, it in enumerate(items, 1):
        d = out / it["season"]
        d.mkdir(exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", it["label"])[:80] + "__" + Path(it["url"]).name
        f = d / name
        it["file"] = str(f.relative_to(out))
        if f.exists() and f.stat().st_size > 2000:
            continue
        for attempt in range(3):
            time.sleep(a.pause * (attempt + 1))
            code = curl("https://web.archive.org/web/2020id_/" + it["url"], f)
            head = f.read_bytes()[:5] if f.exists() else b""
            if code == "200" and head in (b"%PDF-", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1") or head[:4] == b"\x89PNG":
                break
            f.unlink(missing_ok=True)
        print(n, len(items), "ok" if f.exists() else "FAILED", it["label"][:50], flush=True)
    (out / "manifest.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
