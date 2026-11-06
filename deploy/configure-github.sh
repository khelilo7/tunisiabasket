#!/usr/bin/env bash
# Run on YOUR computer, after the server is prepared. Sets up everything the pipeline needs on GitHub in one go:
#   - environment "production" with YOU as required reviewer (the human approval) and only the main branch allowed
#   - secrets: deploy private key + the server's SSH host key; variables: host, user, domain
#   - secret scanning + push protection on the repository
#     bash deploy/configure-github.sh OWNER/REPO SERVER_IP DOMAIN
#     bash deploy/configure-github.sh khelilo7/tunisiabasket 203.0.113.10 tunisiabasket.com
# Needs the GitHub CLI, logged in as the repository owner:  brew install gh && gh auth login
set -euo pipefail
REPO="${1:?usage: configure-github.sh OWNER/REPO SERVER_IP DOMAIN}"
HOST="${2:?usage: configure-github.sh OWNER/REPO SERVER_IP DOMAIN}"
DOMAIN="${3:?usage: configure-github.sh OWNER/REPO SERVER_IP DOMAIN}"
KEY="$HOME/.ssh/proastats_deploy"

command -v gh >/dev/null || { echo "Install the GitHub CLI first:  brew install gh   then   gh auth login"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Not logged in to GitHub. Run:  gh auth login"; exit 1; }
[ -f "$KEY" ] || { echo "Deploy key $KEY not found (deploy/provision.sh creates it)."; exit 1; }

ME_ID="$(gh api user --jq .id)"
echo "==> Environment 'production': you ($(gh api user --jq .login)) must approve every deploy; only 'main' may deploy"
gh api -X PUT "repos/$REPO/environments/production" --input - >/dev/null <<JSON
{"reviewers":[{"type":"User","id":$ME_ID}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
gh api -X POST "repos/$REPO/environments/production/deployment-branch-policies" -f name=main -f type=branch >/dev/null 2>&1 || echo "(branch rule for main already exists)"

echo "==> Secrets and variables (stored in the environment, so they stay locked until you approve)"
gh secret set PROD_SSH_KEY --env production --repo "$REPO" < "$KEY"
ssh-keyscan -t ed25519 "$HOST" 2>/dev/null | gh secret set PROD_SSH_KNOWN_HOSTS --env production --repo "$REPO"
gh variable set PROD_HOST --env production --repo "$REPO" --body "$HOST"
gh variable set PROD_USER --env production --repo "$REPO" --body deploy
gh variable set PRODUCTION_DOMAIN --env production --repo "$REPO" --body "$DOMAIN"

echo "==> Secret scanning and push protection"
gh api -X PATCH "repos/$REPO" \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled' >/dev/null \
  || echo "(could not enable it from here: turn it on in Settings > Code security)"

echo
echo "Done. Check: https://github.com/$REPO/settings/environments"
echo "Then run the first deploy: Actions tab > Deploy > Re-run all jobs (or push a small change), and click Approve."
