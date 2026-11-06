"""Read a federation 'SCORE FINAL' graphic (one matchday: white bars 'CSS 68 X 46 ESR') into results.

Bars are found by colour (white rounded bars on a red background); each bar is OCR'd with Tesseract
after cutting away the club logos. Team codes are snapped to the known league codes. Scores are
plain integers. Returns warnings for anything doubtful: the admin UI shows an editable preview
before anything is saved.
"""
import difflib
import io
import re

import numpy as np
from PIL import Image

import config
import tesseract


def _tess(img, psm=7, wl=None, h=70, invert=False):
    w0, h0 = img.size
    im = img.convert("L").resize((max(1, int(w0 * h / h0)), h), Image.LANCZOS)
    im = im.point(lambda v: 0 if v < 120 else 255)  # black text on white
    if invert:
        im = im.point(lambda v: 255 - v)
    cv = Image.new("L", (im.width + 60, h + 60), 255)
    cv.paste(im, (30, 30))
    buf = io.BytesIO()
    cv.save(buf, "PNG")
    args = ["--psm", str(psm), "-l", "eng", "--dpi", "300"]
    if wl:
        args += ["-c", f"tessedit_char_whitelist={wl}"]
    return tesseract.run(args, buf.getvalue())


def _groups(idx, gap=3):
    out = []
    for y in idx:
        if out and y - out[-1][-1] <= gap:
            out[-1].append(int(y))
        else:
            out.append([int(y)])
    return [(g[0], g[-1]) for g in out]


def find_bars(rgb):
    """Row bands that are mostly white across the middle of the image and have the typical bar height."""
    a = np.array(rgb)
    H, W, _ = a.shape
    white = a.min(2) > 215
    frac = white[:, int(.30 * W):int(.70 * W)].mean(1)
    bands = [b for b in _groups(np.where(frac > 0.45)[0]) if H * 0.025 < b[1] - b[0] < H * 0.08]
    if not bands:
        return []
    # the big 'SCORE FINAL' title also looks white: keep bands with a height close to the most common one
    hs = np.array([b[1] - b[0] for b in bands])
    med = np.median(hs)
    return [b for b in bands if 0.8 * med < b[1] - b[0] < 1.25 * med]


def read_matchday(rgb):
    """'JOURNÉE 01' in the header (white text on red)."""
    W, H = rgb.size
    top = rgb.crop((int(W * .25), int(H * .06), int(W * .75), int(H * .125)))
    g = np.array(top.convert("L"))
    txt = _tess(Image.fromarray(g), psm=7, h=80, invert=True)
    m = re.search(r"(\d{1,2})\s*$", txt) or re.search(r"(\d{1,2})", txt)
    return (int(m.group(1)) if m else None), txt


def _ink_bbox(img, thr=120, pad=3):
    a = np.array(img.convert("L")) < thr
    if not a.any():
        return None
    ys, xs = np.where(a)
    return img.crop((max(0, xs.min() - pad), max(0, ys.min() - pad), xs.max() + 1 + pad, ys.max() + 1 + pad))


TEMPLATE_FILE = config.ASSETS_DIR / "digit_templates.npz"
_templates = None


def _glyph_features(gray_crop):
    """Binary-ish 20x28 picture of one digit plus its aspect ratio."""
    a = np.array(gray_crop.convert("L"))
    ink = a < 130
    ys, xs = np.where(ink)
    g = Image.fromarray(255 - a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]).resize((20, 28), Image.LANCZOS)
    aspect = (xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1)
    return np.concatenate([np.array(g, dtype=float).ravel() / 255.0, [aspect * 3]])


def split_glyphs(img):
    """Split a score crop into single-digit crops (column runs of dark ink)."""
    a = np.array(img.convert("L")) < 130
    if not a.any():
        return []
    cols = a.any(0)
    runs, st = [], None
    for x, v in enumerate(cols):
        if v and st is None:
            st = x
        if not v and st is not None:
            runs.append((st, x))
            st = None
    if st is not None:
        runs.append((st, len(cols)))
    runs = [(x0, x1) for x0, x1 in runs if x1 - x0 >= 3]
    return [img.crop((x0, 0, x1, img.height)) for x0, x1 in runs]


def _read_digits(img):
    """Score -> int using the digit-shape templates (trained from known results); Tesseract is the fallback."""
    global _templates
    if _templates is None and TEMPLATE_FILE.exists():
        d = np.load(TEMPLATE_FILE)
        _templates = (d["X"], d["y"])
    glyphs = split_glyphs(img)
    if _templates is not None and 2 <= len(glyphs) <= 3:
        X, y = _templates
        out = ""
        for g in glyphs:
            f = _glyph_features(g)
            out += str(int(y[np.argmin(((X - f) ** 2).sum(1))]))
        return int(out)
    c = _ink_bbox(img)
    if c is None:
        return None
    for h in (70, 50, 90):
        m = re.fullmatch(r"\d{2,3}", _tess(c, wl="0123456789", h=h).replace(" ", ""))
        if m:
            return int(m.group())
    return None


