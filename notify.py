"""Push notifications of the mobile app (Expo push service), each phone choosing what it gets.

  * The app registers its Expo push token with its choice: level "all" (every Pro A result and every news item), "team" (only those about its club),
    or "none" (the token is forgotten); and three switches: results, news, votes (a fan vote or the predictions open). Stored in data/push.json:
    {token: {level, team, lang, results, news, votes, ts}}. A token is an anonymous address for one install of the app; nothing else is kept.
  * A watcher (start(), one thread, every WATCH_EVERY seconds) compares what is published with what was already announced (data/push_state.json) and
    sends what is new: a result typed in the admin or synced, a news item, a vote opening. On its very first run it only records the current state, so a
    deployment never floods phones with old results.
  * Sending goes to https://exp.host in batches of 100; tokens the service reports as gone (app uninstalled) are dropped. PUSH=0 turns sending off (tests).
"""
import json
import logging
import os
import re
import threading
import time
import urllib.request

import config
import content
import mvp
import plays
import predict
import rounds
import stats

FILE = config.DATA_DIR / "push.json"
STATE = config.DATA_DIR / "push_state.json"
EXPO_URL = "https://exp.host/--/api/v2/push/send"
WATCH_EVERY = 60
MAX_TOKENS = 200_000
TOKEN = re.compile(r"^Expo(?:nent)?PushToken\[[A-Za-z0-9_-]{10,80}\]$")
LEVELS = ("all", "team")
TOPICS = ("results", "news", "votes")
_lock = threading.Lock()
_started = False
log = logging.getLogger("notify")


def _read(path, default):
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, type(default)) else default
    except (OSError, ValueError):
        return default


def _write(path, data):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


# ---------------------------------------------------------------- what each phone wants
def register(b: dict):
    """Body {token, level: all | team | none, team, lang, results, news, votes}. Returns (ok, reason)."""
    token = str(b.get("token") or "").strip()
    if not TOKEN.match(token):
        return False, "token"
    level = str(b.get("level") or "")
    team = str(b.get("team") or "").strip().upper()[:8]
    with _lock:
        subs = _read(FILE, {})
        if level == "none":
            subs.pop(token, None)
            _write(FILE, subs)
            return True, "ok"
        if level not in LEVELS:
            return False, "level"
        if team and team not in stats.load_official()["teams"]:
            return False, "team"
        if level == "team" and not team:
            return False, "team"
        if token not in subs and len(subs) >= MAX_TOKENS:
            return False, "full"
        subs[token] = {"level": level, "team": team, "lang": "en" if b.get("lang") == "en" else "fr", **{t: b.get(t) is not False for t in TOPICS}, "ts": int(time.time())}
        _write(FILE, subs)
    return True, "ok"


def _audience(topic: str, teams=()):
    """The tokens that want this: the topic switched on, and level all, or level team with their club among `teams` (votes go to every level)."""
    out = []
    for tok, s in _read(FILE, {}).items():
        if not s.get(topic, True):
            continue
        if topic == "votes" or s.get("level") == "all" or (s.get("level") == "team" and s.get("team") in teams):
            out.append((tok, s.get("lang") or "fr"))
    return out


