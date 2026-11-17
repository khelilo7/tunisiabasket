"""The club's pages on social media: Facebook, YouTube, Instagram and X, shown as round brand icons in the footer and on the home page.

`assets/social.json` ships with the code ({"facebook": "https://...", "youtube": "", ...}); the admin can change the addresses from the Traffic tab (`data/social.json`, which wins).
An empty address means "no such page": its icon is simply not shown, so nothing points to a page that does not exist.
"""
import json
import re

import config

NETWORKS = (("facebook", "Facebook"), ("youtube", "YouTube"), ("instagram", "Instagram"), ("x", "X"))
FILE = config.DATA_DIR / "social.json"
DEFAULT = {"facebook": "https://www.facebook.com/people/Tunisia-Basket/61596371069928/", "youtube": "", "instagram": "", "x": ""}
URL = re.compile(r"^https://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/[^\s<>\"']*)?$")
# Simple Icons glyphs (24 x 24)
PATHS = {
    "facebook": "M22 12a10 10 0 1 0-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0 0 22 12z",
    "youtube": "M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8zM9.6 15.6V8.4l6.2 3.6-6.2 3.6z",
    "instagram": "M12 2.2c3.2 0 3.6 0 4.8.1 3.3.1 4.8 1.7 4.9 4.9.1 1.3.1 1.6.1 4.8s0 3.6-.1 4.8c-.1 3.2-1.7 4.8-4.9 4.9-1.3.1-1.6.1-4.8.1s-3.6 0-4.8-.1c-3.3-.1-4.8-1.7-4.9-4.9C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.8C2.4 3.9 4 2.4 7.2 2.3 8.4 2.2 8.8 2.2 12 2.2zM12 0C8.7 0 8.3 0 7.1.1 2.7.3.3 2.7.1 7.1 0 8.3 0 8.7 0 12s0 3.7.1 4.9c.2 4.4 2.6 6.8 7 7C8.3 24 8.7 24 12 24s3.7 0 4.9-.1c4.4-.2 6.8-2.6 7-7 .1-1.2.1-1.6.1-4.9s0-3.7-.1-4.9c-.2-4.4-2.6-6.8-7-7C15.7 0 15.3 0 12 0zm0 5.8a6.2 6.2 0 1 0 0 12.4 6.2 6.2 0 0 0 0-12.4zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.4-11.8a1.4 1.4 0 1 0 0 2.9 1.4 1.4 0 0 0 0-2.9z",
    "x": "M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z",
}


def _read(path):
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def load():
    """{network: address or ""}: the admin's file over the shipped one over the built-in defaults."""
    out = dict(DEFAULT)
    for p in (config.ASSETS_DIR / "social.json", FILE):
        for k, v in _read(p).items():
            if k in out and isinstance(v, str):
                out[k] = v.strip() if URL.match(v.strip()) else ""
    return out


def save(values):
    """Store the admin's addresses (https only; an empty one removes the icon). Returns the saved dict, or raises ValueError naming the bad one."""
    cur = load()
    for k, _ in NETWORKS:
        if k in values:
            v = str(values[k] or "").strip()
            if v and not URL.match(v):
                raise ValueError(f"{dict(NETWORKS)[k]}: write the full address, starting with https://")
            cur[k] = v
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, indent=1))
    tmp.replace(FILE)
    return cur


def links():
    d = load()
    return [{"key": k, "name": n, "url": d[k]} for k, n in NETWORKS if d.get(k)]


def icon(key, px=18):
    return f'<svg viewBox="0 0 24 24" width="{px}" height="{px}" aria-hidden="true" fill="currentColor"><path d="{PATHS[key]}"/></svg>'


def html(label="Follow us", big=False):
    """The row of round icons (server side, so it is in the page the crawlers and the first paint see); `big`: labelled buttons (Facebook, YouTube, Instagram...) for the home page."""
    if big:
        items = "".join(f'<a class="sb s-{l["key"]}" href="{l["url"]}" target="_blank" rel="noopener me">{icon(l["key"], 22)}<span>{l["name"]}</span></a>' for l in links())
        return f'<span class="socbig" role="group" aria-label="{label}">{items}</span>' if items else ""
    items = "".join(f'<a class="soc s-{l["key"]}" href="{l["url"]}" target="_blank" rel="noopener me" aria-label="{l["name"]}" title="{l["name"]}">{icon(l["key"])}</a>' for l in links())
    return f'<span class="socials" role="group" aria-label="{label}">{items}</span>' if items else ""
