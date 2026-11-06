#!/usr/bin/env bash
# ONE-TIME server preparation. Run ON THE SERVER as root (OVH: log in as the default user, then `sudo -i`):
#
#   DOMAIN=tunisiabasket.com DEPLOY_PUBKEY="ssh-ed25519 AAAA... github-deploy" bash setup.sh
#
# Optional: DRIVE_FOLDER_ID=...  ALT_DOMAIN=basket.tn (redirects to DOMAIN)  SYNC_INTERVAL_MIN=10  HARDEN_SSH=0
# Prepares: packages (Python, Tesseract, Caddy with automatic HTTPS), the two users, the folder layout, the service,
# firewall, brute-force protection, automatic security updates, nightly backups.
# It does NOT install the app: the GitHub pipeline does that on every approved deploy (see deploy/DEPLOY.md).
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Run as root (sudo -i)."; exit 1; }
: "${DOMAIN:?Set DOMAIN, e.g.  DOMAIN=tunisiabasket.com}"
: "${DEPLOY_PUBKEY:?Set DEPLOY_PUBKEY to the PUBLIC key line of the GitHub deploy key (ssh-ed25519 AAAA...)}"
case "$DEPLOY_PUBKEY" in ssh-*|ecdsa-*) ;; *) echo "DEPLOY_PUBKEY must be a public key line starting with ssh-ed25519 ..."; exit 1;; esac
ALT_DOMAIN="${ALT_DOMAIN:-}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-}"   # the part of your Google Drive link after /folders/ (empty = automatic sync off)
SYNC_INTERVAL_MIN="${SYNC_INTERVAL_MIN:-10}"
HARDEN_SSH="${HARDEN_SSH:-1}"
APP=/opt/proastats

echo "==> 1/9 Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip tesseract-ocr ufw fail2ban unattended-upgrades \
  rsync curl gpg debian-keyring debian-archive-keyring apt-transport-https
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

echo "==> 2/9 Users: 'deploy' (the pipeline logs in as this) and 'proa' (runs the app, owns the data)"
id deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/bash deploy
id proa >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin proa
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
echo "$DEPLOY_PUBKEY" > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
# deploy may restart ONLY this one service, nothing else
echo 'deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart proastats, /usr/bin/systemctl is-active proastats' > /etc/sudoers.d/proastats-deploy
chmod 440 /etc/sudoers.d/proastats-deploy
visudo -cf /etc/sudoers.d/proastats-deploy

echo "==> 3/9 Folders"
install -d -m 755 -o deploy -g deploy "$APP" "$APP/releases"
install -d -m 750 -o proa -g proa "$APP/shared" "$APP/shared/data"
install -d -m 700 /var/backups/proastats
runuser -u deploy -- python3 -m venv "$APP/venv"

echo "==> 4/9 Settings (/etc/proastats.env)"
if [ ! -f /etc/proastats.env ]; then
  cat > /etc/proastats.env <<ENV
APP_ENV=production
BEHIND_PROXY=1
TRUST_CLOUDFLARE=0
BIND=127.0.0.1:5055
DATA_DIR=$APP/shared/data
SYNC_INTERVAL_MIN=$SYNC_INTERVAL_MIN
DRIVE_FOLDER_ID=$DRIVE_FOLDER_ID
AUTO_SYNC=$([ -n "$DRIVE_FOLDER_ID" ] && echo 1 || echo 0)
PYTHONDONTWRITEBYTECODE=1
ENV
  chown root:proa /etc/proastats.env
  chmod 640 /etc/proastats.env
fi

echo "==> 5/9 Service (starts after the first deploy)"
cat > /etc/systemd/system/proastats.service <<'UNIT'
[Unit]
Description=Pro A Stats (gunicorn)
After=network-online.target
Wants=network-online.target

[Service]
User=proa
Group=proa
WorkingDirectory=/opt/proastats/current
EnvironmentFile=/etc/proastats.env
ExecStart=/opt/proastats/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=3
# Hardening: the app can only write inside its data folder
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
ReadWritePaths=/opt/proastats/shared/data

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable proastats

echo "==> 6/9 Web server (Caddy: HTTPS certificates are automatic)"
{
  echo "$DOMAIN {"
  cat <<'CADDY'
	encode zstd gzip
	request_body {
		max_size 300MB
	}
	header {
		Strict-Transport-Security "max-age=31536000"
		-Server
	}
	reverse_proxy 127.0.0.1:5055
}
CADDY
  echo "www.$DOMAIN {"
  echo "	redir https://$DOMAIN{uri} permanent"
  echo "}"
  if [ -n "$ALT_DOMAIN" ]; then
    echo "$ALT_DOMAIN, www.$ALT_DOMAIN {"
    echo "	redir https://$DOMAIN{uri} permanent"
    echo "}"
  fi
} > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "==> 7/9 Firewall, brute-force protection, automatic updates, backups"
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp   # SSH, rate-limited
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades || true
echo "17 3 * * * root $APP/current/deploy/backup.sh >> /var/backups/proastats/backup.log 2>&1" > /etc/cron.d/proastats-backup

echo "==> 8/9 Admin helper (proastats-admin new-token | log | status)"
cat > /usr/local/bin/proastats-admin <<'WRAP'
#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo."; exit 1; }
cd /opt/proastats/current
exec runuser -u proa -- env DATA_DIR=/opt/proastats/shared/data /opt/proastats/venv/bin/python manage.py "$@"
WRAP
chmod 755 /usr/local/bin/proastats-admin

echo "==> 9/9 SSH hardening"
KEYS_OK=0
for f in /root/.ssh/authorized_keys "/home/${SUDO_USER:-nobody}/.ssh/authorized_keys"; do
  [ -s "$f" ] && KEYS_OK=1
done
if [ "$HARDEN_SSH" = 1 ] && [ "$KEYS_OK" = 1 ]; then
  printf 'PasswordAuthentication no\nPermitRootLogin prohibit-password\n' > /etc/ssh/sshd_config.d/10-proastats.conf
  if sshd -t; then systemctl reload ssh || systemctl reload sshd; echo "password logins disabled (keys only)"; else rm -f /etc/ssh/sshd_config.d/10-proastats.conf; fi
else
  echo "SKIPPED: you log in with a password, so I did not disable it (that could lock you out). Add your SSH key, then re-run with HARDEN_SSH=1."
fi

echo
echo "SERVER READY. Next (deploy/DEPLOY.md, step 6): add the GitHub secrets and run the first deploy from GitHub."
echo "After the first deploy: sudo proastats-admin new-token     (creates your admin token)"