# ---------------------------------------------------------------- what is new
def _events():
    """Everything that can be announced, as {key: (topic, teams, {lang: (title, body)}, path)}."""
    off = stats.load_official()
    names, season = off["teams"], off.get("season") or ""
    ev = {}
    for r in off["results"]:
        h, a = r["home"], r["away"]
        hs, as_ = r["home_score"], r["away_score"]
        title = f"{h} {hs} – {as_} {a}"
        win = h if hs > as_ else a
        ev[f"result:{season}|{r['matchday']}|{h}-{a}"] = ("results", (h, a), {
            "fr": (title, f"Pro A · J{r['matchday']} · Victoire de {names.get(win, win)}"),
            "en": (title, f"Pro A · Round {r['matchday']} · {names.get(win, win)} win")}, "/scores")
    for n in content.load_news():
        teams = tuple(x for x in (n.get("team"), (n.get("match") or {}).get("home"), (n.get("match") or {}).get("away")) if x)
        fr, en = n.get("title") or "", n.get("title_en") or n.get("title") or ""
        ev[f"news:{n['id']}"] = ("news", teams, {"fr": ("Actu", fr), "en": ("News", en)}, "/news")
    for md, st in rounds.load().items():
        if rounds.is_open(int(md)):
            ev[f"round:{season}|{md}"] = ("votes", (), {"fr": ("Joueur de la journée", f"Vote pour le meilleur joueur de la J{md}"),
                                                         "en": ("Player of the round", f"Vote for the best player of round {md}")}, "/votes")
    for ph in mvp.PHASES:
        if mvp.voting_open(ph):
            ev[f"mvp:{season}|{ph}"] = ("votes", (), {"fr": ("MVP de la phase", f"Le vote du MVP de la phase {ph} est ouvert"),
                                                     "en": ("Phase MVP", f"Voting for the MVP of phase {ph} is open")}, "/votes")
    for w in plays.load()["weeks"]:
        if plays.is_open(w):
            ev[f"plays:{w['id']}"] = ("votes", (), {"fr": ("Action de la semaine", f"{w.get('title') or ''} : vote pour la plus belle action".strip(" :")),
                                                   "en": ("Play of the week", f"{w.get('title') or ''}: vote for the best play".strip(" :"))}, "/plays")
    r = predict._round()
    if r and r["open"]:
        ev[f"predict:{season}|{r['matchday']}"] = ("votes", (), {"fr": ("Pronostics", f"Les pronostics de la J{r['matchday']} sont ouverts"),
                                                                "en": ("Predictions", f"Predictions for round {r['matchday']} are open")}, "/votes")
    return ev


def check(send=True):
    """Announce what was never announced. Returns the number of messages sent (0 on the first run, which only records)."""
    ev = _events()
    with _lock:
        state = _read(STATE, {})
        seen = set(state.get("seen") or [])
        first = not state.get("init")
        new = [k for k in ev if k not in seen]
        _write(STATE, {"init": True, "seen": sorted(seen | set(ev))[-5000:]})
    if first or not new:
        return 0
    msgs = []
    for k in new:
        topic, teams, text, path = ev[k]
        for tok, lang in _audience(topic, teams):
            title, body = text.get(lang) or text["fr"]
            msgs.append({"to": tok, "title": title, "body": body, "sound": "default", "channelId": "default", "data": {"path": path}})
    if send and os.environ.get("PUSH", "1") == "1":
        _send(msgs)
    return len(msgs)


def _send(msgs):
    gone = set()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if os.environ.get("EXPO_ACCESS_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["EXPO_ACCESS_TOKEN"]
    for i in range(0, len(msgs), 100):
        batch = msgs[i:i + 100]
        try:
            req = urllib.request.Request(EXPO_URL, data=json.dumps(batch).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read() or b"{}").get("data") or []
        except Exception as e:           # a failed batch is not retried: a late "final score" is worse than none
            log.warning("push batch failed: %s", e)
            continue
        for m, t in zip(batch, res):
            if t.get("status") == "error" and (t.get("details") or {}).get("error") == "DeviceNotRegistered":
                gone.add(m["to"])
    if gone:
        with _lock:
            subs = _read(FILE, {})
            for t in gone:
                subs.pop(t, None)
            _write(FILE, subs)


def _loop():
    while True:
        try:
            check()
        except Exception as e:           # notifications must never take the site down
            log.warning("push check failed: %s", e)
        time.sleep(WATCH_EVERY)


def start():
    global _started
    if not _started and os.environ.get("PUSH", "1") == "1":
        _started = True
        threading.Thread(target=_loop, daemon=True).start()
