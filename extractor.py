"""Turn one box-score PDF into a validated game dict, for free.

  1. PDF has a text layer  -> text_parser (exact)
  2. PDF is a scan         -> ocr_parser  (Tesseract, cell by cell, arithmetic-checked)
Returns (game, problems); problems == [] means every consistency check passed.
"""
import datetime
import os
import re

import pdfplumber

from ocr_parser import IMAGE_EXT, parse_scanned_pdf
from text_parser import parse_text_pdf
from validate import validate

SEASON_START = os.environ.get("SEASON_START", "2026-09-28")  # date of matchday 1, used only as a last-resort date
MONTH_NAMES = {"janvier": 1, "jan": 1, "january": 1, "fevrier": 2, "février": 2, "feb": 2, "february": 2,
               "mars": 3, "march": 3, "avril": 4, "april": 4, "mai": 5, "may": 5, "juin": 6, "june": 6,
               "juillet": 7, "july": 7, "aout": 8, "août": 8, "august": 8, "septembre": 9, "september": 9, "sept": 9,
               "octobre": 10, "october": 10, "oct": 10, "novembre": 11, "november": 11, "nov": 11,
               "decembre": 12, "décembre": 12, "december": 12, "dec": 12}


def date_from_filename(name, season_start_year):
    """'SN-ESR  28-10-26.pdf' -> 2026-10-28 ; 'ESS vs USM 10 October (3).pdf' -> 2026-10-10"""
    m = re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})(?!\d)", name)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        try:
            return datetime.date(y, mo, d).isoformat()
        except ValueError:
            pass
    m = re.search(r"(?<!\d)(\d{1,2})\s+([A-Za-zéûô]+)", name)
    if m and m.group(2).lower() in MONTH_NAMES:
        mo = MONTH_NAMES[m.group(2).lower()]
        y = season_start_year if mo >= 8 else season_start_year + 1
        try:
            return datetime.date(y, mo, int(m.group(1))).isoformat()
        except ValueError:
            pass
    return None


def approx_date_from_matchday(matchday):
    """Last resort: matchday N is roughly 4 days after matchday N-1."""
    m = re.match(r"\s*J\s*(\d+)", matchday or "", re.I)
    n = int(m.group(1)) if m else 1
    return (datetime.date.fromisoformat(SEASON_START) + datetime.timedelta(days=4 * (n - 1))).isoformat()


def _has_text_layer(path, page=0):
    if str(path).lower().endswith(IMAGE_EXT):
        return False
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages[page].chars) > 300


def _strip_private(game):
    for t in game["teams"]:
        for p in t["players"]:
            p.pop("_ef", None)


def extract(pdf_path, filename="", matchday="", page=0):
    """pdf_path may be a PDF (any page) or a PNG/JPG image of a box score."""
    season_start_year = int(SEASON_START[:4])
    source = "text" if _has_text_layer(pdf_path, page) else "ocr"
    game = parse_text_pdf(pdf_path, page) if source == "text" else parse_scanned_pdf(pdf_path, page=page)
    if game is None:  # looked like text but wasn't parseable
        source, game = "ocr", parse_scanned_pdf(pdf_path, page=page)

    problems = validate(game)

    game["source"] = source
    game["date_approx"] = False
    if not game.get("date"):
        game["date"] = date_from_filename(filename, season_start_year)
        if not game["date"]:
            game["date"] = approx_date_from_matchday(matchday)
            game["date_approx"] = True
    _strip_private(game)
    return game, problems


if __name__ == "__main__":
    import json
    import sys
    g, probs = extract(sys.argv[1], filename=os.path.basename(sys.argv[1]))
    print(json.dumps(g, indent=1, ensure_ascii=False))
    print("PROBLEMS:", probs or "none")
