#!/usr/bin/env bash
# Backup of everything that matters (votes, visit statistics, games, official results, roster, admin settings).
#   backup.sh          full backup (nightly, from cron): consistent SQLite copies, verified, 14 days + one per month for a year
#   backup.sh --small  votes + visits only (hourly, from cron): kept 3 days
# Run as root by cron. A backup on the same machine does not survive losing the machine: also copy them off
# (DEPLOY.md, "Backups") or switch on OVH's backup option.
set -euo pipefail
export DATA_DIR="${DATA_DIR:-/opt/proastats/shared/data}"
export BACKUP_DIR="${BACKUP_DIR:-/var/backups/proastats}"
APP="${APP:-/opt/proastats/current}"
exec /opt/proastats/venv/bin/python "$APP/tools/backup_data.py" "$@"
