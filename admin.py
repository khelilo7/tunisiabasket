"""Admin tool: drop PDFs / images / ZIP stacks -> parsed to JSON -> review & edit -> saved into the app's data.

  box score PDF or image  -> extractor (text layer or Tesseract OCR) -> data/games/<id>.json
  federation results image -> results_parser                          -> data/official.json (results)

Nothing is saved until you press Save on the reviewed item. Protect it with ADMIN_TOKEN (sent as the
X-Admin-Token header); without a token only requests from this computer (localhost) are accepted.
"""
import hashlib
import io
import json
import os
import queue
import re
import threading
import time
import uuid
import zipfile
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_from_directory

import auth
import config
import stats
import mvp
import traffic
from extractor import extract
from ocr_parser import IMAGE_EXT, page_count
from results_parser import bar_crops, find_bars, parse_results_image
from validate import validate

bp = Blueprint("admin", __name__)
ROOT = config.DATA_DIR
UPLOADS, GAMES, REVIEW = ROOT / "uploads", ROOT / "games", ROOT / "review"
OFFICIAL = ROOT / "official.json"
MAX_ZIP_ENTRY = 60 * 1024 * 1024
ALLOWED = (".pdf",) + IMAGE_EXT

JOBS: dict[str, dict] = {}
_q: "queue.Queue[tuple[str, dict]]" = queue.Queue()
_file_lock = threading.Lock()


# ---------------------------------------------------------------- auth
PUBLIC = {"admin.page", "admin.login_route", "admin.me"}


@bp.before_request
def _auth():
    """Every admin endpoint needs a logged-in admin, except the page shell, login and the 'am I admin' probe."""
    if request.endpoint in PUBLIC:
        return None
    auth.require_admin()


@bp.post("/admin/api/login")
def login_route():
    if not auth.same_origin_ok():
        abort(403)
    return auth.login((request.get_json(silent=True) or {}).get("token", ""))


@bp.post("/admin/api/logout")
def logout_route():
    return auth.logout()


@bp.get("/admin/api/me")
def me():
    return jsonify(admin=auth.is_admin(), configured=auth.token_configured())


@bp.get("/admin")
def page():
    return send_from_directory("static", "admin.html")


# ---------------------------------------------------------------- helpers
def _safe_name(name: str) -> str:
    name = os.path.basename(name.replace("\\", "/"))
    return re.sub(r"[^A-Za-z0-9._ ()-]", "_", name)[:120] or "file"


def _official():
    return json.loads(OFFICIAL.read_text())


def _write_official(o):
    tmp = OFFICIAL.with_suffix(".tmp")
    tmp.write_text(json.dumps(o, indent=1, ensure_ascii=False))
    tmp.replace(OFFICIAL)


def _classify_image(path: Path) -> str:
    """results graphic (red banner with white score bars) or box score photo/scan."""
    from PIL import Image
    import numpy as np
    try:
        rgb = Image.open(path).convert("RGB")
        bars = find_bars(rgb)
        if len(bars) >= 3:
            arr = np.array(rgb)
            if sum(bar_crops(rgb, arr, b) is not None for b in bars) >= 3 or len(bars) >= 10:
                return "results"
    except Exception:
        pass
    return "box"


def _item(job, filename, path, kind, page=0, pages=1):
    it = {"id": len(job["items"]), "filename": filename + (f" (page {page + 1}/{pages})" if pages > 1 else ""),
          "path": str(path), "page": page, "kind": kind, "status": "queued", "message": "", "result": None,
          "problems": [], "warnings": []}
    job["items"].append(it)
    _q.put((job["id"], it))
    return it


def _store_and_queue(job, filename, data: bytes, kind_hint: str):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        job["skipped"].append(f"{filename}: unsupported type")
        return
    d = UPLOADS / job["id"]
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{len(job['items']) + len(job['skipped']):03d}_{_safe_name(filename)}"
    path.write_bytes(data)
    if ext == ".pdf":
        try:
            n = page_count(path)
        except Exception as e:
            job["skipped"].append(f"{filename}: not a readable PDF ({e})")
            return
        for pg in range(n):
            _item(job, filename, path, "box" if kind_hint in ("auto", "box") else kind_hint, pg, n)
    else:
        kind = _classify_image(path) if kind_hint == "auto" else kind_hint
        _item(job, filename, path, kind)