def _similarity(read, code):
    r = re.sub(r"[^A-Z]", "", read.upper())
    if not r:
        return 0.0
    score = difflib.SequenceMatcher(None, r, code).ratio()
    if code in r:
        score += 0.5  # the true code is fully contained in the OCR text (extra letters are logo noise)
    elif r in code:
        score += 0.2
    return score


def _assign(reads, codes):
    """Give every slot a different code, maximising total similarity (bitmask DP; 12 codes = 4096 states)."""
    n, m = len(reads), len(codes)
    sim = [[_similarity(r, c) for c in codes] for r in reads]
    best = {0: (0.0, [])}
    for i in range(n):
        nxt = {}
        for mask, (sc, picks) in best.items():
            for j in range(m):
                if mask >> j & 1:
                    continue
                v = sc + sim[i][j]
                k = mask | 1 << j
                if k not in nxt or v > nxt[k][0]:
                    nxt[k] = (v, picks + [j])
        best = nxt
    sc, picks = max(best.values(), key=lambda t: t[0])
    return [codes[j] for j in picks], [sim[i][j] for i, j in enumerate(picks)]


def bar_crops(rgb, arr, band):
    """(left_score, right_score, left_code, right_code) crops of one bar, or None if the red X is missing."""
    y0, y1 = band
    u = y1 - y0  # bar height: all horizontal offsets scale with it (same template at every image size)
    mid = arr[y0:y1, int(.30 * arr.shape[1]):int(.70 * arr.shape[1])].astype(int)
    red = (mid[..., 0] > 140) & (mid[..., 1] < 90) & (mid[..., 2] < 90)
    if red.sum() < 20:
        return None
    cx = int(.30 * arr.shape[1]) + int(np.median(np.where(red)[1]))  # the red X is the anchor
    top, bot = y0 + 5, y1 - 5
    return (rgb.crop((cx - int(1.55 * u), top, cx - int(.30 * u), bot)),
            rgb.crop((cx + int(.30 * u), top, cx + int(1.55 * u), bot)),
            rgb.crop((cx - int(3.25 * u), top, cx - int(1.75 * u), bot)),
            rgb.crop((cx + int(1.75 * u), top, cx + int(3.25 * u), bot)))


def parse_results_image(path, known_codes):
    """Returns {"kind": "results"|"standings"|"unknown", "matchday": int|None, "games": [...], "warnings": [...]}"""
    rgb = Image.open(path).convert("RGB")
    arr = np.array(rgb)
    bars = find_bars(rgb)
    warnings = []
    if len(bars) >= 10:
        return {"kind": "standings", "matchday": None, "games": [],
                "warnings": ["This looks like a standings table. Standings are computed from results, so it is not needed."]}
    if not bars:
        return {"kind": "unknown", "matchday": None, "games": [], "warnings": ["No result bars found in this image."]}
    codes = list(known_codes)
    raw = []  # per bar: (left code text, right code text, home score, away score)
    for band in bars:
        crops = bar_crops(rgb, arr, band)
        if crops is None:
            raw.append(("", "", None, None))
            continue
        left_score, right_score, left_code, right_code = crops
        lt = _tess(_ink_bbox(left_code) or left_code, wl="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        rt = _tess(_ink_bbox(right_code) or right_code, wl="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        raw.append((lt, rt, _read_digits(left_score), _read_digits(right_score)))

    reads = [t for r in raw for t in (r[0], r[1])]
    if len(reads) <= len(codes):
        assigned, sims = _assign(reads, codes)
    else:
        assigned, sims = reads, [1.0] * len(reads)
    games = []
    for i, (lt, rt, hs, as_) in enumerate(raw):
        h, a = assigned[2 * i], assigned[2 * i + 1]
        if sims[2 * i] < 0.6 or sims[2 * i + 1] < 0.6:
            warnings.append(f"Bar {i + 1}: team names read as {lt!r} / {rt!r}; please check {h} / {a}.")
        if hs is None or as_ is None:
            warnings.append(f"Bar {i + 1} ({h} - {a}): a score could not be read; please enter it.")
        games.append({"home": h, "away": a, "home_score": hs, "away_score": as_, "raw": f"{lt} | {rt}"})
    md, mdtxt = read_matchday(rgb)
    if md is None:
        warnings.append(f"Matchday number not found in the header (read {mdtxt!r}); please enter it.")
    if len(games) != len(codes) // 2:
        warnings.append(f"Found {len(games)} games, expected {len(codes) // 2}.")
    return {"kind": "results", "matchday": md, "games": games, "warnings": warnings}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(parse_results_image(sys.argv[1], ["CA", "JSK", "USM", "ESS", "DSG", "CSS", "ESG", "SN", "JSM", "ESR", "USA", "CSHS"]),
                     indent=1, ensure_ascii=False))
