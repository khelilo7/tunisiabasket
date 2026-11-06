#!/usr/bin/env bash
# Nightly backup of everything that matters (games, official results, admin hash, logs). Keeps 14 days.
# Run as root by cron. A backup on the same machine does not survive losing the machine: also copy them off
# (DEPLOY.md, "Backups") or switch on OVH's backup option.
set -euo pipefail
DATA="${DATA_DIR:-/opt/proastats/shared/data}"
OUT="${BACKUP_DIR:-/var/backups/proastats}"
mkdir -p "$OUT"
tar -C "$(dirname "$DATA")" -czf "$OUT/data-$(date +%Y%m%d).tgz" "$(basename "$DATA")"
find "$OUT" -name 'data-*.tgz' -mtime +14 -delete
echo "$(date '+%F %T') backup ok"
