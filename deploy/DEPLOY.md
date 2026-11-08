# Deployment reference

## Setting up from scratch (new server, new project)
Names below: server `SERVER_IP`, domain `tunisiabasket.com`, GitHub repository `OWNER/REPO`.

1. **Server.** Order an OVHcloud VPS (Ubuntu 24.04, 2 vCPU / 4 GB is plenty; France is the closest region). If you cannot log in, reinstall it from the OVH
   Control Panel (VPS > Reinstall) or use rescue mode to reset the password. At the first login the server forces a password change: type the temporary
   password from OVH's email at both prompts, then your new one. Check with `ssh ubuntu@SERVER_IP`.
2. **Domain.** Buy it at Cloudflare (Domain Registration), then Cloudflare > DNS: two `A` records (`@` and `www`) to `SERVER_IP`, **DNS only (grey cloud)** until
   the server has its HTTPS certificate.
3. **GitHub.** Create the repository, add your own SSH key to GitHub (Settings > SSH keys), `git push -u origin main`.
4. **Prepare the server (once):** `bash deploy/provision.sh SERVER_IP tunisiabasket.com`. It makes the pipeline's deploy key, installs your SSH key, asks for the
   Google Drive folder ID (the part after `/folders/` in the Drive link) and runs `setup.sh` on the server.
5. **Wire up GitHub:** `brew install gh && gh auth login`, then `bash deploy/configure-github.sh OWNER/REPO SERVER_IP tunisiabasket.com`. It creates the
   `production` environment with you as required reviewer, stores the secrets and variables, and turns on secret scanning.
6. **First deploy:** GitHub > Actions > Deploy > Re-run all jobs, then Review deployments > Approve. Afterwards every push to `main` runs the tests and waits for your approval.
7. **Admin token:** `ssh ubuntu@SERVER_IP` then `sudo proastats-admin new-token` (shown once).
8. **Go live behind Cloudflare:** switch both DNS records to Proxied (orange cloud), SSL/TLS = Full (strict), Always Use HTTPS = on, then on the server
   `sudo bash /opt/proastats/current/deploy/firewall-cloudflare.sh` so only Cloudflare can reach the web ports.

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
| `/var/backups/proastats` | nightly full backup (7 days, then one per month for a year) + a votes/visits snapshot every 6 hours when something changed (2 days), all verified | root |

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
- **Restore a backup:** see "Backups" below.

## Backups (votes, visit statistics, games, roster, admin settings)
What is saved: the whole data folder `/opt/proastats/shared/data`, including `votes.db` (the fans' votes), `traffic.db` (visit statistics) and `traffic.key`. Deploys never touch it.
- **Nightly, 03:17:** full backup `data-YYYYmmdd-HHMMSS.tgz`; kept 7 days, then the oldest of each month for a year.
- **Every 6 hours (00:07, 06:07, 12:07, 18:07):** `small-YYYYmmdd-HHMM.tgz` with only votes, visits and settings; kept 2 days. It is skipped when no vote and no setting changed since the last one, so quiet days cost nothing. A vote is never more than 6 hours from a backup (and a visit never more than a day: the nightly full backup has them).
- SQLite files are copied with SQLite's own backup call (safe while votes arrive) and every backup is re-opened and checked (integrity, row counts). A backup that fails the check is deleted and logged as `BACKUP FAILED` in `/var/backups/proastats/backup.log`.
- **Servers that already have the hourly line** must replace it once with the 6-hourly one (the nightly one picks up the new script by itself after a deploy): `sudo sed -i 's|^7 \* \* \* \*|7 */6 * * *|' /etc/cron.d/proastats-backup`. A new server gets it from `setup.sh`. If the line is missing altogether:
  `echo '7 */6 * * * root /opt/proastats/current/deploy/backup.sh --small >> /var/backups/proastats/backup.log 2>&1' | sudo tee -a /etc/cron.d/proastats-backup`
- **Run one now:** `sudo /opt/proastats/current/deploy/backup.sh` (prints the vote and visit counts it saved).
- **Restore:** `sudo /opt/proastats/venv/bin/python /opt/proastats/current/tools/backup_data.py --data /opt/proastats/shared/data --restore /var/backups/proastats/data-XXXX.tgz`
  unpacks into a new folder next to `data` and never overwrites the live data. Then `sudo systemctl stop proastats`, move the restored `data` folder into place (keep the old one aside), `sudo chown -R proa:proa /opt/proastats/shared/data`, `sudo systemctl start proastats`.
- **Off the machine:** copy the folder to your own computer now and then, for example `rsync -av ubuntu@SERVER_IP:/var/backups/proastats/ ~/proastats-backups/` (run it with sudo rights on the server side or from a user that can read the folder), or switch on OVH's backup option. A backup that lives only on the server is lost with the server.
- **On your own computer:** `python manage.py backup` writes a verified backup into `./backups` (git-ignored); `python manage.py backup --small` for votes and visits only.

## If something goes wrong
| Symptom | Likely cause / fix |
|---|---|
| Deploy job fails at "Refuse to deploy…" | No required reviewer on the `production` environment (see step 5 above). Private repos need GitHub Pro |
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
