#!/usr/bin/env bash
# Rehearses deploy/release.sh in a fake server layout in /tmp (no root, no systemd):
#   good release -> switches | broken-before-switch -> refused | crashes-on-start -> automatic rollback | manual rollback
# Usage (from the repo root, with python3 = the interpreter that has the requirements):  bash tests/test_release.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(mktemp -d)"; PORT=5077
export APP_ROOT="$ROOT" HEALTH_URL="http://127.0.0.1:$PORT/api/overview" KEEP=3
mkdir -p "$ROOT/releases" "$ROOT/shared/data" "$ROOT/run"
ln -s "$(python3 -c 'import sys; print(sys.prefix)')" "$ROOT/venv"
cat > "$ROOT/restart.sh" <<RS
#!/usr/bin/env bash
# stand-in for "systemctl restart proastats": stop the old server, start gunicorn from the 'current' release
if [ -f "$ROOT/run/pid" ]; then kill "\$(cat "$ROOT/run/pid")" 2>/dev/null || true; fi
sleep 1
cd "$ROOT/current"
APP_ENV=production AUTO_SYNC=0 BEHIND_PROXY=1 DATA_DIR="$ROOT/shared/data" BIND=127.0.0.1:$PORT \
  nohup "$ROOT/venv/bin/gunicorn" -c gunicorn.conf.py app:app > "$ROOT/run/log" 2>&1 &
echo \$! > "$ROOT/run/pid"
RS
chmod +x "$ROOT/restart.sh"; export RESTART_CMD="$ROOT/restart.sh"
cleanup() {
  if [ -f "$ROOT/run/pid" ]; then kill "$(cat "$ROOT/run/pid")" 2>/dev/null || true; fi
  rm -rf "$ROOT"
}
trap cleanup EXIT

new_release() {  # name [broken-kind]
  mkdir -p "$ROOT/releases/$1"
  rsync -a --exclude .venv --exclude .git --exclude data --exclude __pycache__ "$REPO"/ "$ROOT/releases/$1/"
  case "${2:-}" in
    nosmoke) echo "raise RuntimeError('broken release')" >> "$ROOT/releases/$1/app.py" ;;
    crashprod) printf '\nimport os\nif os.environ.get("APP_ENV") == "production":\n    raise RuntimeError("crashes only in production")\n' >> "$ROOT/releases/$1/app.py" ;;
  esac
  sleep 1  # distinct modification times: releases are ordered by age
}
serving() { curl -fsS -m 3 "$HEALTH_URL" >/dev/null 2>&1; }
current() { basename "$(readlink -f "$ROOT/current")"; }
fail=0
ok() { echo "  PASS $1"; }
bad() { echo "  FAIL $1"; fail=1; }

# check <description> <command...>: PASS when the command succeeds
check() { local d="$1"; shift; if "$@"; then echo "  PASS $d"; else echo "  FAIL $d"; fail=1; fi; }
# refuse <description> <command...>: PASS when the command FAILS
refuse() { local d="$1"; shift; if "$@"; then echo "  FAIL $d"; fail=1; else echo "  PASS $d"; fi; }
release() { bash "$ROOT/releases/$1/deploy/release.sh" "$1" >/dev/null 2>&1; }
live_and_serving() { [ "$(current)" = "$1" ] && serving; }
release_then_live() { release "$1" && live_and_serving "$1"; }

echo "1) good release r1";  new_release r1
check "r1 live and serving" release_then_live r1
echo "2) release r2 fails the smoke test BEFORE switching"; new_release r2 nosmoke
refuse "r2 is refused" release r2
check "r1 still live and serving" live_and_serving r1
echo "3) release r3 passes the smoke test but crashes in production -> automatic rollback"; new_release r3 crashprod
refuse "r3 reported as failed" release r3
check "rolled back: r1 live and serving again" live_and_serving r1
echo "4) good release r4, then manual rollback"; new_release r4
check "r4 live and serving" release_then_live r4
check "manual rollback succeeds" bash "$ROOT/releases/r4/deploy/release.sh" --rollback
check "after rollback: r1 is live and serving" live_and_serving r1
echo "5) failed releases and old ones are cleaned up (KEEP=$KEEP)"
check "failed releases r2/r3 removed" test ! -d "$ROOT/releases/r2" -a ! -d "$ROOT/releases/r3"
check "rollback target r1 and current r1/r4 kept" test -d "$ROOT/releases/r1" -a -d "$ROOT/releases/r4"
check "history lists only healthy releases" test "$(tr '\n' ' ' < "$ROOT/history")" = "r1 r4 "
echo "6) live data untouched by deploys"
check "shared/data still there" test -d "$ROOT/shared/data"
if [ "$fail" = 0 ]; then echo "release rehearsal: ok"; else echo "release rehearsal: FAILED"; exit 1; fi
