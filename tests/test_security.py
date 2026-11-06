"""Only the admin can upload, save or sync. Visitors are read-only."""
import os
import sys
from pathlib import Path

os.environ["ADMIN_TOKEN"] = "TEST-TOKEN-0000-1111"  # test token; never the real one
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
import auth  # noqa: E402

auth.time.sleep = lambda s: None
c = app.app.test_client()
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def ip(addr):
    return {"REMOTE_ADDR": addr}


for method, path in [("post", "/api/sync"), ("get", "/admin/api/official"), ("get", "/admin/api/review"),
                     ("post", "/admin/api/upload"), ("post", "/admin/api/jobs/x/items/0/save"),
                     ("post", "/admin/api/review/x/save"), ("get", "/admin/api/jobs")]:
    got = getattr(c, method)(path, environ_overrides=ip("198.51.100.1")).status_code
    check(got == 401, f"anonymous {method.upper()} {path} must be 401, got {got}")
for path in ["/", "/api/overview", "/api/players", "/api/games", "/api/planning", "/api/teams/CA"]:
    check(c.get(path).status_code == 200, f"public page {path} must work")
check("error" not in c.get("/api/status").get_data(as_text=True), "public status must not leak error details")

# wrong token, then lockout (per address)
codes = [c.post("/admin/api/login", json={"token": "bad%d" % i}, environ_overrides=ip("198.51.100.2")).status_code for i in range(6)]
check(codes == [401] * 5 + [429], f"lockout sequence {codes}")
check(c.post("/admin/api/login", json={"token": os.environ["ADMIN_TOKEN"]}, environ_overrides=ip("198.51.100.2")).status_code == 429,
      "right token must also be refused while locked out")

# real login from another address
r = c.post("/admin/api/login", json={"token": os.environ["ADMIN_TOKEN"]}, environ_overrides=ip("198.51.100.3"))
check(r.status_code == 200, "login with the right token")
cookie = r.headers.get("Set-Cookie", "")
check("HttpOnly" in cookie and "SameSite=Strict" in cookie, "session cookie must be HttpOnly + SameSite=Strict")
check(c.get("/admin/api/official", environ_overrides=ip("198.51.100.3")).status_code == 200, "admin sees admin data")
check(c.post("/api/sync", headers={"Origin": "http://evil.example"}, environ_overrides=ip("198.51.100.3")).status_code == 403,
      "cross-site POST must be refused even with a valid session")
c.post("/admin/api/logout", environ_overrides=ip("198.51.100.3"))
check(c.get("/admin/api/official", environ_overrides=ip("198.51.100.3")).status_code == 401, "logout must end the session")
c2 = app.app.test_client()
c2.set_cookie(auth.COOKIE, "forged", domain="localhost")
check(c2.get("/admin/api/official", environ_overrides=ip("198.51.100.4")).status_code == 401, "forged cookie must be refused")

print("security:", "FAILED" if fails else "ok")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
