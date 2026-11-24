"""Who scored each basket, from the commentator: an add-on of the Live reader (tools/live_reader.py --scorers).

When the reader sends a new score, the basket is queued here. 8 seconds later (the commentator names the scorer as the ball goes in, or just after),
the commentary since the previous basket (at most 35 s: the scoreboard is updated by hand and can be late) is transcribed by Whisper on this Mac
(mlx-whisper, large-v3-turbo, ~1.6 GB downloaded once), the scoring team's player named next to a success word is found (tools/commentary_match.py)
and sent to the site (POST /api/livescore/scorer, same token). The site shows him in the score timeline and adds his points.

The sound comes from the browser playing the game (tools/audiocap.swift, macOS 13+, Screen Recording permission), or from the video file in a test
(--file). It is kept in memory for 90 s and never written anywhere; only the player's name leaves the computer.
"""
import collections
import json
import os
import queue
import subprocess
import threading
import time
import urllib.request

import numpy as np

import commentary_match as cm

RATE = 16000
WAIT = 8.0            # seconds after the score change: the commentator's call
BACK = 35.0           # at most this far back: the board can be updated late
KEEP = 90.0
MODEL = "mlx-community/whisper-large-v3-turbo"
HERE = os.path.dirname(os.path.abspath(__file__))
AUDIOCAP_SRC = os.path.join(HERE, "audiocap.swift")
AUDIOCAP = os.path.join(HERE, "audiocap") if os.path.exists(os.path.join(HERE, "audiocap")) else os.path.expanduser("~/.cache/tunisiabasket/audiocap")   # the installer builds it next to this file


class AppAudio:
    """The sound of the apps showing the game, kept for the last KEEP seconds (wall-clock time)."""

    def __init__(self, apps, log=print):
        self.apps, self.log = sorted(set(apps)), log
        self.chunks = collections.deque()            # (wall time at the end of the chunk, samples)
        self.lock = threading.Lock()
        self.proc = None
        self._start()

    def _start(self):
        if os.path.exists(AUDIOCAP_SRC) and (not os.path.exists(AUDIOCAP) or os.path.getmtime(AUDIOCAP) < os.path.getmtime(AUDIOCAP_SRC)):
            os.makedirs(os.path.dirname(AUDIOCAP), exist_ok=True)
            r = subprocess.run(["swiftc", "-O", AUDIOCAP_SRC, "-o", AUDIOCAP], capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError("could not build the sound capture (xcode-select --install gives swiftc): " + r.stderr[-300:])
        self.proc = subprocess.Popen([AUDIOCAP, *self.apps], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._errors, daemon=True).start()

    def _errors(self):
        for line in self.proc.stderr:
            self.log("sound: " + line.decode(errors="replace").strip())

    def _read(self):
        f = self.proc.stdout
        while True:
            buf = f.read(RATE // 2 * 4)                  # ~0.5 s
            if not buf:
                self.log("sound: the capture stopped (scorers paused)")
                return
            x = np.frombuffer(buf[: len(buf) // 4 * 4], dtype=np.float32)
            now = time.time()
            with self.lock:
                self.chunks.append((now, x))
                while self.chunks and now - self.chunks[0][0] > KEEP:
                    self.chunks.popleft()

    def get(self, t0, t1):
        """Samples between the wall-clock times t0 and t1 (what is still kept), and the time of the first one."""
        with self.lock:
            parts, start = [], None
            for end, x in self.chunks:
                s = end - len(x) / RATE
                if end < t0 or s > t1:
                    continue
                a, b = max(0, int((t0 - s) * RATE)), min(len(x), int((t1 - s) * RATE))
                if b > a:
                    start = s + a / RATE if start is None else start
                    parts.append(x[a:b])
        return (np.concatenate(parts), start) if parts else (np.zeros(0, np.float32), t0)

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


class FileAudio:
    """A test on a recording: the sound of the video file, at the reader's video time (wall time -> video time)."""

    def __init__(self, path, start, speed, t0):
        self.path, self.start, self.speed, self.t0 = path, start, speed, t0

    def get(self, t0, t1):
        v0 = self.start + (t0 - self.t0) * self.speed
        dur = (t1 - t0) * self.speed
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(v0, 0):.2f}", "-t", f"{dur:.2f}", "-i", self.path, "-vn", "-ac", "1",
                              "-ar", str(RATE), "-f", "f32le", "-"], capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.float32), t0

    def close(self):
        pass


class Scorers:
    def __init__(self, server, token, audio, dry=False, log=print, post=None):
        self.server, self.token, self.audio, self.dry, self.log, self.post = server, token, audio, dry, log, post
        self.jobs = queue.Queue()
        self.last = {}                                   # game teams -> wall time of its last basket
        self.rosters = {}
        threading.Thread(target=self._run, daemon=True).start()

    def basket(self, teams, team, pts, score, matchday=None, label=""):
        """A basket the reader has just sent: teams (left, right) as the broadcast shows them, team that scored, pts, score after it (left, right)."""
        now = time.time()
        prev = self.last.get(teams)
        self.last[teams] = now
        t_from = now - BACK if prev is None else max(now - BACK, prev - 5)   # not before the previous basket (its board can be late too)
        self.jobs.put({"teams": list(teams), "team": team, "pts": pts, "score": list(score), "at": now, "from": t_from, "matchday": matchday, "label": label})

    def roster(self, code):
        if code not in self.rosters:
            try:
                req = urllib.request.Request(f"{self.server.rstrip('/')}/api/teams/{code}", headers={"User-Agent": "tunisiabasket-live-reader"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    players = json.loads(r.read())["players"]
                self.rosters[code] = [{"id": p["id"], "number": p.get("number"), "name": p["name"], "gp": p.get("gp")} for p in players]
            except (OSError, ValueError, KeyError) as e:
                self.log(f"scorers: no roster for {code} ({e})")
                return []
        return self.rosters[code]

    def _run(self):
        import mlx_whisper                               # loaded once, in this thread: the reader keeps reading meanwhile
        while True:
            job = self.jobs.get()
            wait = job["at"] + WAIT - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                samples, start = self.audio.get(job["from"], job["at"] + WAIT)
                if len(samples) < RATE * 3:
                    self.log(f"scorers: no sound for {job['label']} (is the game tab muted?)")
                    continue
                t = time.time()
                r = mlx_whisper.transcribe(samples, path_or_hf_repo=MODEL, language="ar", word_timestamps=True, condition_on_previous_text=False)
                words = [{"t": float(start + w["start"]), "w": w["word"].strip()} for seg in r["segments"] for w in seg.get("words", [])]   # plain floats: the body is JSON
                res = cm.who_scored(words, self.roster(job["team"]), job["at"], job["from"])
                p = res["player"]
                body = {"teams": job["teams"], "score": job["score"], "team": job["team"], "pts": job["pts"],
                        "player": {"id": p.get("id"), "number": p.get("number"), "name": p["name"]} if p else None,
                        "conf": res["conf"], "sure": cm.sure(res)}
                if job["matchday"]:
                    body["matchday"] = job["matchday"]
                status, out = (200, {}) if self.dry else self.post(self.server, self.token, body, "/api/livescore/scorer")
                who = f"#{p.get('number')} {p['name']}" if p else "nobody named"
                self.log(f"   scorer {job['label']} {job['team']} +{job['pts']}: {who} ({'sure' if body['sure'] else 'to confirm'}, "
                         f"{time.time() - t:.0f} s)  -> {status} {out.get('error', '')}")
            except Exception as e:                       # one basket's failure must never stop the reader
                self.log(f"scorers: {job['label']} failed ({type(e).__name__}: {e})")
