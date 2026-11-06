# Deployment reference

The step-by-step is in `TODO.md` at the top of the repository. This file explains how the pieces fit, for when something needs fixing.

## How a deploy works
```
git push main ─► GitHub: CI (lint, tests, release rehearsal) ─► YOU APPROVE (environment "production") ─►
rsync code to  /opt/proastats/releases/<time>-<sha>/  on the OVH server ─► deploy/release.sh <name>:
    pip install ─► smoke test on a throwaway data folder ─► switch /opt/proastats/current ─► restart ─► health check
                                                                                              └─ unhealthy? switch back automatically
```

## Server layout (made by `deploy/setup.sh`)
| Path | What | Owner |
|---|---|---|
| `/opt/proastats/releases/<name>/` | one folder per deploy (the code) | `deploy` |
| `/opt/proastats/current` | symlink to the live release | `deploy` |
| `/opt/proastats/venv` | Python packages | `deploy` |
| `/opt/proastats/shared/data` | **live data** (games, official results, admin hash, logs, uploads). Deploys never touch it | `proa` |
| `/opt/proastats/history` | releases that went live and stayed healthy (rollbacks only go to these) | `deploy` |
| `/etc/proastats.env` | settings (data folder, sync interval, Cloudflare trust) | root |
| `/var/backups/proastats` | nightly backups of the data folder, 14 days | root |

Two users on purpose: **`deploy`** (what the pipeline logs in as; can write code and may restart only this one service) and **`proa`** (runs the
app; can write only inside `shared/data`). Reading the code or the data never gives access to the other.

## Where the secrets are
| Secret | Where | Never |
|---|---|---|
| Deploy private key | GitHub → environment `production` → secret `PROD_SSH_KEY` (and your `~/.ssh/proastats_deploy`) | in the repo |
| Admin token | in your head/password manager; the server stores only a hash | in the repo, in chat |
| Server's SSH host key | secret `PROD_SSH_KNOWN_HOSTS` (the pipeline refuses unknown servers) | |

## Changing things
- **Settings** (`/etc/proastats.env`, then `sudo systemctl restart proastats`): `SYNC_INTERVAL_MIN`, `DRIVE_FOLDER_ID`, `TRUST_CLOUDFLARE`.
- **Official calendar** for J12–J22: upload it as `data/fixtures.json` (format in the README), no deploy needed.
- **Rotate the deploy key:** make a new one, replace the line in `/home/deploy/.ssh/authorized_keys` and the GitHub secret.
- **New server:** do to-do 1 again, update `PROD_HOST` and `PROD_SSH_KNOWN_HOSTS`, restore a data backup into `/opt/proastats/shared/data`.
- **Restore a backup:** `sudo systemctl stop proastats; sudo tar -xzf data-YYYYMMDD.tgz -C /opt/proastats/shared; sudo chown -R proa:proa /opt/proastats/shared/data; sudo systemctl start proastats`

## If something goes wrong
| Symptom | Likely cause / fix |
|---|---|
| Deploy job fails at "Refuse to deploy…" | No required reviewer on the `production` environment (see TODO step 4a). Private repos need GitHub Pro |
| Deploy job fails at "Prepare SSH"/rsync | Wrong `PROD_*` secret/variable, or the deploy public key is not in `/home/deploy/.ssh/authorized_keys` |
| `release.sh` says smoke test failed | The new code is broken; nothing was switched. Fix and push again |
| "Health check FAILED … rolling back" | The new release crashed on start; the old one is serving again. Read `journalctl -u proastats -n 100` |
| Browser shows a Cloudflare 521/522 | Caddy/app down (`systemctl status caddy proastats`), or the Cloudflare-only firewall was applied while the DNS cloud was still grey |
| Certificate error on first visit | DNS must point at the server (grey cloud) until Caddy has its certificate (`journalctl -u caddy -n 50`) |
| Admin says "too many attempts" | wait 10 minutes, or `sudo systemctl restart proastats` |
| Scanned PDFs fail | `tesseract --version` must work on the server |

## Security summary
Visitors are read-only; upload, save and sync need the admin session (token → HttpOnly cookie, lockout after 5 failures, audit log).
Only Cloudflare can reach the web ports (`firewall-cloudflare.sh`), SSH is rate-limited with fail2ban and, when you log in with a key, password
logins are off. The pipeline can only act after a human approves, uses a dedicated key that can restart one service, and keeps a rollback.
Keep your SSH key, the deploy key and the admin token private: whoever has one controls that part of the site.