# ---------------------------------------------------------------- upload
@bp.post("/admin/api/upload")
def upload():
    files = request.files.getlist("files")
    if not files:
        abort(400, "no files")
    kind = request.form.get("kind", "auto")
    job = {"id": uuid.uuid4().hex[:10], "created": time.time(), "items": [], "skipped": [],
           "matchday": request.form.get("matchday", "").strip()}
    JOBS[job["id"]] = job
    auth.audit("upload", f"{len(files)} file(s)")
    for f in files:
        data = f.read()
        name = f.filename or "file"
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for info in z.infolist():
                        if info.is_dir() or info.file_size > MAX_ZIP_ENTRY or "__MACOSX" in info.filename:
                            continue
                        _store_and_queue(job, info.filename, z.read(info), kind)
            except zipfile.BadZipFile:
                job["skipped"].append(f"{name}: not a valid ZIP")
        else:
            _store_and_queue(job, name, data, kind)
    return jsonify(job_id=job["id"], items=len(job["items"]), skipped=job["skipped"])


# ---------------------------------------------------------------- worker
def _suggest(game):
    """Look the game up in the official results: suggested matchday, score check, duplicate check."""
    a, b = game["teams"]
    o = _official()
    pair = frozenset([a["code"], b["code"]])
    cands = [r for r in o["results"] if frozenset([r["home"], r["away"]]) == pair]
    box = {a["code"]: a["points"], b["code"]: b["points"]}
    out = {"matchday": None, "official": None, "unknown_codes": [c for c in box if c not in o["teams"]]}
    same = [r for r in cands if {r["home"]: r["home_score"], r["away"]: r["away_score"]} == box]
    r = same[0] if same else (cands[0] if len(cands) == 1 else None)
    if r:
        out["matchday"] = r["matchday"]
        out["official"] = f"{r['home']} {r['home_score']} – {r['away_score']} {r['away']} (J{r['matchday']})"
        out["score_matches"] = bool(same)
    key = (min(box), max(box), box[min(box)], box[max(box)])
    for g in stats.load_games():
        t1, t2 = sorted(g["teams"], key=lambda t: t["code"])
        if (t1["code"], t2["code"], t1.get("box_points", t1["points"]), t2.get("box_points", t2["points"])) == key:
            out["duplicate_of"] = g.get("source_file") or g["id"]
            break
    return out


def _process(job, it):
    it["status"] = "processing"
    try:
        path = Path(it["path"])
        if it["kind"] == "results":
            o = _official()
            res = parse_results_image(str(path), list(o["teams"]))
            if res["kind"] == "standings":
                it.update(kind="standings", status="done", warnings=res["warnings"], message="Standings image: nothing to import.")
                return
            if res["kind"] == "unknown":
                it.update(status="error", message=res["warnings"][0])
                return
            it.update(result=res, warnings=res["warnings"], status="done")
            md = res["matchday"]
            if md and any(r["matchday"] == md for r in o["results"]):
                old = {frozenset([r["home"], r["away"]]): (r["home_score"], r["away_score"]) for r in o["results"] if r["matchday"] == md}
                diff = [g for g in res["games"] if old.get(frozenset([g["home"], g["away"]]), None) not in (None, (g["home_score"], g["away_score"]))]
                it["message"] = f"Matchday {md} already saved ({len(old)} games)" + (f"; {len(diff)} score(s) differ." if diff else "; identical so far.")
            return
        hint = job.get("matchday")
        game, problems = extract(str(path), filename=Path(it["filename"]).name, matchday=f"J{hint}" if hint else "", page=it["page"])
        game["source_file"] = Path(it["filename"]).name
        sug = _suggest(game)
        it.update(result=game, problems=problems, suggest=sug, status="done")
    except Exception as e:  # a bad file must not stop the queue
        it.update(status="error", message=f"{type(e).__name__}: {e}")


def _worker():
    while True:
        job_id, it = _q.get()
        job = JOBS.get(job_id)
        if job:
            _process(job, it)
        _q.task_done()


threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------- job views
def _public(it):
    return {k: v for k, v in it.items() if k != "path"}


