"""Admin authentication. Only the admin can upload files, save data or trigger a sync.

Layers:
  1. One secret admin token. Only a salted scrypt hash is stored on disk (data/admin_token.json, mode 600),
     so reading the file does not reveal the token. Create/rotate it with:  python manage.py new-token
     (ADMIN_TOKEN in the environment overrides the file, for hosting platforms.)
  2. Token is exchanged once for a login session: random id in an HttpOnly + SameSite=Strict cookie
     (Secure on HTTPS), expires after SESSION_HOURS. JavaScript on the page can never read it.
  3. Brute-force lockout: MAX_FAILS wrong tokens from one address within WINDOW seconds -> 429.
  4. CSRF guard: state-changing requests must come from this site (Origin/Referer host check).
  5. Constant-time token comparison, security headers, and an audit log (data/admin.log).
No token configured = admin is locked for everybody.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from urllib.parse import urlparse

from flask import abort, jsonify, request

import config

DATA = config.DATA_DIR
TOKEN_FILE = DATA / "admin_token.json"
LOG_FILE = DATA / "admin.log"
COOKIE = "proa_admin"
# Behind Cloudflare every request arrives from a Cloudflare address. With TRUST_CLOUDFLARE=1 the real visitor
# address comes from the CF-Connecting-IP header. Only enable it when the server accepts web traffic from
# Cloudflare alone (deploy/firewall-cloudflare.sh); otherwise anyone could forge the header.
TRUST_CLOUDFLARE = os.environ.get("TRUST_CLOUDFLARE") == "1"
SESSION_HOURS = 8
MAX_FAILS = 5
WINDOW = 600  # seconds

_sessions: dict[str, float] = {}
_fails: dict[str, list[float]] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------- token storage
def _hash(token: str, salt: bytes) -> str:
    return hashlib.scrypt(token.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def new_token() -> str:
    """Readable but strong: 16 symbols from an unambiguous alphabet (~80 bits), e.g. K7QD-M2XR-9TWB-HC4N."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(16))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def set_token(token: str):
    DATA.mkdir(exist_ok=True)
    salt = secrets.token_bytes(16)
    TOKEN_FILE.write_text(json.dumps({"salt": salt.hex(), "hash": _hash(token, salt), "created": time.strftime("%Y-%m-%d %H:%M:%S")}))
    os.chmod(TOKEN_FILE, 0o600)
    with _lock:
        _sessions.clear()  # rotating the token logs everybody out


def token_configured() -> bool:
    return bool(os.environ.get("ADMIN_TOKEN")) or TOKEN_FILE.exists()


def _verify(token: str) -> bool:
    token = (token or "").strip()
    env = os.environ.get("ADMIN_TOKEN")
    if env:
        return hmac.compare_digest(token.encode(), env.encode())
    if not TOKEN_FILE.exists():
        return False
    d = json.loads(TOKEN_FILE.read_text())
    return hmac.compare_digest(_hash(token.upper(), bytes.fromhex(d["salt"])), d["hash"])  # generated tokens are upper-case


def client_ip() -> str:
    if TRUST_CLOUDFLARE:
        ip = (request.headers.get("CF-Connecting-IP") or "").strip()
        if ip:
            return ip
    return request.remote_addr or "?"


def visitor_ip() -> str:
    """The visitor's address for statistics and the vote's per-network cap (never for security decisions: use client_ip()).
    Behind Caddy every request comes from 127.0.0.1, and behind Cloudflare the real address is in CF-Connecting-IP; a forged
    header here can only skew our own counts, so it is accepted even when TRUST_CLOUDFLARE is off."""
    ip = (request.headers.get("CF-Connecting-IP") or "").strip()
    if not ip and request.remote_addr in ("127.0.0.1", "::1"):
        ip = (request.headers.get("X-Forwarded-For") or "").split(",")[-1].strip()
    return ip or request.remote_addr or "?"


# ---------------------------------------------------------------- audit log
def audit(action: str, detail: str = ""):
    try:
        DATA.mkdir(exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{client_ip()}\t{action}\t{detail}\n")
        os.chmod(LOG_FILE, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------- sessions & lockout
def _locked_out(ip: str) -> int:
    """Seconds left of lockout (0 = fine)."""
    now = time.time()
    with _lock:
        recent = [t for t in _fails.get(ip, []) if now - t < WINDOW]
        _fails[ip] = recent
        return int(WINDOW - (now - recent[0])) if len(recent) >= MAX_FAILS else 0


def login(token: str):
    """Returns (response, status). Sets the session cookie on success."""
    ip = client_ip()
    wait = _locked_out(ip)
    if wait:
        audit("login-blocked", f"locked for {wait}s")
        r = jsonify(error=f"Too many wrong attempts. Try again in {wait // 60 + 1} minute(s)."), 429
        return r[0], 429
    if not token_configured():
        return jsonify(error="No admin token is set. Run: python manage.py new-token"), 503
    if not _verify(token):
        with _lock:
            _fails.setdefault(ip, []).append(time.time())
        time.sleep(0.6)  # slows guessing even before the lockout
        audit("login-failed")
        return jsonify(error="Wrong token."), 401
    sid = secrets.token_urlsafe(32)
    with _lock:
        _fails.pop(ip, None)
        now = time.time()
        for k in [k for k, exp in _sessions.items() if exp < now]:
            del _sessions[k]
        _sessions[sid] = now + SESSION_HOURS * 3600
    audit("login-ok")
    resp = jsonify(ok=True)
    resp.set_cookie(COOKIE, sid, max_age=SESSION_HOURS * 3600, httponly=True, samesite="Strict",
                    secure=request.is_secure, path="/")
    return resp, 200


def logout():
    sid = request.cookies.get(COOKIE)
    with _lock:
        _sessions.pop(sid, None)
    audit("logout")
    resp = jsonify(ok=True)
    resp.delete_cookie(COOKIE, path="/")
    return resp


def is_admin() -> bool:
    sid = request.cookies.get(COOKIE)
    if sid:
        with _lock:
            exp = _sessions.get(sid)
            if exp and exp > time.time():
                return True
            _sessions.pop(sid, None)
    # scripts (curl, cron) may send the token directly; it is checked like a login, with the same lockout
    hdr = request.headers.get("X-Admin-Token")
    if hdr:
        ip = client_ip()
        if _locked_out(ip):
            return False
        if _verify(hdr):
            return True
        with _lock:
            _fails.setdefault(ip, []).append(time.time())
        audit("header-token-failed")
    return False


def same_origin_ok() -> bool:
    """CSRF guard for POSTs: the browser's Origin/Referer must be this site (non-browser clients send neither)."""
    src = request.headers.get("Origin") or request.headers.get("Referer")
    if not src:
        return True  # curl/scripts; they must still pass is_admin()
    return urlparse(src).netloc == request.host


def require_admin():
    """Call at the start of any protected request. Aborts with 401/403 otherwise."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and not same_origin_ok():
        audit("csrf-blocked", request.path)
        abort(403, "Cross-site request refused.")
    if not is_admin():
        abort(401, "Admin login required.")


def add_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if request.path.startswith(("/admin", "/analytics", "/api/sync")):
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp
