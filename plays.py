"""Play of the week: the fans vote for the best action of the week among a few video clips the admin picked.

  * The admin creates a week (a title such as "J12"), adds clips (a YouTube or Facebook link, or a direct .mp4 address, with a title and optionally the player and
    his club), opens the vote, closes it (or lets an optional deadline end it), and may crown a clip whatever the votes say.
  * One final vote per device, a handful per network, crawlers refused, only hashes stored: the same rules and the same database as the other fan votes
    (data/votes.db, table play_votes, which refuses changes and deletions).
  * The winner is the admin's crown, else the clip with most votes once the vote has ended (a tie goes to the clip listed first). The latest week stays on show,
    with its winner, until the next week is opened; earlier winners make the archive.
Settings live in data/plays.json: {"weeks": [{"id", "title", "clips": [{"id", "title", "player", "team", "url"}], "open", "deadline", "winner", "opened_at", "closed_at", "created"}]}
(newest last).
"""
import json
import re
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

import auth
import config
import mvp
import traffic

FILE = config.DATA_DIR / "plays.json"
MAX_CLIPS = 8
MAX_VOTERS_PER_NETWORK = mvp.MAX_VOTERS_PER_NETWORK
ARCHIVE = 12
_lock = threading.Lock()

YOUTUBE = re.compile(r"^https://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
FACEBOOK = re.compile(r"^https://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.watch)/\S+$")
FILE_URL = re.compile(r"^https://[A-Za-z0-9.-]+\.[A-Za-z]{2,}/\S+\.(?:mp4|m4v|mov|webm)(?:\?\S*)?$", re.I)


def video(url: str):
    """What the app needs to show a clip: {kind: youtube | facebook | file, url, embed, thumb}; None for an address it cannot play."""
    url = (url or "").strip()
    m = YOUTUBE.match(url)
    if m:
        vid = m.group(1)
        return {"kind": "youtube", "url": f"https://www.youtube.com/watch?v={vid}", "embed": f"https://www.youtube.com/embed/{vid}?playsinline=1&rel=0",
                "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
    if FILE_URL.match(url):
        return {"kind": "file", "url": url, "embed": url, "thumb": None}
    if FACEBOOK.match(url):
        return {"kind": "facebook", "url": url, "embed": "https://www.facebook.com/plugins/video.php?" + urllib.parse.urlencode({"href": url, "show_text": "false"}),
                "thumb": None}
    return None


# ---------------------------------------------------------------- settings
def load() -> dict:
    try:
        raw = json.loads(FILE.read_text())
    except (OSError, ValueError):
        raw = {}
    weeks = [w for w in (raw.get("weeks") or []) if isinstance(w, dict) and w.get("id")]
    return {"weeks": weeks}


def _write(data: dict):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(FILE)


def _deadline(w):
    try:
        return mvp.parse_deadline(w.get("deadline"))
    except ValueError:
        return None


def is_open(w: dict) -> bool:
    dl = _deadline(w)
    return bool(w.get("open")) and (dl is None or datetime.now(timezone.utc) < dl)


def _ended(w: dict) -> bool:
    return bool(w.get("opened_at")) and not is_open(w)


def _week(data, wid):
    return next((w for w in data["weeks"] if w["id"] == wid), None)


# ---------------------------------------------------------------- votes
def tally(wid: str) -> dict:
    with mvp._lock:
        con = mvp._db()
        try:
            return dict(con.execute("SELECT clip, COUNT(*) FROM play_votes WHERE week=? GROUP BY clip", (wid,)))
        finally:
            con.close()


def my_vote(wid: str, vid: str):
    if not mvp.VID.match(vid or ""):
        return None
    with mvp._lock:
        con = mvp._db()
        try:
            r = con.execute("SELECT clip FROM play_votes WHERE week=? AND voter=?", (wid, mvp._hash("pvid", wid, vid))).fetchone()
            return r[0] if r else None
        finally:
            con.close()


def cast(request, wid: str, clip: str, vid: str):
    """(ok, reason): ok | bot | browser | closed | week | clip | already | network. A vote is final."""
    ua = request.headers.get("User-Agent", "")
    if not ua or traffic.BOT.search(ua):
        return False, "bot"
    if not mvp.VID.match(vid or ""):
        return False, "browser"
    w = _week(load(), wid)
    if not w:
        return False, "week"
    if not is_open(w):
        return False, "closed"
    if clip not in {c["id"] for c in w.get("clips") or []}:
        return False, "clip"
    voter, net = mvp._hash("pvid", wid, vid), mvp._hash("pnet", wid, auth.visitor_ip())
    with mvp._lock:
        con = mvp._db()
        try:
            if con.execute("SELECT 1 FROM play_votes WHERE week=? AND voter=?", (wid, voter)).fetchone():
                return False, "already"
            if con.execute("SELECT COUNT(*) FROM play_votes WHERE week=? AND net=?", (wid, net)).fetchone()[0] >= MAX_VOTERS_PER_NETWORK:
                return False, "network"
            con.execute("INSERT INTO play_votes VALUES (?,?,?,?,?)", (wid, voter, net, clip, int(time.time())))
            con.commit()
        finally:
            con.close()
    return True, "ok"


# ---------------------------------------------------------------- what fans see
def _rows(w: dict) -> list:
    votes = tally(w["id"])
    rows = []
    for c in w.get("clips") or []:
        v = video(c.get("url"))
        if v:
            rows.append({**{k: c.get(k) or "" for k in ("id", "title", "player", "team")}, **v, "votes": votes.get(c["id"], 0)})
    total = sum(r["votes"] for r in rows)
    for r in rows:
        r["vote_share"] = round(100 * r["votes"] / total) if total else 0
    return rows


def _winner(w: dict, rows: list):
    if w.get("winner"):
        x = next((r for r in rows if r["id"] == w["winner"]), None)
        if x:
            return x
    if not _ended(w):
        return None
    best = max(rows, key=lambda r: r["votes"], default=None)          # max keeps the first of equals: a tie goes to the clip listed first
    return best if best and best["votes"] else None


def view(vid: str = "") -> dict:
    """{week: the latest opened week or None, archive: [{id, title, winner}] of the earlier ones}. Vote shares show once you voted or the vote ended."""
    weeks = [w for w in load()["weeks"] if w.get("opened_at")]
    out = {"week": None, "archive": []}
    if not weeks:
        return out
    cur = weeks[-1]
    for w in reversed(weeks[:-1]):
        win = _winner(w, _rows(w))
        if win:
            out["archive"].append({"id": w["id"], "title": w.get("title") or "", "winner": win})
        if len(out["archive"]) >= ARCHIVE:
            break
    rows = _rows(cur)
    mine = my_vote(cur["id"], vid)
    op = is_open(cur)
    reveal = bool(mine) or not op
    if not reveal:
        for r in rows:
            r["votes"] = r["vote_share"] = None
    dl = _deadline(cur)
    out["week"] = {"id": cur["id"], "title": cur.get("title") or "", "open": op, "deadline_ts": int(dl.timestamp()) if dl and op else None,
                   "clips": rows, "my_vote": mine, "total_votes": sum(r["votes"] or 0 for r in rows) if reveal else None, "winner": _winner(cur, _rows(cur)) if not op or cur.get("winner") else None}
    return out


# ---------------------------------------------------------------- admin
def admin_view() -> dict:
    out = []
    for w in reversed(load()["weeks"]):
        rows = _rows(w)
        bad = [c for c in w.get("clips") or [] if not video(c.get("url"))]
        win = _winner(w, rows)
        out.append({**{k: w.get(k) for k in ("id", "title", "deadline", "winner")}, "state": "open" if is_open(w) else ("closed" if w.get("opened_at") else "draft"),
                    "clips": rows, "unplayable": bad, "votes": sum(r["votes"] for r in rows), "leader": win["id"] if win else None})
    return {"weeks": out, "max_clips": MAX_CLIPS}


def _clean(s, n):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def act(b: dict):
    """b: {op: create | add | remove | open | close | crown | delete, week, title, url, player, team, clip, deadline, winner}. Returns (ok, message, week id)."""
    op = str(b.get("op") or "")
    with _lock:
        data = load()
        if op == "create":
            title = _clean(b.get("title"), 60)
            if not title:
                return False, "Give the week a title (for example J12).", None
            wid = "w" + uuid.uuid4().hex[:8]
            data["weeks"].append({"id": wid, "title": title, "clips": [], "open": False, "deadline": None, "winner": None, "opened_at": None, "closed_at": None,
                                  "created": int(time.time())})
            _write(data)
            return True, f"Week “{title}” created: add its clips, then open the vote.", wid
        w = _week(data, str(b.get("week") or ""))
        if not w:
            return False, "Unknown week.", None
        votes = sum(tally(w["id"]).values())
        if op == "add":
            if len(w["clips"]) >= MAX_CLIPS:
                return False, f"At most {MAX_CLIPS} clips a week.", w["id"]
            url = str(b.get("url") or "").strip()
            if not video(url):
                return False, "Paste a YouTube or Facebook video link, or a direct https address of an .mp4 file.", w["id"]
            title = _clean(b.get("title"), 80)
            if not title:
                return False, "Give the clip a short title (for example: Dunk over two defenders).", w["id"]
            cid = "c" + uuid.uuid4().hex[:8]
            w["clips"].append({"id": cid, "title": title, "player": _clean(b.get("player"), 60), "team": _clean(b.get("team"), 8).upper(), "url": url})
            msg = "Clip added."
        elif op == "remove":
            if votes:
                return False, "Fans already voted: the clips can no longer be removed.", w["id"]
            w["clips"] = [c for c in w["clips"] if c["id"] != b.get("clip")]
            msg = "Clip removed."
        elif op == "open":
            if len([c for c in w["clips"] if video(c.get("url"))]) < 2:
                return False, "Add at least two clips before opening the vote.", w["id"]
            other = next((x for x in data["weeks"] if x is not w and is_open(x)), None)
            if other:
                return False, f"Close the vote of “{other.get('title')}” first: one vote at a time.", w["id"]
            try:
                dl = mvp.parse_deadline(b.get("deadline") or None)
            except ValueError:
                return False, "The deadline must look like 2026-11-14T12:00 (Tunisian time).", w["id"]
            w.update(open=True, deadline=dl.astimezone(mvp.TUNIS).isoformat(timespec="minutes") if dl else None, opened_at=w.get("opened_at") or int(time.time()), closed_at=None)
            data["weeks"] = [x for x in data["weeks"] if x is not w] + [w]          # the opened week becomes the latest one, the one on show
            msg = "The vote is open: the app and the site show it now."
        elif op == "close":
            w.update(open=False, closed_at=int(time.time()))
            msg = "The vote is closed: the winner stays on show until the next week is opened."
        elif op == "crown":
            win = b.get("winner") or None
            if win and win not in {c["id"] for c in w["clips"]}:
                return False, "Only a clip of this week can be crowned.", w["id"]
            w["winner"] = win
            msg = "Crowned." if win else "The crown is removed: the fans decide."
        elif op == "delete":
            if votes:
                return False, "Fans already voted for this week: it stays (votes are final).", w["id"]
            data["weeks"] = [x for x in data["weeks"] if x is not w]
            msg = "Week deleted."
        else:
            return False, "Unknown action.", w["id"]
        _write(data)
        return True, msg, w["id"]
