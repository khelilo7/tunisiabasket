"""Sync a PUBLIC ("anyone with the link") Google Drive folder: find new PDFs, extract, store.

No Google API key needed: public folders are listed through Drive's embedded folder view.
State (what was already processed / failed) lives in data/state.json, so each run only
touches new files. Games that fail validation go to data/review/ instead of the app.
"""
import hashlib
import html
import json
import os
import re
import tempfile
import time
from pathlib import Path

import requests

import config

ROOT = config.DATA_DIR
GAMES = ROOT / "games"
REVIEW = ROOT / "review"
STATE = ROOT / "state.json"
FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")  # the part of the Drive link after /folders/ (set it in the server settings)


def _key(fid):
    """Opaque id used for our own files and sync state, so the repository and data never contain Drive file links."""
    return "d" + hashlib.sha1(fid.encode()).hexdigest()[:15]
UA = {"User-Agent": "Mozilla/5.0 (basketstats sync)"}


def list_folder(folder_id, path=""):
    """Yield (file_id, name, matchday_folder_name) for every PDF under folder_id."""
    r = requests.get("https://drive.google.com/embeddedfolderview", params={"id": folder_id}, headers=UA, timeout=30)
    r.raise_for_status()
    for m in re.finditer(r'<a href="https://drive\.google\.com/(drive/folders|file/d)/([\w-]+)[^"]*".*?'
                         r'flip-entry-title">([^<]*)<', r.text, re.S):
        kind, fid, name = m.group(1), m.group(2), html.unescape(m.group(3))
        if kind == "drive/folders":
            yield from list_folder(fid, name)
        elif name.lower().endswith(".pdf"):
            yield fid, name, path


def download(file_id, dest):
    r = requests.get("https://drive.usercontent.google.com/download",
                     params={"id": file_id, "export": "download", "confirm": "t"}, headers=UA, timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError("download did not return a PDF (is the file shared with 'anyone with the link'?)")
    Path(dest).write_bytes(r.content)


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    ROOT.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def sync(log=print):
    """One sync pass. Returns a summary dict."""
    from extractor import extract  # free: text layer first, Tesseract OCR for scans

    for d in (GAMES, REVIEW):
        d.mkdir(parents=True, exist_ok=True)
    if not FOLDER_ID:
        raise RuntimeError("DRIVE_FOLDER_ID is not set: sync is off. Set it in /etc/proastats.env (the part of the Drive link after /folders/).")
    state = load_state()
    summary = {"found": 0, "new": 0, "added": 0, "review": 0, "errors": 0}
    for fid, name, folder in list_folder(FOLDER_ID):
        summary["found"] += 1
        k = _key(fid)
        if state.get(k, {}).get("status") in ("ok", "review", "gave_up"):
            continue
        summary["new"] += 1
        log(f"processing {folder} / {name}")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                pdf = Path(tmp) / "game.pdf"
                download(fid, pdf)
                game, problems = extract(str(pdf), filename=name, matchday=folder)
            game.update(id=k, matchday=folder, source_file=name)
            if problems:
                game["problems"] = problems
                (REVIEW / f"{k}.json").write_text(json.dumps(game, indent=1, ensure_ascii=False))
                state[k] = {"status": "review", "name": name, "problems": problems}
                summary["review"] += 1
            else:
                (GAMES / f"{k}.json").write_text(json.dumps(game, indent=1, ensure_ascii=False))
                state[k] = {"status": "ok", "name": name}
                summary["added"] += 1
        except Exception as e:  # keep going; retried on the next pass
            log(f"  failed: {e}")
            e_count = state.get(k, {}).get("attempts", 0) + 1
            state[k] = {"status": "error" if e_count < 3 else "gave_up", "name": name,
                        "error": str(e), "attempts": e_count}
            summary["errors"] += 1
        save_state(state)
    summary["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return summary


if __name__ == "__main__":
    print(sync())
