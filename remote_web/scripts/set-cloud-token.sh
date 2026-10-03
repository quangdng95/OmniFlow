#!/bin/bash
# Saves the OmniFlow cloud access token where sync_cloud_cookies.py reads it
# (~/.config/omniflow/cloud_token, chmod 600). Run once.
#
#   bash remote_web/scripts/set-cloud-token.sh            # prompts, input hidden
#   some-command-that-prints-the-token | bash remote_web/scripts/set-cloud-token.sh
#
# The token is the same one you type on the unlock page / the iOS Shortcut uses.
set -euo pipefail

FILE="$HOME/.config/omniflow/cloud_token"
mkdir -p "$(dirname "$FILE")"
chmod 700 "$(dirname "$FILE")"

if [ -t 0 ]; then
  printf 'Cloud access token (input hidden): '
  read -rs TOKEN
  echo
else
  read -r TOKEN
fi

[ -n "$TOKEN" ] || { echo "Empty token - nothing saved." >&2; exit 1; }

umask 077
printf '%s\n' "$TOKEN" > "$FILE"
chmod 600 "$FILE"
echo "Saved to $FILE (mode 600)."
