"""Live score reader: reads the Diwan Sport scoreboard off the screen (or off a video file, to test) and sends the score to the site (/api/livescore, see livescore.py).

Run it on a Mac that plays the game(s) in a browser signed in to Diwan Sport, ONE WINDOW PER GAME (not tabs: a browser only draws its front tab), each window big
enough for the scoreboard to be readable (half a screen is plenty). The windows may stay behind other windows while you use the Mac, but not minimised; if one is
completely covered and the browser stops drawing it, the reader says so (leave a corner visible):

    .venv/bin/python tools/live_reader.py --token XXXX-XXXX-XXXX-XXXX                      # every Firefox/Safari window titled "Diwan Sport", even behind others
    .venv/bin/python tools/live_reader.py --screen --token ...                             # the whole screen instead
    .venv/bin/python tools/live_reader.py --file game.mp4 --start 1500 --show --server http://localhost:5055 --token ...   # a recording played in real time (test)

Needs tesseract (brew install tesseract) and, for the screen, the Screen Recording permission of the app that runs it (System Settings > Privacy & Security).
Nothing is recorded: each capture is read in memory and dropped; only the numbers leave the computer.

How it reads: the scoreboard's two score boxes and its quarter box are dark-blue boxes on one line, found by colour wherever the video is on the screen (several games at once
are fine); every other field is placed from them. Each field is read with tesseract. A new score is sent only once two captures in a row agree, it never goes down (a lower score
of 1 to 3 points seen for 30 s in a row is sent as a correction), and a jump of more than 6 points is ignored as a misread, unless the scoreboard was away for a while (started mid-game,
replays, a dropped stream): then three captures must agree. The final is sent when the clock shows 00:00 in the 4th quarter or
an overtime with the scores not level, three captures in a row.
"""
import argparse
import difflib
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

import numpy as np
from PIL import Image

try:
    import macos_ocr                                                              # next to this file
except ImportError:                                                           # not found (a copy without it): tesseract does everything
    macos_ocr = type('NoOcr', (), {'available': staticmethod(lambda: False)})

# where each field is, relative to the left score box, in pixels of the 1080p broadcast (that box is 66 x 61 px there)
BOX_W, BOX_H = 66, 61
FIELDS = {"home": (3, 2, 63, 59), "away": (73, 2, 133, 59), "q": (369, 2, 432, 59), "clock": (440, 0, 572, 61),   # boxes read just inside their edges
          "t_left": (-160, 4, -20, 56), "t_right": (150, 4, 270, 56)}
# the second layout (24 November 2026, ESS-USM): [quarter badge][clock] [code][logo] [blue panel: both scores] [code][logo], team fouls as dots under the codes.
# Offsets are in pixels of a panel 130 px wide (the panel's own width sets the scale), from its top-left corner.
BOX_W_B = 130
FIELDS_B = {"home": (3, 2, 63, 46), "away": (68, 2, 128, 46), "q": (-364, 8, -338, 42), "clock": (-308, 8, -218, 42), "t_left": (-110, 8, -52, 40), "t_right": (226, 8, 292, 40)}
WL = {"home": "0123456789", "away": "0123456789", "q": "Q1234OT", "clock": "0123456789:.", "t_left": "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "t_right": "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}


# ---------------------------------------------------------------- finding the scoreboard(s)
def find_boards(rgb):
    """[(x, y, scale)] of every scoreboard: the top-left corner of its left score box and the size of that box relative to 66 px."""
    from scipy import ndimage                                                 # only the Mac reader needs scipy (tools/install_live_reader.sh installs it), not the server
    a = rgb.astype(np.int16)
    navy = (a[..., 2] > 80) & (a[..., 2] - a[..., 0] > 60) & (a[..., 0] < 70) & (a[..., 1] < 110)
    navy = ndimage.binary_fill_holes(navy)                                    # the white digits inside a box
    lab, n = ndimage.label(navy)
    boxes = []
    for sl in ndimage.find_objects(lab):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        w, h = x1 - x0, y1 - y0
        if 14 <= h <= 200 and 0.9 <= w / h <= 2.2:
            boxes.append((x0, y0, w, h))
    out = []
    for x0, y0, w, h in boxes:
        s = w / BOX_W                                                         # by the width: some players cut the bottom of the scoreboard off
        # the right score box just after it, the quarter box further on, all on the same line and the same height
        same = lambda bx, dx: abs(bx[1] - y0) <= 4 * s and abs(bx[3] - h) <= 5 * s and abs(bx[0] - (x0 + dx * s)) <= 12 * s
        if any(same(b, 70) for b in boxes) and any(same(b, 367) for b in boxes):
            out.append((x0, y0, s))
    # two adjacent score boxes both pass as "left" only if the layout repeats; keep the left-most of each line
    out.sort()
    keep = []
    for b in out:
        if not any(abs(b[1] - k[1]) < 10 and abs(b[0] - k[0]) < 200 * b[2] for k in keep):
            keep.append(b)
    return keep + find_boards_b(rgb)


