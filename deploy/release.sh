#!/usr/bin/env bash
# Runs ON THE SERVER as the 'deploy' user, started by the GitHub pipeline after it copied the code to
# /opt/proastats/releases/<name>/ :      bash /opt/proastats/releases/<name>/deploy/release.sh <name>
#   release.sh <name>        install, test, switch, restart, health-check; roll back automatically if anything fails
#   release.sh --rollback    switch back, by hand, to the release that was live before the current one
# Live data (/opt/proastats/shared/data) is never touched by a deploy.
# $APP_ROOT/history lists every release that went live and stayed healthy (newest last): rollbacks only go to those.
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/proastats}"
RESTART_CMD="${RESTART_CMD:-sudo -n /usr/bin/systemctl restart proastats}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:5055/api/overview}"
KEEP="${KEEP:-5}"
HISTORY="$APP_ROOT/history"
cd "$APP_ROOT"
touch "$HISTORY"

restart_and_check() {
  $RESTART_CMD
  for _ in $(seq 1 30); do
    if curl -fsS -m 3 "$HEALTH_URL" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}

current_name() { basename "$(readlink -f current 2>/dev/null || echo none)"; }

previous_good() {  # newest entry of the history that is not the current release and still exists on disk
  local cur name; cur="$(current_name)"
  while read -r name; do
    if [ "$name" != "$cur" ] && [ -d "$APP_ROOT/releases/$name" ]; then echo "$name"; fi
  done < <(tac "$HISTORY" 2>/dev/null || tail -r "$HISTORY") | head -1
}

switch_to() {  # atomic on Linux (mv -T); the fallback only matters when rehearsing on a Mac
  ln -sfn "$APP_ROOT/releases/$1" current.tmp
  if ! mv -Tf current.tmp current 2>/dev/null; then rm -f current; mv current.tmp current; fi
}

if [ "${1:-}" = "--rollback" ]; then
  prev="$(previous_good)"
  [ -n "$prev" ] || { echo "No earlier healthy release to go back to."; exit 1; }
  echo "Rolling back to $prev"
  switch_to "$prev"
  if restart_and_check; then echo "Rolled back OK."; else echo "Health check failed after rollback!"; exit 1; fi
  exit 0
fi

NAME="${1:?usage: release.sh <release-name> | --rollback}"
REL="$APP_ROOT/releases/$NAME"
[ -d "$REL" ] || { echo "Release folder $REL not found."; exit 1; }
OLD="$(current_name)"

echo "==> Installing dependencies"
"$APP_ROOT/venv/bin/pip" install --quiet --disable-pip-version-check -r "$REL/requirements.txt"

echo "==> Smoke test on a throwaway data folder (the live data is not touched)"
TMPDATA="$(mktemp -d)"
trap 'rm -rf "$TMPDATA"' EXIT
( cd "$REL" && DATA_DIR="$TMPDATA" "$APP_ROOT/venv/bin/python" tests/smoke.py )

echo "==> Switching to $NAME"
switch_to "$NAME"
if restart_and_check; then
  echo "$NAME" >> "$HISTORY"
  echo "==> Healthy. Release $NAME is live."
else
  echo "!! Health check FAILED"
  if [ "$OLD" != none ] && [ -d "$APP_ROOT/releases/$OLD" ]; then
    echo "!! Rolling back to $OLD"
    switch_to "$OLD"
    if restart_and_check; then echo "Rolled back; the previous version is serving again."; else echo "!! Rollback also failed: check 'journalctl -u proastats'."; fi
  fi
  exit 1
fi

echo "==> Cleaning up: keeping the current release and the last $KEEP healthy ones"
keep=" $NAME $(tail -n "$KEEP" "$HISTORY" | tr '\n' ' ')"
for dir in "$APP_ROOT"/releases/*/; do
  n="$(basename "$dir")"
  case "$keep" in *" $n "*) ;; *) rm -rf "$dir" ;; esac
done
