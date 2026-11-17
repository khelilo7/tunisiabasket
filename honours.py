"""What a club has won (assets/honours.json): the Tunisian championship and Cup as a small mention on its team page, the African Champions Cup and the BAL (wins, and lost finals; never third or fourth places) as a side note, with the Arab Club Championship and the Maghreb Championship.

The file lists only wins. Years are the end of the season (2026 = 2025-26). It ships with the code, so every copy of the site shows the same facts; the page says where they come from.
"""
import json

import config

FILE = config.ASSETS_DIR / "honours.json"


def _season(y):
    return f"{y - 1}-{str(y)[2:]}"


def load():
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {"clubs": {}, "sources": {}}


def for_club(code):
    """{"league": {"n", "last", "seasons"}, "cup": {...}, "africa"/"bal": [years won], "africa_final"/"bal_final": [years lost in the final], "sources": {...}, "checked": date} or None when the club has won none of them."""
    d = load()
    c = (d.get("clubs") or {}).get(code) or {}
    out = {}
    for k in ("league", "cup"):
        ys = sorted(int(y) for y in c.get(k) or [])
        if ys:
            out[k] = {"n": len(ys), "last": _season(ys[-1]), "seasons": [_season(y) for y in ys]}
    for k in ("africa", "africa_final", "bal", "bal_final", "arab", "arab_final", "maghreb", "maghreb_final"):
        ys = sorted(int(y) for y in c.get(k) or [])
        if ys:
            out[k] = [str(y) for y in ys]                                       # the African Cup and the BAL are played over a calendar year
    if not out:
        return None
    return {**out, "sources": d.get("sources") or {}, "checked": d.get("checked")}