def find_boards_b(rgb):
    """[(x, y, scale, "B")] of every scoreboard of the second layout: one blue panel holding both scores, a light panel with the clock to its left (the first layout
    has navy boxes and no light panel, and the bar shown at half-time, with the Arabic names, has no clock panel either)."""
    from scipy import ndimage
    h = rgb.shape[0]
    top = int(h * 0.5)                                                        # the bar sits in the lower half of the window
    a = rgb[top:].astype(np.int16)
    blue = (a[..., 2] > 95) & (a[..., 2] - a[..., 0] > 40) & (a[..., 2] - a[..., 1] > 15)
    blue = ndimage.binary_fill_holes(ndimage.binary_closing(blue, structure=np.ones((3, 5))))
    lab, _n = ndimage.label(blue)
    gray = np.asarray(Image.fromarray(rgb).convert("L")).astype(np.int16)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        y0, y1, x0, x1 = sl[0].start + top, sl[0].stop + top, sl[1].start, sl[1].stop
        w, bh = x1 - x0, y1 - y0
        if not (50 <= w <= 420 and 14 <= bh <= 130 and 1.6 <= w / bh <= 6.5) or (lab[sl] == i).sum() < 0.55 * w * bh:
            continue
        s = w / BOX_W_B
        y_a, y_b = int(y0 + 8 * s), int(y0 + 40 * s)
        zone = lambda a, b: gray[y_a:y_b, max(0, int(x0 + a * w)):max(0, int(x0 + b * w))]
        clock, code_l, code_r = zone(-2.8, -1.8), zone(-1.15, -0.35), zone(1.15, 2.4)   # the light clock panel; the dark bar around both team codes
        if y_b > rgb.shape[0] or x0 - 2.8 * w < 0 or not clock.size or not code_l.size or not code_r.size:
            continue
        if (clock > 120).mean() >= 0.45 and (code_l < 95).mean() >= 0.7 and (code_r < 95).mean() >= 0.7:
            out.append((x0, y0, s, "B"))
    return out


def field_img(rgb, board, name):
    x, y, s = board[:3]
    kind = board[3] if len(board) > 3 else "A"
    fx0, fy0, fx1, fy1 = (FIELDS_B if kind == "B" else FIELDS)[name]
    box = (int(x + fx0 * s), int(y + fy0 * s), int(x + fx1 * s), int(y + fy1 * s))
    g = np.asarray(Image.fromarray(rgb).crop(box).convert("L")).astype(np.int16)
    if kind == "B":                                                           # B: the clock is dark on a light panel; codes, scores and quarter are light on dark or blue.
        lo, hi = np.percentile(g, [8, 97])                                    # The lights differ from one broadcast to the next: the threshold is the middle of this
        mid = (lo + hi) / 2                                                   # field's own range (nothing at all when there is no contrast: an empty box)
        ink = (g < mid if name == "clock" else g > mid) & (hi - lo > 35)
    else:
        ink = g < 110 if name.startswith("t_") or name == "clock" else g > 150  # team codes and clock: dark on white; scores and quarter: white on dark blue
    if name in ("home", "away", "q"):                                         # marks touching the crop's edge are slivers of the box's border or of the bar
        from scipy import ndimage                                             # around it (some players squash the scoreboard), never a digit: erase them
        lab, _ = ndimage.label(ink)
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        if edge:
            ink = ink & ~np.isin(lab, list(edge))
    im = Image.fromarray(np.where(ink, 0, 255).astype(np.uint8))
    k = 100 / max(1, im.height)
    im = im.resize((max(1, int(im.width * k)), 100), Image.LANCZOS)
    if kind == "B" and name in ("home", "away"):                              # the second layout's score digits are so bold that tesseract reads 38 as nothing and 46 as 66:
        from scipy import ndimage                                             # one step thinner and it reads them
        im = Image.fromarray(np.where(ndimage.binary_erosion(np.asarray(im) < 128), 0, 255).astype(np.uint8))
    cv = Image.new("L", (im.width + 40, 140), 255)
    cv.paste(im, (20, 20))
    return cv


