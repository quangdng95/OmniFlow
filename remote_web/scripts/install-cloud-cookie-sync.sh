#!/bin/bash
# Installs a LaunchAgent that runs sync_cloud_cookies.py every 6 hours, so
# the OmniFlow cloud deployment's YouTube/Instagram/Threads session stays
# fresh while this Mac is on. Also runs it once now.
#
# Usage:  bash remote_web/scripts/install-cloud-cookie-sync.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO_ROOT/.venv/bin/python3"
SCRIPT="$REPO_ROOT/remote_web/scripts/sync_cloud_cookies.py"
PLIST="$HOME/Library/LaunchAgents/com.omniflow.cloudcookies.plist"
LOG_DIR="$HOME/Library/Logs/OmniFlowCloudCookies"

[ -x "$PY" ] || { echo "No venv python at $PY - run the repo setup first"; exit 1; }
[ -f "$SCRIPT" ] || { echo "Missing $SCRIPT"; exit 1; }
mkdir -p "$LOG_DIR"

echo "### one-off sync now (approve the Keychain prompt if it appears)"
"$PY" "$SCRIPT"

echo "### writing LaunchAgent -> $PLIST"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.omniflow.cloudcookies</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$SCRIPT</string>
  </array>
  <key>StartInterval</key><integer>21600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/out.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/err.log</string>
</dict>
</plist>
PL

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "### done - syncs every 6h while the Mac is awake. Logs: $LOG_DIR"
echo "### remove later with:  launchctl unload $PLIST && rm $PLIST"
