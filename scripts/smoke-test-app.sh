#!/bin/bash
# Smoke test of a BUILT Mac app: opens it, checks the page and the settings API, then checks and
# downloads a short public TikTok clip as MP3 (this runs the bundled ffmpeg) into a temporary
# folder. Needs the network. Run by hand, never from pytest.
#
#   ./scripts/smoke-test-app.sh release/v2.0.0/_build/arm64/ViDrop.app
#   ./scripts/smoke-test-app.sh release/v2.0.0/_build/x86_64/ViDrop.app    # Intel, runs under Rosetta
#
# The app listens on port 5001 (fixed), so stop `scripts/dev.sh` first: this script refuses to
# run while something else holds the port. The app's own config.json is backed up and restored.
set -uo pipefail

APP="${1:?usage: smoke-test-app.sh path/to/ViDrop.app}"
PORT=5001
URL="http://127.0.0.1:$PORT"
CONFIG="$HOME/Library/Application Support/ViDrop/config.json"
CLIP="https://www.tiktok.com/@vio_decor127/video/7650834126223805717"

[ -x "$APP/Contents/MacOS/ViDrop" ] || { echo "not an app: $APP"; exit 2; }
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo "port $PORT is busy ($(lsof -nP -iTCP:$PORT -sTCP:LISTEN | awk 'NR>1{print $1" pid "$2}' | head -1)); stop it first (for example the dev server) and run again."
    exit 3
fi
pgrep -f "MacOS/ViDrop" >/dev/null && { echo "a ViDrop app is already running; quit it first."; exit 3; }

DOWNLOADS="$(mktemp -d)"
BACKUP="$(mktemp)"; HAD_CONFIG=0
if [ -f "$CONFIG" ]; then cp "$CONFIG" "$BACKUP"; HAD_CONFIG=1; fi
cleanup() {
    pkill -f "MacOS/ViDrop" 2>/dev/null; sleep 2; pkill -9 -f "MacOS/ViDrop" 2>/dev/null
    if [ "$HAD_CONFIG" = 1 ]; then cp "$BACKUP" "$CONFIG"; else rm -f "$CONFIG"; fi
    rm -rf "$DOWNLOADS" "$BACKUP"
}
trap cleanup EXIT

FAILED=0
step() { if [ "$2" = ok ]; then echo "  ok    $1"; else echo "  FAIL  $1"; FAILED=1; fi; }

echo "App:  $APP"
echo "Arch: $(lipo -info "$APP/Contents/MacOS/ViDrop" | sed 's/.*is architecture: //')"
"$APP/Contents/MacOS/ViDrop" >/dev/null 2>&1 &
for _ in $(seq 1 40); do curl -s -o /dev/null "$URL/" && break; sleep 1; done

[ "$(curl -s -o /dev/null -w '%{http_code}' "$URL/")" = 200 ] && step "GET / answers 200" ok || step "GET / answers 200" fail
curl -s "$URL/api/settings" | python3 -c "import sys,json; json.load(sys.stdin)['playlist_limit']" 2>/dev/null && step "GET /api/settings" ok || step "GET /api/settings" fail

curl -s -X POST "$URL/api/settings" -H 'Content-Type: application/json' -d "{\"path\":\"$DOWNLOADS\"}" >/dev/null
CHECK="$(curl -s -X POST "$URL/api/check" -H 'Content-Type: application/json' -d "{\"url\":\"$CLIP\"}")"
echo "$CHECK" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('type')=='video'" 2>/dev/null && step "check a TikTok link" ok || step "check a TikTok link" fail

JOB="$(curl -s -X POST "$URL/api/download" -H 'Content-Type: application/json' -d "{\"url\":\"$CLIP\",\"quality\":\"Audio Only\",\"title\":\"smoke\"}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null)"
STATUS=running
for _ in $(seq 1 60); do
    STATUS="$(curl -s "$URL/api/progress/$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status'))" 2>/dev/null)"
    [ "$STATUS" != running ] && break; sleep 1.5
done
[ "$STATUS" = done ] && step "download finishes (status: $STATUS)" ok || step "download finishes (status: $STATUS)" fail
CODEC="$(ffprobe -v error -show_entries stream=codec_name -of csv=p=0 "$DOWNLOADS"/smoke.mp3 2>/dev/null | head -1)"
[ "$CODEC" = mp3 ] && step "the saved file is a real MP3" ok || step "the saved file is a real MP3 (got: ${CODEC:-nothing})" fail

[ "$FAILED" = 0 ] && echo "SMOKE TEST PASSED" || echo "SMOKE TEST FAILED"
exit $FAILED