@bp.get("/admin/api/jobs/<job_id>")
def job_view(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    items = [_public(i) for i in job["items"]]
    return jsonify(id=job_id, skipped=job["skipped"], items=items,
                   pending=sum(i["status"] in ("queued", "processing") for i in items))


@bp.get("/admin/api/jobs")
def jobs_list():
    return jsonify(jobs=[{"id": j["id"], "created": j["created"], "items": len(j["items"]),
                          "pending": sum(i["status"] in ("queued", "processing") for i in j["items"])}
                         for j in sorted(JOBS.values(), key=lambda j: -j["created"])][:20])


@bp.get("/admin/api/review")
def review_list():
    """Games the Drive sync could not verify (they failed a consistency check)."""
    items = []
    for i, f in enumerate(sorted(REVIEW.glob("*.json"))) if REVIEW.exists() else []:
        g = json.loads(f.read_text())
        problems = g.pop("problems", [])
        items.append({"id": f.stem, "filename": g.get("source_file", f.stem), "kind": "box", "status": "done",
                      "result": g, "problems": problems, "warnings": [], "message": "From Drive sync",
                      "suggest": _suggest(g)})
    return jsonify(items=items)


@bp.get("/admin/api/traffic")
def traffic_view():
    return jsonify(traffic.summary(request.args.get("days", 30)))


@bp.get("/admin/api/mvp")
def mvp_admin():
    out = []
    for ph in mvp.PHASES:
        r = mvp.race(ph)
        out.append({"phase": ph, "complete": r["complete"], **mvp.settings(ph), "votes": mvp.admin_votes(ph),
                    "candidates": [{k: c[k] for k in ("id", "name", "team", "number", "votes", "score", "impact")} for c in r["candidates"]]})
    return jsonify(phases=out)


@bp.post("/admin/api/mvp")
def mvp_admin_save():
    b = request.get_json(silent=True) or {}
    ph = int(b.get("phase") or 0)
    if ph not in mvp.PHASES:
        return jsonify(error="Unknown phase."), 400
    winner = b.get("winner") or None
    if winner and winner not in {c["id"] for c in mvp.candidates(ph)}:
        return jsonify(error="That player is not a candidate of this phase."), 400
    mvp.save_settings(ph, winner, bool(b.get("voting_open")), str(b.get("note") or ""))
    auth.audit("mvp", f"phase {ph} winner={winner} open={bool(b.get('voting_open'))}")
    return jsonify(ok=True)


@bp.get("/admin/api/positions")
def positions_view():
    """Every player with the position the model infers and any manual correction."""
    d = stats.build()
    manual = stats.load_positions()
    rows = [{"id": p["id"], "name": p["name"], "team": p["team"], "number": p["number"], "gp": p["gp"],
             "total_min": p["total_min"], "auto": p["auto_pos"], "pos": p["pos"], "manual": manual.get(p["id"])}
            for p in d["players"]]
    rows.sort(key=lambda r: (r["team"], -r["total_min"]))
    return jsonify(positions=stats.POSITIONS, players=rows)


@bp.post("/admin/api/positions")
def positions_save():
    """Body {"changes": {"<player id>": "PG" | null}}: null removes a correction (back to automatic)."""
    changes = (request.get_json(silent=True) or {}).get("changes")
    if not isinstance(changes, dict):
        return jsonify(error="Send {\"changes\": {player id: position or null}}."), 422
    known = {p["id"] for p in stats.build()["players"]}
    with _file_lock:
        cur = stats.load_positions()
        for pid_, pos in changes.items():
            if pid_ not in known:
                return jsonify(error=f"unknown player {pid_}"), 422
            if pos is None:
                cur.pop(pid_, None)
            elif pos in stats.POSITIONS:
                cur[pid_] = pos
            else:
                return jsonify(error=f"bad position {pos!r}"), 422
        tmp = stats.POSITIONS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, indent=1, ensure_ascii=False))
        tmp.replace(stats.POSITIONS_FILE)
    auth.audit("positions", f"{len(changes)} change(s)")
    return jsonify(ok=True, manual=len(cur))


@bp.get("/admin/api/official")
def official_view():
    o = _official()
    per = {}
    for r in o["results"]:
        per.setdefault(r["matchday"], []).append(r)
    return jsonify(teams=o["teams"], matchdays={str(k): len(v) for k, v in sorted(per.items())},
                   games=len(o["results"]))


# ---------------------------------------------------------------- save / discard
def _add_result(o, md, home, away, hs, as_):
    """Insert/replace one official result (same matchday + same pair = replace)."""
    for r in o["results"]:
        if r["matchday"] == md and {r["home"], r["away"]} == {home, away}:
            r.update(home=home, away=away, home_score=hs, away_score=as_)
            return "updated"
    o["results"].append({"matchday": md, "home": home, "away": away, "home_score": hs, "away_score": as_})
    o["results"].sort(key=lambda r: r["matchday"])
    return "added"