def ocr(img, wl):
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(tmp)
        r = subprocess.run(["tesseract", tmp, "-", "--psm", "7", "-c", f"tessedit_char_whitelist={wl}"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip().replace(" ", "")
    finally:
        os.remove(tmp)


def read_board(rgb, board, fields=("home", "away", "q", "clock")):
    out = {}
    for f in fields:
        if len(board) > 3 and board[3] == "B" and f in ("home", "away") and macos_ocr.available():   # the bold digits of the second layout: tesseract reads 44 as 464
            x, y, s = board[:3]
            fx0, fy0, fx1, fy1 = FIELDS_B[f]
            out[f] = macos_ocr.read_digits(rgb[int(y + fy0 * s):int(y + fy1 * s), int(x + fx0 * s):int(x + fx1 * s)])
        else:
            out[f] = ocr(field_img(rgb, board, f), WL[f])
    return out


def parse(r):
    """{'home': '28', 'away': '32', 'q': 'Q2', 'clock': '01:09'} -> (28, 32, 2, '01:09') or None. An empty score box is 0."""
    try:                                                                      # an empty box is None: the broadcast shows 0 as an empty box, but a box also goes
        h = int(r["home"]) if r["home"] else None                             # empty for a moment by a graphics glitch (Game.update decides which)
        a = int(r["away"]) if r["away"] else None
    except ValueError:
        return None
    q = r["q"].upper()
    if "T" in q:                                                              # OT, OT1, OT2... (the O is sometimes read as 0)
        d = q.split("T")[-1]
        qn = 4 + (int(d) if d.isdigit() and int(d) >= 1 else 1)
    elif q and q[-1] in "1234":                                               # Q2, or 2 (some broadcasts show no Q), or 22 (the Q read as a 2): the last digit
        qn = int(q[-1])
    else:
        return None
    c = (r["clock"] or "").strip(".:")
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", c) or re.fullmatch(r"(\d{1,2})\.(\d)", c)   # 01:09, 00.48 (colon read as a dot), 45.3 (last minute)
    c = c if m and int(m.group(1)) <= 12 or (m and len(m.group(2)) == 1) else None             # 20:08 or .07 are misreads: keep the last good clock
    return h, a, qn, c


def clock_zero(c):
    return c is not None and all(ch in "0:." for ch in c)


def clock_secs(c):
    try:
        m, sec = c.replace(".", ":").split(":")[:2]
        return int(m) * 60 + int(sec)
    except (AttributeError, ValueError):
        return None


# ---------------------------------------------------------------- captures
def grab_screen(display=1):
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        r = subprocess.run(["screencapture", "-x", "-t", "png", "-D", str(display), tmp], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.getsize(tmp):
            raise RuntimeError("screen capture refused: give the Screen Recording permission to the app running this (System Settings > Privacy & Security), then restart it")
        return np.asarray(Image.open(tmp).convert("RGB"))
    finally:
        os.remove(tmp)


WINLIST = os.path.expanduser("~/.cache/tunisiabasket/winlist")
WINLIST_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "winlist.swift")


def windows(title):
    """[(id, app, on screen)] of the windows whose title contains `title` (case does not matter), front first. Builds tools/winlist.swift once."""
    if os.path.exists(WINLIST_SRC) and (not os.path.exists(WINLIST) or os.path.getmtime(WINLIST) < os.path.getmtime(WINLIST_SRC)):
        os.makedirs(os.path.dirname(WINLIST), exist_ok=True)
        r = subprocess.run(["swiftc", "-O", WINLIST_SRC, "-o", WINLIST], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("could not build the window lister (xcode-select --install gives swiftc): " + r.stderr[-300:])
    out, titled, rows = [], 0, 0
    for line in subprocess.run([WINLIST], capture_output=True, text=True).stdout.splitlines():
        f = line.split("\t")
        if len(f) < 6:
            continue
        rows += f[4] == "1"
        titled += bool(f[5].strip())
        if title.lower() in f[5].lower() and int(f[2]) > 300:
            out.append((int(f[0]), f[1], f[4] == "1"))
    if rows and not titled:                                                   # macOS gives window titles only to an app allowed to record the screen
        raise RuntimeError("screen capture refused: give the Screen Recording permission to the app running this (System Settings > Privacy & Security), then restart it")
    return out


def grab_window(wid):
    """One window's own picture, even when other windows cover it (not when it is minimised)."""
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        r = subprocess.run(["screencapture", "-x", "-o", "-t", "png", f"-l{wid}", tmp], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.getsize(tmp):
            return None
        return np.asarray(Image.open(tmp).convert("RGB"))
    finally:
        os.remove(tmp)


def grab_file(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")) if raw else None


# ---------------------------------------------------------------- one game followed
class Game:
    def __init__(self, teams):
        self.teams = teams                  # (left code, right code) as the broadcast shows them
        self.sent = None                    # (h, a, q) last sent
        self.cand, self.cand_n = None, 0    # a new reading waiting for confirmation
        self.low, self.low_n = None, 0      # a lower score seen again and again (a correction by the table)
        self.zero_n = 0
        self.final = False
        self.last_post = 0.0
        self.last_seen = time.time()
        self.clock = None
        self.prev = None

    def update(self, h, a, q, c):
        """Returns the body to send, or None."""
        cur0 = self.sent or (0, 0, 1)
        h = h if h is not None else (0 if cur0[0] == 0 else cur0[0])          # an empty box: 0 while that team has 0, otherwise the score it had
        a = a if a is not None else (0 if cur0[1] == 0 else cur0[1])
        now = time.time()
        gap = now - self.last_seen > 20 or self.sent is None       # started mid-game, or the scoreboard was away (replays, ads, a dropped stream): bigger jumps are possible
        self.clock = c or self.clock
        self.last_seen = now
        cur = self.sent or (0, 0, 1)
        out = None
        if self.sent is None or (h, a) != cur[:2] or q != cur[2]:              # the very first reading is sent even at 0-0: the site then knows the game started on time
            big = h - cur[0] > 6 or a - cur[1] > 6 or q - cur[2] > 1
            if h < cur[0] or a < cur[1]:                                      # a lower score: a correction by the table (1 to 3 points, seen for 30 s), or a misread
                small = cur[0] - h <= 3 and cur[1] - a <= 3 and h >= cur[0] - 3 and a >= cur[1] - 3
                self.low_n = self.low_n + 1 if self.low == (h, a, q) and small else (1 if small else 0)
                self.low = (h, a, q)
                if self.low_n >= 15:
                    out = self._body(h, a, max(q, cur[2]), fix=True)
            elif q >= cur[2] and (not big or gap or self.cand == (h, a, q)):
                self.cand_n = self.cand_n + 1 if self.cand == (h, a, q) else 1
                self.cand = (h, a, q)
                if self.cand_n >= (3 if big else 2):                 # a big jump needs a third capture that agrees
                    out = self._body(h, a, q)
        else:
            self.cand, self.cand_n, self.low, self.low_n = None, 0, None, 0
        # the final buzzer: 00:00 in Q4 or overtime, the scores not level
        s = self.sent or (h, a, q)
        if s[2] >= 4 and clock_zero(c) and s[0] != s[1] and (h, a) == s[:2]:
            self.zero_n += 1
            if self.zero_n >= 3 and not self.final:
                self.final = True
                out = self._body(*s, final=True)
        else:
            self.zero_n = 0
        pending_q = self.cand is not None and self.cand[2] > self.sent[2] if self.sent else False
        if out is None and self.sent and time.time() - self.last_post > 10 and not pending_q:   # a heartbeat with the clock: the game stays live on the site
            out = self._body(*self.sent)
        return out

    def gone(self):
        """The scoreboard has not been seen for a while: if that happened in the last seconds of the 4th quarter or an overtime with the scores not level,
        the broadcast has cut away after the buzzer (it often never shows 00:00). Returns the final to send, or None."""
        s = self.sent
        if self.final or not s or s[2] < 4 or s[0] == s[1] or time.time() - self.last_seen < 90:
            return None
        left = clock_secs(self.clock)
        if left is None or left > 5:
            return None
        self.final = True
        return self._body(*s, final=True)

    def _body(self, h, a, q, fix=False, final=False):
        self.prev = self.sent                 # the score before this one: who scored what (--scorers)
        self.sent = (h, a, q)
        self.last_post = time.time()
        self.cand, self.cand_n, self.low, self.low_n = None, 0, None, 0
        b = {"teams": list(self.teams), "score": [h, a], "q": q, "clock": self.clock}
        if fix:
            b["fix"] = True
        if final:
            b["final"] = True
        return b


def post(server, token, body, path="/api/livescore"):
    req = urllib.request.Request(server.rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + token, "User-Agent": "tunisiabasket-live-reader"})
    def body(raw, code):                                                      # an error page of Cloudflare or a route the site does not have yet is HTML, not JSON
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            return {"error": f"HTTP {code}: not a reply of the site"}
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, body(r.read(), r.status)
    except urllib.error.HTTPError as e:
        return e.code, body(e.read(), e.code)
    except OSError as e:
        return 0, {"error": str(e)}


def known_teams(server):
    try:
        req = urllib.request.Request(server.rstrip("/") + "/api/schedule", headers={"User-Agent": "tunisiabasket-live-reader"})   # Cloudflare refuses Python's default one
        with urllib.request.urlopen(req, timeout=10) as r:
            return list(json.loads(r.read())["teams"])
    except (OSError, ValueError, KeyError):
        return []


def live_now(server):
    """The games read from a broadcast that the Live page shows now: "id<TAB>HOME 70 - 66 AWAY  FINAL" (or the quarter)."""
    try:
        req = urllib.request.Request(server.rstrip("/") + "/api/live", headers={"User-Agent": "tunisiabasket-live-reader", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=10) as r:
            games = json.loads(r.read())["games"]
    except (OSError, ValueError, KeyError):
        return []
    out = []
    for g in games:
        if g.get("source") != "scoreboard":
            continue
        h, w = g["home"], g["away"]
        q = (g.get("clock") or {}).get("q") or 0
        state = "FINAL" if g.get("final") else f"Q{q}" if 1 <= q <= 4 else f"OT{q - 4}" if q > 4 else ""
        out.append(f"{g['id']}\t{h} {g['teams'][h]['score']} - {g['teams'][w]['score']} {w}  {state}")
    return out


def snap(code, codes):
    code = (code or "").upper()
    if not codes or code in codes:
        return code or None
    m = difflib.get_close_matches(code, codes, n=1, cutoff=0.5)
    return m[0] if m else None


def send(a, g, body, vt):
    if a.matchday:
        body["matchday"] = a.matchday
    stamp = time.strftime("%H:%M:%S") + (f"  video {int(vt // 60)}:{int(vt % 60):02d}" if a.file else "")
    status, res = (200, {}) if a.dry else post(a.server, a.token, body)
    what = "FINAL" if body.get("final") else "fix" if body.get("fix") else ""
    print(f"{stamp}  {g.teams[0]} {body['score'][0]} - {body['score'][1]} {g.teams[1]}  Q{body['q']} {body['clock'] or ''} {what}  -> {status} {res.get('error', '')}", flush=True)
    sc = getattr(a, "_scorers", None)
    if sc and status == 200 and not body.get("fix") and g.prev:                # a basket: the commentator will say who scored it
        for side in (0, 1):
            d = body["score"][side] - g.prev[side]
            if 1 <= d <= 3:
                sc.basket(g.teams, g.teams[side], d, body["score"], a.matchday, label=f"{g.teams[0]} {body['score'][0]}-{body['score'][1]} {g.teams[1]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server", default="https://tunisiabasket.com")
    ap.add_argument("--token", default=os.environ.get("LIVESCORE_TOKEN", ""))
    ap.add_argument("--every", type=float, default=2.0, help="seconds between two captures")
    ap.add_argument("--title", default="Diwan", help="read the windows whose title contains this (default: Diwan), even behind other windows")
    ap.add_argument("--screen", action="store_true", help="read the whole screen instead of the game windows")
    ap.add_argument("--winlist", help="a prebuilt window lister (tools/install_live_reader.sh makes one)")
    ap.add_argument("--display", type=int, default=1, help="with --screen: which screen (1 = main)")
    ap.add_argument("--file", help="read a video file in real time instead of the screen (test)")
    ap.add_argument("--start", type=float, default=0, help="with --file: where to start, in seconds")
    ap.add_argument("--speed", type=float, default=1.0, help="with --file: playback speed")
    ap.add_argument("--show", action="store_true", help="with --file: also play the video in a window (ffplay), in step with the reading")
    ap.add_argument("--teams", help="LEFT-RIGHT codes as the scoreboard shows them, if its team names cannot be read (e.g. ESS-DSG)")
    ap.add_argument("--matchday", type=int, help="the matchday, if the calendar cannot tell (e.g. a test on an old game)")
    ap.add_argument("--dry", action="store_true", help="read and print, send nothing")
    ap.add_argument("--scorers", action="store_true", help="also say who scored each basket, from the commentator (tools/live_scorer.py: needs mlx-whisper)")
    ap.add_argument("--listen", nargs="+", metavar="APP", help="with --scorers: the apps whose sound to listen to (default: those showing the game windows)")
    ap.add_argument("--live", action="store_true", help="list the games read from a broadcast that are on the Live page now (id, then the score), and stop")
    ap.add_argument("--remove", nargs="+", metavar="ID", help="take these games (ids from --live) off the Live page now, and stop")
    a = ap.parse_args()
    if a.live:
        for g in live_now(a.server):
            print(g, flush=True)
        return
    if not a.token and not a.dry:
        sys.exit("--token (or LIVESCORE_TOKEN) is required: python manage.py new-livescore-token on the server")
    if a.remove:
        for gid in a.remove:
            status, res = post(a.server, a.token, {"id": gid}, "/api/livescore/stop")
            print(f"{gid}: {'taken off the Live page' if status == 200 else 'not removed'} -> {status} {res.get('error', '')}", flush=True)
        return
    if a.winlist:
        global WINLIST, WINLIST_SRC
        WINLIST, WINLIST_SRC = os.path.abspath(a.winlist), ""
    codes = known_teams(a.server)
    if not codes:
        print(f"could not get the list of teams from {a.server}: team names will only be read as they are", flush=True)
    games = {}                                  # (left, right) teams -> Game
    t0 = time.time()
    if a.scorers:
        try:
            import live_scorer
            __import__("mlx_whisper")                   # checked now: a missing package must not wait for the first basket
        except ImportError as e:
            sys.exit(f"--scorers needs mlx-whisper in this Python ({e}): pip install mlx-whisper")
        log = lambda m: print(m, flush=True)
        if a.file:
            audio = live_scorer.FileAudio(a.file, a.start, a.speed, t0)
        else:
            apps = a.listen or sorted({app for _, app, _ in windows(a.title)})
            if not apps:
                sys.exit(f"--scorers: no '{a.title}' window open to listen to (or give --listen APP)")
            audio = live_scorer.AppAudio(apps, log)
            if len(apps) == 1 and len(windows(a.title)) > 1:
                print(f"--scorers: several games in {apps[0]}: their sounds are mixed (one browser per game keeps them apart)", flush=True)
        a._scorers = live_scorer.Scorers(a.server, a.token, audio, a.dry, log, post)
        print(f"scorers: on (the commentator's words, ~{live_scorer.WAIT:.0f} s after each basket)", flush=True)
    if a.file and a.show:
        subprocess.Popen(["ffplay", "-v", "error", "-ss", str(a.start), "-x", "960", "-y", "540", "-window_title", "Diwan Sport (test)", a.file],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    print(f"reading {'the file ' + a.file if a.file else 'the screen'} every {a.every:g} s, sending to {a.server}{' (dry run)' if a.dry else ''}", flush=True)
    first, last_hint, last_found = True, 0.0, time.time()
    seen = {}                                   # source -> (picture fingerprint, since): a window whose picture never changes is not being drawn
    naming = {}                                 # board -> the team names read so far, before it is followed
    placed = {}                                 # board position -> the teams of the game shown there
    warned = {}
    # stopping the reader (the app's Stop, its Terminal window closed, Ctrl-C) takes its games off the Live pages at once
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
    try:
        while True:
            tick = time.time()
            vt = a.start + (tick - t0) * a.speed
            try:
                if a.file:
                    rgb = grab_file(a.file, vt)
                    if rgb is None:
                        print("end of the video", flush=True)
                        break
                    sources = [("file", rgb)]
                elif a.screen:
                    sources = [("screen", grab_screen(a.display))]
                else:
                    sources = []
                    for wid, app, on in windows(a.title):
                        if not on:
                            if tick - warned.get(("min", wid), 0) > 60:
                                print(f"a '{a.title}' window of {app} is minimised or on another desktop: it cannot be read (behind other windows is fine)", flush=True)
                                warned[("min", wid)] = tick
                            continue
                        rgb = grab_window(wid)
                        if rgb is not None:
                            sources.append((f"w{wid}", rgb))
            except RuntimeError as e:
                sys.exit(str(e))
            if first:
                what = f"{len(sources)} '{a.title}' window(s)" if not (a.file or a.screen) else f"{sources[0][1].shape[1]}x{sources[0][1].shape[0]} px"
                print(f"capture works ({what}); looking for the Diwan scoreboard...", flush=True)
                first = False
            found = False
            for src, rgb in sources:
                if src.startswith("w"):                                           # a window not redrawn for 20 s: Firefox stops drawing a window that is fully covered
                    fp = hash(rgb[::16, ::16].tobytes())
                    old = seen.get(src)
                    seen[src] = (fp, old[1]) if old and old[0] == fp else (fp, tick)
                    if tick - seen[src][1] > 20 and tick - warned.get(src, 0) > 60:
                        print("a game window has not changed for 20 s: is the game paused, or the window completely covered? Leave a corner of it visible.", flush=True)
                        warned[src] = tick
                boards = find_boards(rgb)
                found = found or bool(boards)
                for board in boards:
                    key = (src, round(board[0] / 40), round(board[1] / 40))
                    g = games.get(placed.get(key))
                    if g is None:
                        if a.teams:
                            teams = tuple(a.teams.upper().split("-"))
                        else:                                                     # the team names must be read the same three times in a row: one misread would follow the wrong game
                            r = read_board(rgb, board, ("t_left", "t_right"))
                            teams = (snap(r["t_left"], codes), snap(r["t_right"], codes))
                            votes = naming.setdefault(key, [])
                            votes.append(teams)
                            if len(votes) < 3 or len(set(votes[-3:])) > 1:
                                if len(votes) >= 10 and tick - warned.get(("names", key), 0) > 60:
                                    print(f"a scoreboard ({src}): team names not read reliably ({votes[-3:]}), use --teams", flush=True)
                                    warned[("names", key)] = tick
                                continue
                        if not all(teams):
                            print(f"a scoreboard ({src}): team names not readable, use --teams", flush=True)
                            continue
                        placed[key] = teams                                       # a game is the two teams: if its scoreboard moves (the window is resized), it is the same game
                        if teams in games:
                            g = games[teams]
                        else:
                            g = games[teams] = Game(teams)
                            print(f"following {teams[0]} - {teams[1]}", flush=True)
                    p = parse(read_board(rgb, board))
                    if not p:
                        continue
                    body = g.update(*p)
                    if body:
                        send(a, g, body, vt)
            if found:
                last_found = tick
            elif tick - last_found > 15 and tick - last_hint > 30:               # nothing found for a while: say so, and why it may be
                print("no scoreboard found: is a game playing in a window titled 'Diwan Sport' (one window per game, not tabs), big enough (half the screen)? Replays and ads hide it too.", flush=True)
                last_hint = tick
            for g in games.values():
                body = g.gone()
                if body:
                    send(a, g, body, vt)
            time.sleep(max(0.0, a.every - (time.time() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        if not a.dry:
            for g in games.values():
                if g.sent:
                    status, res = post(a.server, a.token, {"teams": list(g.teams), **({"matchday": a.matchday} if a.matchday else {})}, "/api/livescore/stop")
                    try:                                                      # the window may already be gone (closed Terminal): printing can fail
                        print(f"stopped: {g.teams[0]} - {g.teams[1]} taken off the Live page -> {status} {res.get('error', '')}", flush=True)
                    except OSError:
                        pass


if __name__ == "__main__":
    main()
