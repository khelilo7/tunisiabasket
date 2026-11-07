"""What search engines and link previews get: titles, descriptions, canonical/alternate links, structured data, sitemap."""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ["SITE_URL"] = "https://example.test"
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import app  # noqa: E402
import seo  # noqa: E402
import stats  # noqa: E402
from PIL import Image  # noqa: E402

c = app.app.test_client()
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def get(path):
    r = c.get(path)
    return r.status_code, r.get_data(as_text=True)


def head_of(html):
    return html[html.index("<head>"): html.index("</head>")]


d = stats.build()
players = d["players"]
game_ids = [g["id"] for g in d["games"]]
pages = [("home", None), ("standings", None), ("players", None), ("games", None), ("planning", None), ("mvp", None)]
pages += [("team", code) for code in stats.load_official()["teams"]]
pages += [("player", seo.player_ref(p)) for p in players[:25]] + [("game", gid) for gid in game_ids[:12]]

titles = {}
for lang in seo.LANGS:
    for page, arg in pages:
        path = seo.path(lang, page, arg)
        code, html = get(path)
        check(code == 200, f"{path}: status {code}")
        if code != 200:
            continue
        h = head_of(html)
        title = re.search(r"<title>(.*?)</title>", h, re.S)
        desc = re.search(r'<meta name="description" content="([^"]*)"', h)
        check(title and 15 <= len(title.group(1)) <= 120, f"{path}: title missing or odd length ({title and len(title.group(1))})")
        check(desc and 60 <= len(desc.group(1)) <= 330, f"{path}: description missing or odd length ({desc and len(desc.group(1))})")
        check(f'<link rel="canonical" href="https://example.test{path}">' in h, f"{path}: canonical link wrong")
        for hl in ("en", "fr", "x-default"):
            check(f'hreflang="{hl}"' in h, f"{path}: missing hreflang {hl}")
        check('property="og:image" content="https://example.test/img/og-image.jpg"' in h, f"{path}: og:image")
        check(f'<html lang="{lang}">' in html, f"{path}: html lang")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try:
                json.loads(block.replace("<\\/", "</"))
            except ValueError:
                check(False, f"{path}: JSON-LD is not valid JSON")
        check("©" in html and "{{" not in html and "<!--HEAD" not in html and "<!--SSR" not in html and "<!--NAV" not in html, f"{path}: template token left in the page")
        check(len(re.findall(r'<a href="/', html)) >= 5, f"{path}: too few crawlable internal links")
        if title:
            titles.setdefault((lang, page), []).append(title.group(1))

for (lang, page), ts in titles.items():
    if page in ("team", "player", "game"):
        check(len(set(ts)) == len(ts), f"{lang} {page}: duplicate titles")

# canonical redirects and 404s
code = c.get("/joueur/" + players[0]["id"]).status_code
check(code == 301, f"id-only player URL must redirect to the canonical one, got {code}")
check(c.get("/index.html").status_code == 301, "/index.html must redirect to /")
check(c.get("/equipe/ca").status_code == 301, "lower-case team code must redirect to /equipe/CA")
check(c.get("/equipe/NOPE").status_code == 404 and c.get("/en/game/nope").status_code == 404, "unknown pages must be 404")
check(seo.DEFAULT == "fr" and seo.path("fr", "team", "CA") == "/equipe/CA" and seo.path("en", "team", "CA") == "/en/team/CA", "French is the default language")
check(get("/")[1].count('<html lang="fr">') == 1, "the home page must be French")
for old, new in (("/fr/", "/"), ("/fr/equipe/CA", "/equipe/CA"), ("/fr/classement", "/classement"), ("/team/CA", "/en/team/CA"), ("/standings", "/en/standings"), ("/players", "/en/players")):
    r = c.get(old)
    check(r.status_code == 301 and r.headers["Location"].endswith(new), f"old address {old} must redirect (301) to {new}, got {r.status_code} {r.headers.get('Location')}")
check('name="robots" content="noindex"' in get("/equipe/NOPE")[1], "404 pages must be noindex")

# sitemap: valid XML, every URL answers 200 (no redirects), both languages, hreflang pairs
code, xml = get("/sitemap.xml")
check(code == 200, "sitemap status")
ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
tree = ET.fromstring(xml)
urls = [u.find("s:loc", ns).text for u in tree.findall("s:url", ns)]
check(len(urls) == len(set(urls)) and len(urls) >= 2 * (5 + 12 + len(players) + len(game_ids)), f"sitemap has {len(urls)} urls")
for u in urls:
    p = u.replace("https://example.test", "")
    r = c.get(p)
    check(r.status_code == 200, f"sitemap url {p} answers {r.status_code}")
check(all(len(u.findall("x:link", ns)) == 3 for u in tree.findall("s:url", ns)), "every sitemap url needs en, fr and x-default alternates")

robots = get("/robots.txt")[1]
check("Sitemap: https://example.test/sitemap.xml" in robots and "Disallow: /admin" in robots, "robots.txt")
check("Disallow: /api" not in robots, "robots.txt must not block /api (the app needs it to render)")
r = c.get("/admin")
check("noindex" in r.headers.get("X-Robots-Tag", "") and 'content="noindex, nofollow"' in r.get_data(as_text=True), "admin must be noindex")

# brand assets
for code in stats.load_official()["teams"]:
    check((root / "static" / "img" / "teams" / f"{code}.png").exists(), f"missing team logo {code}")
check(Image.open(root / "static" / "img" / "og-image.jpg").size == (1200, 630), "og-image must be 1200x630")
check(Image.open(root / "static" / "img" / "apple-touch-icon.png").size == (180, 180), "apple-touch-icon must be 180x180")
manifest = json.loads((root / "static" / "site.webmanifest").read_text())
check(manifest["name"] == "Tunisia Basket" and len(manifest["icons"]) >= 2, "web manifest")
for f in ("favicon.ico", "img/logo-96.png", "img/logo.png", "img/favicon-32.png", "img/icon-192.png", "img/icon-512.png"):
    check(c.get("/" + f).status_code == 200, f"/{f} must be served")

print("seo:", "FAILED" if fails else f"ok ({len(pages) * 2} pages checked, {len(urls)} sitemap urls)")
for f in fails[:25]:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