def _check_results(games, o, md):
    seen, errs = [], []
    for g in games:
        for k in ("home", "away"):
            if g.get(k) not in o["teams"]:
                errs.append(f"unknown team {g.get(k)!r}")
            seen.append(g.get(k))
        for k in ("home_score", "away_score"):
            if not isinstance(g.get(k), int) or not 0 <= g[k] <= 250:
                errs.append(f"bad score for {g.get('home')}-{g.get('away')}")
        if g.get("home") == g.get("away"):
            errs.append(f"{g.get('home')} plays itself")
    dup = {c for c in seen if seen.count(c) > 1}
    if dup:
        errs.append(f"team(s) appear twice in matchday {md}: {', '.join(sorted(dup))}")
    return sorted(set(errs))


@bp.post("/admin/api/jobs/<job_id>/items/<int:idx>/save")
def save_item(job_id, idx):
    body = request.get_json(force=True)
    job = JOBS.get(job_id)
    it = job["items"][idx] if job and idx < len(job["items"]) else None
    if not it or it["status"] != "done" or it["result"] is None:
        abort(400, "item is not ready")
    return _save(it, body)


@bp.post("/admin/api/review/<stem>/save")
def save_review(stem):
    f = REVIEW / f"{_safe_name(stem)}.json"
    if not f.exists():
        abort(404)
    g = json.loads(f.read_text())
    g.pop("problems", None)
    resp, status = _save({"kind": "box", "result": g, "filename": g.get("source_file", stem), "status": "done"},
                         request.get_json(force=True))
    if status == 200:
        f.unlink()
    return resp, status


@bp.post("/admin/api/review/<stem>/discard")
def discard_review(stem):
    f = REVIEW / f"{_safe_name(stem)}.json"
    if f.exists():
        (ROOT / "review_discarded").mkdir(exist_ok=True)
        f.rename(ROOT / "review_discarded" / f.name)
    return jsonify(ok=True)


@bp.post("/admin/api/jobs/<job_id>/items/<int:idx>/discard")
def discard_item(job_id, idx):
    job = JOBS.get(job_id)
    if job and idx < len(job["items"]):
        job["items"][idx]["status"] = "discarded"
    return jsonify(ok=True)


def _save(it, body):
    with _file_lock:
        o = _official()
        # ---------- results graphic -> official.json
        if it["kind"] == "results":
            md = body.get("matchday")
            games = body.get("games") or it["result"]["games"]
            if not isinstance(md, int) or not 1 <= md <= 60:
                return jsonify(error="Enter the matchday number (1-60)."), 422
            errs = _check_results(games, o, md)
            if errs:
                return jsonify(error="; ".join(errs)), 422
            added = sum(_add_result(o, md, g["home"], g["away"], g["home_score"], g["away_score"]) == "added" for g in games)
            _write_official(o)
            auth.audit("save-results", f"matchday {md}")
            it["status"] = "saved"
            return jsonify(ok=True, message=f"Matchday {md}: {added} added, {len(games) - added} updated in official results."), 200
        # ---------- box score -> data/games
        game = body.get("game") or it["result"]
        problems = validate(game)
        if problems and not body.get("force"):
            return jsonify(error="Consistency checks failed.", problems=problems), 422
        md = body.get("matchday")
        if md is not None and not isinstance(md, int):
            return jsonify(error="Matchday must be a number."), 422
        if body.get("date"):
            game["date"] = body["date"]
            game["date_approx"] = False
        if md:
            game["matchday_no"], game["matchday"] = md, f"J{md}"
        digest = hashlib.sha1(json.dumps(game, sort_keys=True).encode()).hexdigest()[:16]
        game["id"] = game.get("id") or f"up-{digest}"
        if problems:
            game["forced_with_problems"] = problems
        game["uploaded"] = True
        GAMES.mkdir(parents=True, exist_ok=True)
        (GAMES / f"{game['id']}.json").write_text(json.dumps(game, indent=1, ensure_ascii=False))
        msg = f"Saved game {game['teams'][0]['code']} {game['teams'][0]['points']} – {game['teams'][1]['points']} {game['teams'][1]['code']}."
        a, b = game["teams"]
        if md and body.get("add_result") and a["code"] in o["teams"] and b["code"] in o["teams"]:
            how = _add_result(o, md, a["code"], b["code"], a["points"], b["points"])
            _write_official(o)
            msg += f" Official result for J{md} {how}."
        auth.audit("save-game", game["id"])
        it["status"] = "saved"
        return jsonify(ok=True, message=msg), 200
