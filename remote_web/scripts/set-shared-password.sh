#!/bin/bash
# Replace the long random access token with a password you choose, on the
# production VM, this Mac's local server and the cookie-sync config at once.
# The password is typed at a hidden prompt: it never appears on a command
# line, in shell history or in any log. Run from the repo root:
#   ./remote_web/scripts/set-shared-password.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$PATH:$HOME/Documents/google-cloud-sdk/bin"

read -r -s -p "New password (min 10 characters): " PW; echo
read -r -s -p "Repeat password: " PW2; echo
[ "$PW" = "$PW2" ] || { echo "Passwords differ - nothing changed." >&2; exit 1; }
[ "${#PW}" -ge 10 ] || { echo "Too short (min 10) - nothing changed." >&2; exit 1; }

gcloud compute start-iap-tunnel omniflow-cloud 22 --local-host-port=localhost:2222 \
  --project=omniflow-cloud-260910 --zone=us-west1-b >/dev/null 2>&1 &
TUNNEL=$!
trap 'kill $TUNNEL 2>/dev/null || true' EXIT
sleep 6

printf '%s' "$PW" | ssh -i ~/.ssh/omniflow_cloud -p 2222 omniflow@localhost \
  'cd ~/omniflow && .venv/bin/python -c "import sys;from remote_web import config;config.set_token(sys.stdin.read())"'
echo "Production updated."

printf '%s' "$PW" | .venv/bin/python -c "import sys;from remote_web import config;config.set_token(sys.stdin.read())"
echo "Local server updated."

umask 077
mkdir -p ~/.config/omniflow
printf '%s' "$PW" > ~/.config/omniflow/cloud_token
chmod 600 ~/.config/omniflow/cloud_token
echo "Cookie-sync config updated. Use the new password on /unlock (local and production)."
