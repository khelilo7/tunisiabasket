#!/usr/bin/env bash
# Run on the server AFTER the domain works through Cloudflare (orange cloud on):  bash deploy/firewall-cloudflare.sh
# Lets ONLY Cloudflare reach ports 80/443, so nobody can bypass Cloudflare, and then trusts the
# CF-Connecting-IP header (real visitor address -> the admin login lockout hits the attacker, not everyone).
# Re-run it every month or two (Cloudflare occasionally changes its address ranges): /etc/cron.monthly is set up below.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run as root."; exit 1; }
RANGES="$(curl -fsS https://www.cloudflare.com/ips-v4; echo; curl -fsS https://www.cloudflare.com/ips-v6)"
RANGES="$(echo "$RANGES" | grep -E '^[0-9a-fA-F:.]+/[0-9]+$' || true)"
N=$(echo "$RANGES" | grep -c . || true)
[ "$N" -ge 10 ] || { echo "Could not download Cloudflare's address list ($N entries). Nothing changed."; exit 1; }
for r in $RANGES; do ufw allow from "$r" to any port 80,443 proto tcp >/dev/null; done
ufw delete allow 80/tcp >/dev/null 2>&1 || true
ufw delete allow 443/tcp >/dev/null 2>&1 || true
sed -i 's/^TRUST_CLOUDFLARE=.*/TRUST_CLOUDFLARE=1/' /etc/proastats.env
systemctl restart proastats
ln -sf /opt/proastats/current/deploy/firewall-cloudflare.sh /etc/cron.monthly/proastats-cloudflare-ips
echo "OK: web ports now accept Cloudflare only ($N ranges). SSH is unchanged."
