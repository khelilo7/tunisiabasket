"""Free OCR parser for scanned (image-only) box-score PDFs, using the Tesseract command-line tool.

How it stays accurate:
  1. The table grid is found from its ruled lines, so every cell is OCR'd on its own.
  2. Each cell is read at 3 sizes with a digits-only whitelist and the readings are voted.
  3. The box score's own arithmetic repairs leftovers: REB = OR + DR, FG = 2P + 3P,
     PTS = 2*2P + 3*3P + FT, and column sums must equal the Totals row.
Anything still inconsistent is reported by validate.py and goes to manual review.
"""
import io
import itertools
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pdfplumber
from PIL import Image

import tesseract

COLS = ["no", "name", "min", "fgma", "fgp", "p2ma", "p2p", "p3ma", "p3p", "ftma", "ftp",
        "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts"]
SKIP = {"fgp", "p2p", "p3p"}  # percentages are recomputed, never read (FT% is read only as a tie-breaker)
COLS_EF = COLS[:-1] + ["ef", "pts"]  # variant layout with an Efficiency column
INT_COLS = ["oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "fd", "pm", "pts"]
HEIGHTS = (36, 40, 44)
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ '-()."


def _tess(img, whitelist, h=40, psm=7, binarize=True, pad=40):
    w0, h0 = img.size
    im = img.resize((max(1, int(w0 * h / h0)), h), Image.LANCZOS)
    if binarize:
        im = im.point(lambda v: 0 if v < 150 else 255)
    cv = Image.new("L", (im.width + 2 * pad, h + 2 * pad), 255)
    cv.paste(im, (pad, pad))
    buf = io.BytesIO()
    cv.save(buf, "PNG")
    args = ["--psm", str(psm), "-l", "eng", "--dpi", "300"]
    if whitelist:
        args += ["-c", f"tessedit_char_whitelist={whitelist}"]
    return tesseract.run(args, buf.getvalue())


def _groups(vals, gap=2):
    out = []
    for v in vals:
        if out and v - out[-1][-1] <= gap:
            out[-1].append(v)
        else:
            out.append([v])
    return [int(np.mean(g)) for g in out]


def _longest_run(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def _ink_crop(img, pad=2):
    a = np.array(img) < 150
    if not a.any():
        return None
    ys, xs = np.where(a)
    return img.crop((max(0, xs.min() - pad), max(0, ys.min() - pad), xs.max() + 1 + pad, ys.max() + 1 + pad))


BASE = ((36, 7), (40, 7), (44, 7))
EXTRA = ((28, 7), (100, 7), (44, 8), (60, 8), (80, 8), (100, 8), (36, 8))


def _vote(img, whitelist, parse):
    """Read a cell with several tesseract settings. Cheap pass first; if the readings are not
    unanimous (tesseract is flaky on lone digits) escalate to more settings. Most-voted first."""
    votes = Counter()
    empties = 0
    for h, psm in BASE:
        v = parse(_tess(img, whitelist, h, psm).replace(" ", ""))
        if v is None:
            empties += 1
        else:
            votes[v] += 1
    if empties or len(votes) > 1:
        for h, psm in EXTRA:
            v = parse(_tess(img, whitelist, h, psm).replace(" ", ""))
            if v is not None:
                votes[v] += 1
    return [v for v, _ in votes.most_common()]


def _read_int(img, signed=False):
    """Candidate integer readings of a number cell, most-voted first."""
    pat = re.compile(r"-?\d+" if signed else r"\d+")
    return _vote(img, "0123456789-" if signed else "0123456789",
                 lambda t: int(t) if pat.fullmatch(t) else None) or [0]


def _read_signed(img):
    """+/- cell: a leading dash is a short flat glyph, detected by geometry (OCR often drops it)."""
    a = np.array(img) < 150
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
    if len(runs) >= 2:
        hs = [int(np.ptp(np.where(a[:, x0:x1].any(1))[0])) + 1 for x0, x1 in runs]
        if hs[0] < 0.35 * max(hs[1:]):
            rest = _ink_crop(img.crop((runs[1][0], 0, img.width, img.height)))
            return [-v for v in _read_int(rest)] if rest else [0]
    return _read_int(img, signed=True)


def _read_pair(img):
    def parse(t):
        m = re.fullmatch(r"(\d+)/(\d+)", t)
        return (int(m.group(1)), int(m.group(2))) if m and int(m.group(1)) <= int(m.group(2)) else None
    return _vote(img, "0123456789/", parse)  # [] when unreadable: repaired from FG = 2P + 3P


def _read_pct(img):
    def parse(t):
        m = re.fullmatch(r"(\d{1,3})[,.](\d)", t)
        return float(f"{m.group(1)}.{m.group(2)}") if m else None
    return _vote(img, "0123456789,.", parse)


def _read_min(img):
    def parse(t):
        m = re.fullmatch(r"(\d{1,3}):(\d\d)", t)
        return round(int(m.group(1)) + int(m.group(2)) / 60, 2) if m and int(m.group(2)) < 60 else None
    return _vote(img, "0123456789:", parse)


def _read_number_cell(img):
    """Jersey number cell: optional '*' (starter) followed by 1-2 digits."""
    a = np.array(img) < 150
    cols = a.any(0)
    runs, s = [], None
    for x, v in enumerate(cols):
        if v and s is None:
            s = x
        if not v and s is not None:
            runs.append((s, x))
            s = None
    if s is not None:
        runs.append((s, len(cols)))
    if not runs:
        return -1, False
    heights = [int(np.ptp(np.where(a[:, x0:x1].any(1))[0])) + 1 for x0, x1 in runs]
    starter = len(runs) > 1 and heights[0] < 0.7 * max(heights[1:]) and (runs[0][1] - runs[0][0]) < 1.2 * heights[0]
    digits = img.crop((runs[1][0] if starter else runs[0][0], 0, img.width, img.height))
    digits = _ink_crop(digits)
    return (_read_int(digits)[0] if digits else -1), starter


def _read_name(img):
    votes = Counter()
    for h in (40, 48, 36):
        t = re.sub(r"\s+", " ", _tess(img, LETTERS, h)).strip()
        if t:
            votes[t] += 1
    return votes.most_common(1)[0][0] if votes else ""


def _cell_job(args):
    gray, box, kind = args
    c = _ink_crop(gray.crop(box))
    if c is None:
        return None
    if kind == "name":
        return _read_name(c)
    if kind == "no":
        return _read_number_cell(c)
    if kind == "min":
        return _read_min(c)
    if kind == "ma":
        return _read_pair(c)
    if kind == "pct":
        return _read_pct(c)
    return _read_signed(c) if kind == "pm" else _read_int(c)


KIND = {"no": "no", "name": "name", "min": "min", "fgma": "ma", "p2ma": "ma", "p3ma": "ma", "ftma": "ma", "ftp": "pct", "pm": "pm", "ef": "pm"}


def _repair_player(c, ftp=None):
    """c: dict field -> candidate list (most-voted first). Pick the most-voted combination that satisfies
    the arithmetic. Unreadable or doubtful shooting cells get extra candidates derived from the others."""
    keys = ["fgma", "p2ma", "p3ma", "ftma", "oreb", "dreb", "reb", "pts"]
    c = {k: list(v) for k, v in c.items()}
    # FG = 2P + 3P: derive each of the three from the other two (appended after the OCR readings).
    for tgt, a, b, op in (("fgma", "p2ma", "p3ma", 1), ("p2ma", "fgma", "p3ma", -1), ("p3ma", "fgma", "p2ma", -1)):
        for x in c[a][:3]:
            for y in c[b][:3]:
                d = (x[0] + op * y[0], x[1] + op * y[1])
                if 0 <= d[0] <= d[1] and d not in c[tgt]:
                    c[tgt].append(d)
    # Free throws: made = PTS - 2*2PM - 3*3PM; attempts from the FT% cell when the pair is unreadable.
    if not c["ftma"]:
        for pts in c["pts"][:3]:
            for p2 in c["p2ma"][:3]:
                for p3 in c["p3ma"][:3]:
                    ftm = pts - 2 * p2[0] - 3 * p3[0]
                    if ftm < 0:
                        continue
                    for fta in range(max(ftm, 1) if ftm else 0, ftm + 16):
                        pct = 100.0 * ftm / fta if fta else 0.0
                        if not ftp or any(abs(pct - q) < 0.06 for q in ftp[:2]):
                            if (ftm, fta) not in c["ftma"]:
                                c["ftma"].append((ftm, fta))
    if any(not c[k] for k in ("fgma", "p2ma", "p3ma", "ftma")):
        return None
    opts = [c[k][:6] for k in keys]
    best, best_rank = None, None
    for combo in itertools.product(*opts):
        v = dict(zip(keys, combo))
        if v["fgma"][0] != v["p2ma"][0] + v["p3ma"][0] or v["fgma"][1] != v["p2ma"][1] + v["p3ma"][1]:
            continue
        if v["reb"] != v["oreb"] + v["dreb"]:
            continue
        if v["pts"] != 2 * v["p2ma"][0] + 3 * v["p3ma"][0] + v["ftma"][0]:
            continue
        rank = sum(c[k].index(x) for k, x in v.items())  # lower = more votes
        if best is None or rank < best_rank:
            best, best_rank = v, rank
    return best


def _repair_ef(p, c):
    """EF = PTS+REB+AST+STL+BLK - missed FG - missed FT - TOV. If it doesn't hold, fix one misread cell."""
    def ef(q):
        return (q["pts"] + q["reb"] + q["ast"] + q["stl"] + q["blk"]
                - (q["fga"] - q["fgm"]) - (q["fta"] - q["ftm"]) - q["tov"])
    if ef(p) == p["_ef"]:
        return
    fixes = []
    for k in ("ast", "tov", "stl", "blk"):
        for alt in c[k][1:]:
            if ef({**p, k: alt}) == p["_ef"]:
                fixes.append((k, alt))
    for alt in list(c["ef"][1:]) + [-p["_ef"]]:  # or the EF cell itself was misread (often a lost minus sign)
        if ef(p) == alt:
            fixes.append(("_ef", alt))
    if len(fixes) == 1:
        p[fixes[0][0]] = fixes[0][1]


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
PAGE_WIDTH_PX = 2481  # an A4 page at 300 dpi: all pixel sizes in this parser assume this scale


def load_gray(path, page=0, dpi=300):
    """Grayscale image of a PDF page or an image file, normalised to A4 @ 300 dpi width."""
    if str(path).lower().endswith(IMAGE_EXT):
        img = Image.open(path)
        img.load()
        img = img.convert("L")
        if abs(img.width - PAGE_WIDTH_PX) > 40:
            img = img.resize((PAGE_WIDTH_PX, round(img.height * PAGE_WIDTH_PX / img.width)), Image.LANCZOS)
        return img
    with pdfplumber.open(path) as pdf:
        return pdf.pages[page].to_image(resolution=dpi).original.convert("L")


def page_count(path):
    if str(path).lower().endswith(IMAGE_EXT):
        return 1
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def parse_scanned_pdf(path, dpi=300, page=0):
    gray = load_gray(path, page, dpi)
    dark = np.array(gray) < 140
    H, W = dark.shape
    hy = _groups([y for y in range(H) if dark[y].sum() / W > 0.6 and _longest_run(dark[y]) / W > 0.7])
    spacing = float(np.median(np.diff(hy)))
    blocks, cur = [], [hy[0]]
    for y in hy[1:]:
        if y - cur[-1] > 2.3 * spacing:
            blocks.append(cur)
            cur = [y]
        else:
            cur.append(y)
    blocks.append(cur)
    tables = [b for b in blocks if len(b) >= 10][:2]
    if len(tables) < 2:
        raise ValueError("could not find the two team tables")

    jobs, layout = [], []
    for lines in tables:
        band = dark[lines[1]:lines[-3]]
        f = band.sum(0) / band.shape[0]
        xs = _groups([x for x in range(W) if f[x] > 0.85])
        if len(xs) == len(COLS) + 1:
            cols = COLS
        elif len(xs) == len(COLS_EF) + 1:
            cols = COLS_EF
        else:
            raise ValueError(f"unknown table layout: {len(xs)-1} columns")
        rows = lines[1:]
        rlist = []
        for r in range(len(rows) - 1):
            y0, y1 = rows[r] + 4, rows[r + 1] - 4
            idx = {}
            for ci, col in enumerate(cols):
                if col in SKIP:
                    continue
                if col in ("no", "name", "min") and r >= len(rows) - 3:
                    continue  # Team/Coach and Totals rows: labels, not data
                idx[col] = len(jobs)
                jobs.append((gray, (xs[ci] + 4, y0, xs[ci + 1] - 4, y1), KIND.get(col, "int")))
            rlist.append(idx)
        head = gray.crop((xs[0], lines[0] - 85, int(xs[-1] * 0.8), lines[0] - 5))
        layout.append((rlist, head))

    with ThreadPoolExecutor(tesseract.workers()) as ex:
        res = list(ex.map(_cell_job, jobs))
        heads = list(ex.map(lambda h: _tess(_ink_crop(h) or h, "", 60, 7, False, 30), [l[1] for l in layout]))

    teams = []
    for (rlist, _), head in zip(layout, heads):
        m = re.search(r"\(([A-Za-z0-9 ]{2,6})\)", head)
        code = re.sub(r"\s+", "", m.group(1)).upper() if m else "?"
        tname = re.sub(r"\(.*", "", head).strip().title()
        players, cands = [], []
        team_row, totals_row = None, None
        for ri, idx in enumerate(rlist):
            g = lambda c: res[idx[c]]
            if ri == len(rlist) - 1:
                totals_row = {k: (g(k) or [0])[0] for k in INT_COLS if k in idx}
                totals_row.update({k: (g(k) or [(0, 0)])[0] for k in ("p2ma", "p3ma", "ftma") if k in idx})
                continue
            if ri == len(rlist) - 2:
                team_row = {k: (g(k) or [0])[0] for k in INT_COLS if k in idx}
                continue
            nm = g("name") or ""
            captain = bool(re.search(r"\(\s*[CO]\s*\)?|\bC\)", nm.upper()))
            pname = re.sub(r"\(.*|\s*\bC\)", "", nm).strip()
            if not pname:
                continue
            no, starter = g("no") if g("no") else (-1, False)
            mins = g("min")
            p = {"number": no, "name": pname, "starter": starter, "captain": captain, "dnp": not mins}
            c = None
            if mins:
                p["min"] = mins[0]
                c = {k: g(k) for k in ["fgma", "p2ma", "p3ma", "ftma"] + INT_COLS if k in idx}
                best = _repair_player(c, g("ftp") if "ftp" in idx else None)
                if best is None:  # no consistent combination: keep top votes, validate.py will flag it
                    best = {k: (c[k] or [(0, 0)])[0] for k in ("fgma", "p2ma", "p3ma", "ftma", "oreb", "dreb", "reb", "pts")}
                (p["fgm"], p["fga"]), (p["p2m"], p["p2a"]) = best["fgma"], best["p2ma"]
                (p["p3m"], p["p3a"]), (p["ftm"], p["fta"]) = best["p3ma"], best["ftma"]
                for k in ("oreb", "dreb", "reb", "pts"):
                    p[k] = best[k]
                for k in ("ast", "tov", "stl", "blk", "pf", "fd", "pm"):
                    p[k] = c[k][0]
                if "ef" in idx:
                    c["ef"] = g("ef")
                    p["_ef"] = c["ef"][0]
                    _repair_ef(p, c)
            players.append(p)
            cands.append(c)

        # Column sums vs Totals row (player rows + Team/Coach row): fix single-cell misreads.
        if totals_row and team_row:
            for k in ("ast", "tov", "stl", "blk", "pf", "fd"):
                want = totals_row.get(k)
                have = sum(p[k] for p in players if not p["dnp"]) + team_row.get(k, 0)
                if want is None or have == want:
                    continue
                fixes = []
                for p, c in zip(players, cands):
                    if c and len(c[k]) > 1:
                        for alt in c[k][1:]:
                            if have - p[k] + alt == want:
                                fixes.append((p, alt))
                if len(fixes) == 1:  # only apply an unambiguous fix
                    fixes[0][0][k] = fixes[0][1]

        # Team points: the Totals cell, unless a misread is proven by the Totals row's own shooting line.
        psum = sum(p.get("pts", 0) for p in players if not p["dnp"])
        pts = (totals_row or {}).get("pts")
        if totals_row and pts != psum:
            implied = 2 * totals_row["p2ma"][0] + 3 * totals_row["p3ma"][0] + totals_row["ftma"][0]
            if implied == psum:
                pts = psum
        teams.append({"code": code, "name": tname, "coach": "", "points": pts, "players": players, "_cands": cands})

    _repair_plus_minus(teams)
    for t in teams:
        t.pop("_cands", None)
    return {"competition": "", "date": None, "teams": teams}


def _repair_plus_minus(teams):
    """Sum of +/- over a team's players == 5 x (team points - opponent points). Fix one misread cell."""
    if any(t["points"] is None for t in teams):
        return
    for t, o in ((teams[0], teams[1]), (teams[1], teams[0])):
        want = 5 * (t["points"] - o["points"])
        played = [(p, c) for p, c in zip(t["players"], t["_cands"]) if not p["dnp"]]
        have = sum(p["pm"] for p, _ in played)
        if have == want:
            continue
        fixes = set()
        for p, c in played:
            alts = set(c["pm"][1:]) | {-p["pm"]}
            for alt in alts:
                if have - p["pm"] + alt == want:
                    fixes.add((id(p), alt))
        if len(fixes) == 1:
            pid_, alt = next(iter(fixes))
            for p, _ in played:
                if id(p) == pid_:
                    p["pm"] = alt


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(parse_scanned_pdf(sys.argv[1]), indent=1, ensure_ascii=False))
