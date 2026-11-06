#!/usr/bin/env bash
# Run on YOUR computer (not the server). Copies setup.sh to the server and runs it there, with the right quoting.
#     bash deploy/provision.sh SERVER_IP DOMAIN [SSH_USER]
#     bash deploy/provision.sh 203.0.113.10 tunisiabasket.com
# Needs: you can already `ssh SSH_USER@SERVER_IP` (default user: ubuntu). It makes the pipeline's deploy key if you have none.
set -euo pipefail
IP="${1:?usage: provision.sh SERVER_IP DOMAIN [SSH_USER]}"
DOMAIN="${2:?usage: provision.sh SERVER_IP DOMAIN [SSH_USER]}"
SSH_USER="${3:-ubuntu}"
KEY="$HOME/.ssh/proastats_deploy"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$KEY.pub" ]; then
  echo "Creating the pipeline's deploy key $KEY (no passphrase: GitHub uses it unattended)"
  ssh-keygen -t ed25519 -f "$KEY" -C github-deploy -N "" -q
fi
DEPLOY_PUBKEY="$(cat "$KEY.pub")"

# Your own key: the first time you are asked for the server password ONCE; after that no more passwords.
MYKEY=""
for f in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_rsa.pub"; do
  if [ -z "$MYKEY" ] && [ -f "$f" ]; then MYKEY="$f"; fi
done
if [ -n "$MYKEY" ] && ! ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$SSH_USER@$IP" true 2>/dev/null; then
  echo "==> Installing your SSH key ($MYKEY) on the server. Type the server password when asked."
  ssh-copy-id -o StrictHostKeyChecking=accept-new -i "$MYKEY" "$SSH_USER@$IP"
fi
read -r -p "Google Drive folder ID (the part after /folders/ in your Drive link; Enter to skip, sync stays off): " DRIVE_FOLDER_ID

echo "==> Copying setup.sh to $SSH_USER@$IP"
scp -o StrictHostKeyChecking=accept-new "$HERE/setup.sh" "$SSH_USER@$IP:/tmp/proastats-setup.sh"
echo "==> Running it (it will take a few minutes; sudo may ask for the password)"
ssh -t "$SSH_USER@$IP" "sudo env DOMAIN=$(printf '%q' "$DOMAIN") DRIVE_FOLDER_ID=$(printf '%q' "$DRIVE_FOLDER_ID") DEPLOY_PUBKEY=$(printf '%q' "$DEPLOY_PUBKEY") bash /tmp/proastats-setup.sh"
echo
echo "Server prepared. Next: bash deploy/configure-github.sh khelilo7/tunisiabasket $IP $DOMAIN"
